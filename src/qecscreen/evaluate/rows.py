"""Measurement rows (D-009), and the guard that keeps calibration output out of them.

**The row writer (M0-RUN-01).** ``build_row(code, checkpoint_dir)`` turns one
code's finished checkpoint directory (``qecscreen.evaluate.checkpoint``) into
one row of the measurements table, whose columns are exactly
``spec/architecture.md §3``'s (``MEASUREMENT_COLUMNS``). Features and
predictions live in other files (D-009), so no column here is ``pred_*``
(INV-1).

- Counts come from the checkpoint's ``result.parquet``, checked against its
  shards. Censoring and the Wilson interval come only from
  ``evaluate.label.make_label`` (INV-3), so from ``qecscreen.protocol``.
- ``sampling_seed`` comes only from ``protocol.sampling_seed(code_id,
  protocol_hash)``, and must equal the seed the checkpoint was run with. The
  hash includes the installed decoder version, so building a row where
  another ldpc is installed than the one that decoded it is refused here.
- ``code_id`` is CONTRACT's formula, via ``qecscreen.codes.ids``.
- ``commit_sha``, ``stim_version`` and ``cpu_class`` come from the shards,
  never from the process building the row (D-017, D-027). Shards that
  disagree on any of them are refused (D-032). A missing, empty or
  placeholder ``commit_sha`` is refused.
- ``seed`` is 0: the M0 population is admitted with ``generate(..., seed=0)``
  and ``estimate_d_upper(..., seed=0)`` (D-031). ``d_exact`` is null (INV-5).

**The guard.** The decoder calibration (``qecscreen.evaluate.calibrate``)
measures under settings that are not the pinned protocol, at values of ``p``
and shot counts chosen for calibration, so a calibration number in the
dataset would be a label from a different protocol under the pinned
protocol's hash (INV-6). Every calibration file and record carries
``"calibration": true``. ``reject_calibration`` refuses anything that does,
and ``build_row`` calls it on every input before building anything.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from qecscreen.codes import ids
from qecscreen.codes.bb import generate
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.codes.validate import validate
from qecscreen.evaluate.checkpoint import PROVENANCE_FIELDS, CodeCheckpoint
from qecscreen.evaluate.label import make_label
from qecscreen.protocol import (
    MAX_SHOTS,
    MIN_FAILURES,
    P_PILOT,
    SCHEMA_VERSION,
    SHOT_BATCH,
    Protocol,
    installed_decoder_version,
    protocol_hash,
    sampling_seed,
)

__all__ = [
    "CALIBRATION_MARKER",
    "CalibrationOutputError",
    "MEASUREMENT_COLUMNS",
    "MEASUREMENT_SCHEMA",
    "RowBuildError",
    "build_row",
    "reject_calibration",
    "rows_table",
]

# The key every calibration file and record sets to true.
CALIBRATION_MARKER = "calibration"

# spec/architecture.md §3, in its order and with its types. Nothing else is a
# column (INV-1: no pred_*, no undeclared metadata).
MEASUREMENT_SCHEMA = pa.schema([
    pa.field("code_id", pa.string(), nullable=False),
    pa.field("construction_program_id", pa.string(), nullable=False),
    pa.field("family", pa.string(), nullable=False),
    pa.field("params_json", pa.string(), nullable=False),
    pa.field("seed", pa.int64(), nullable=False),
    pa.field("n", pa.int32(), nullable=False),
    pa.field("k", pa.int32(), nullable=False),
    pa.field("d_exact", pa.int32(), nullable=True),
    pa.field("d_upper", pa.int32(), nullable=False),
    pa.field("phi_from_d_upper", pa.float64(), nullable=False),
    pa.field("n_ancilla", pa.int32(), nullable=False),
    pa.field("n_total", pa.int32(), nullable=False),
    pa.field("protocol_hash", pa.string(), nullable=False),
    pa.field("commit_sha", pa.string(), nullable=False),
    pa.field("sampling_seed", pa.int64(), nullable=False),
    pa.field("stim_version", pa.string(), nullable=False),
    pa.field("cpu_class", pa.string(), nullable=False),
    pa.field("p", pa.float64(), nullable=False),
    pa.field("rounds", pa.int32(), nullable=False),
    pa.field("shots", pa.int64(), nullable=False),
    pa.field("failures", pa.int64(), nullable=False),
    pa.field("true_ler", pa.float64(), nullable=True),
    pa.field("true_ler_ub", pa.float64(), nullable=False),
    pa.field("true_ler_ci_low", pa.float64(), nullable=False),
    pa.field("true_ler_ci_high", pa.float64(), nullable=False),
    pa.field("censored", pa.bool_(), nullable=False),
    pa.field("decode_seconds", pa.float64(), nullable=False),
    pa.field("schema_version", pa.int32(), nullable=False),
    pa.field("created_at", pa.string(), nullable=False),
])
MEASUREMENT_COLUMNS = tuple(MEASUREMENT_SCHEMA.names)

# D-031: the M0 population is admitted with generate(..., seed=0) and
# estimate_d_upper(..., seed=0); the row stores the seed that regenerates it.
_CODE_SEED = 0

# A git object id, and never all zeros (a common placeholder).
_COMMIT_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class CalibrationOutputError(ValueError):
    """Calibration output was offered where a dataset row was expected."""


class RowBuildError(ValueError):
    """A checkpoint cannot become a measurement row."""


def _refuse(what: str) -> None:
    raise CalibrationOutputError(
        f"{what} is decoder-calibration output ('{CALIBRATION_MARKER}': true), not a "
        "dataset row; calibration is never written to the dataset"
    )


def _check_json_file(path: Path) -> None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return  # not JSON: not calibration output, which is always JSON
    if isinstance(obj, Mapping) and obj.get(CALIBRATION_MARKER):
        _refuse(str(path))


def reject_calibration(source: Any) -> None:
    """Raise ``CalibrationOutputError`` if ``source`` is or contains calibration output.

    ``source`` may be a mapping (one record), a pandas-like frame (anything
    with ``columns``; the marker column's presence is enough), a path to a
    file or a directory (every ``*.json`` under it is checked), or an
    iterable of any of these. Returns ``None`` otherwise.
    """
    if isinstance(source, Mapping):
        if source.get(CALIBRATION_MARKER):
            _refuse("a record")
        return
    if hasattr(source, "columns"):
        if CALIBRATION_MARKER in list(source.columns):
            _refuse("a frame")
        return
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        if path.is_dir():
            for f in sorted(path.rglob("*.json")):
                _check_json_file(f)
        elif path.is_file() and path.suffix == ".json":
            _check_json_file(path)
        return
    if isinstance(source, Iterable) and not isinstance(source, (bytes, bytearray)):
        for item in source:
            reject_calibration(item)


def _check_commit(commit: Any, where: Path) -> str:
    if not isinstance(commit, str) or not commit:
        raise RowBuildError(f"{where}: commit_sha is missing; a row needs the commit that produced it (D-017)")
    if not _COMMIT_RE.fullmatch(commit) or set(commit) == {"0"}:
        raise RowBuildError(
            f"{where}: commit_sha {commit!r} is a placeholder, not a 40- or 64-hex git object id (D-017)"
        )
    return commit


def build_row(
    code: Mapping[str, Any],
    checkpoint_dir: str | os.PathLike[str],
    *,
    p: float = P_PILOT,
    batch_size: int = SHOT_BATCH,
    max_shots: int = MAX_SHOTS,
    created_at: str | None = None,
) -> dict[str, Any]:
    """One measurement row for ``code`` from its finished ``checkpoint_dir``.

    ``code`` holds ``construction_program_id``, ``l``, ``m``, ``a_exps`` and
    ``b_exps``; any of ``code_id``, ``n``, ``k`` and ``d_upper`` it also holds
    must match what the parameters give. ``batch_size`` and ``max_shots``
    must be the ones the checkpoint was run with; they default to CONTRACT's
    and are smaller only in tests. ``created_at`` defaults to now, UTC.

    Raises ``CalibrationOutputError`` on calibration input, and
    ``RowBuildError`` if the code has not finished, its checkpoint is not the
    run this code and protocol imply, or its provenance is missing or mixed.
    """
    directory = Path(checkpoint_dir)
    reject_calibration(code)
    reject_calibration(directory)
    if not directory.is_dir():
        raise RowBuildError(f"{directory} is not a checkpoint directory")
    for f in sorted(directory.glob("*.parquet")):
        reject_calibration(pq.read_table(f).to_pandas())

    program = code["construction_program_id"]
    params = ids.params_json(code["l"], code["m"], code["a_exps"], code["b_exps"])
    cid = ids.code_id(program, params)
    decoded = json.loads(params)
    h_x, h_z = generate(decoded["l"], decoded["m"], [tuple(e) for e in decoded["a_exps"]],
                        [tuple(e) for e in decoded["b_exps"]], seed=_CODE_SEED)
    n, k = validate(h_x, h_z)  # INV-8
    d_upper, _ = estimate_d_upper(h_x, h_z, seed=_CODE_SEED)
    for key, value in (("code_id", cid), ("n", n), ("k", k), ("d_upper", d_upper)):
        if key in code and code[key] != value:
            raise RowBuildError(f"{cid}: the code record says {key}={code[key]!r}, its parameters give {value!r}")

    h = protocol_hash(Protocol(p=p, decoder_version=installed_decoder_version()))
    seed = sampling_seed(cid, h)
    checkpoint = CodeCheckpoint(directory, seed=seed, batch_size=batch_size, max_shots=max_shots)
    try:
        result = checkpoint.result()
        shards = checkpoint.batches()
        provenance = checkpoint.shard_provenance()
    except ValueError as exc:  # another run's checkpoint, or mixed provenance (D-032)
        raise RowBuildError(f"{cid}: {exc}") from exc
    if result is None:
        raise RowBuildError(f"{cid}: {directory} has no result; the code has not finished")
    if not shards or (shards[-1].shots, shards[-1].failures) != (result["shots"], result["failures"]):
        raise RowBuildError(f"{cid}: the result's counts are not its shards' totals")
    stopped = "min_failures" if result["failures"] >= MIN_FAILURES else "max_shots"
    if result["stopped_by"] != stopped or (stopped == "max_shots" and result["shots"] != max_shots):
        raise RowBuildError(f"{cid}: the result stopped by {result['stopped_by']!r} at {result['shots']} shots")
    assert provenance is not None  # there are shards
    commit = _check_commit(provenance["commit_sha"], directory)
    for field in ("stim_version", "cpu_class"):
        if not provenance[field]:
            raise RowBuildError(f"{directory}: {field} is missing (D-027)")

    label = make_label(p=p, rounds=d_upper, k=k, shots=result["shots"],
                       failures=result["failures"], decode_seconds=result["decode_seconds"])
    n_ancilla = h_x.shape[0] + h_z.shape[0]  # one ancilla per check (CONTRACT, qubit indexing)
    row = {
        "code_id": cid,
        "construction_program_id": program,
        "family": ids.family(program),
        "params_json": params,
        "seed": _CODE_SEED,
        "n": n,
        "k": k,
        "d_exact": None,  # INV-5: a randomised search gives an upper bound only
        "d_upper": d_upper,
        "phi_from_d_upper": k * d_upper**2 / n,
        "n_ancilla": n_ancilla,
        "n_total": n + n_ancilla,
        "protocol_hash": h,
        "commit_sha": commit,
        "sampling_seed": seed,
        "stim_version": provenance["stim_version"],
        "cpu_class": provenance["cpu_class"],
        "p": label.p,
        "rounds": label.rounds,
        "shots": label.shots,
        "failures": label.failures,
        "true_ler": label.true_ler,
        "true_ler_ub": label.true_ler_ub,
        "true_ler_ci_low": label.true_ler_ci_low,
        "true_ler_ci_high": label.true_ler_ci_high,
        "censored": label.censored,
        "decode_seconds": label.decode_seconds,
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    assert tuple(row) == MEASUREMENT_COLUMNS and set(PROVENANCE_FIELDS) <= set(row)
    return row


def rows_table(rows: Sequence[Mapping[str, Any]]) -> pa.Table:
    """``rows`` as a table of exactly ``MEASUREMENT_SCHEMA`` (LERs float64, never float32)."""
    for row in rows:
        reject_calibration(row)
        if tuple(row) != MEASUREMENT_COLUMNS:
            raise RowBuildError(f"a row's columns are not MEASUREMENT_COLUMNS: {list(row)}")
    return pa.Table.from_pylist([dict(r) for r in rows], schema=MEASUREMENT_SCHEMA)
