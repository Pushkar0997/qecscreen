"""M0-RUN-01: the M0 pilot, run as a chain of Kaggle sessions (D-031, D-032, D-033).

The pilot labels every code of the M0 population (``m0_population()``: the 244
admissible BB codes at n <= 72, enumerated) at ``P_PILOT`` with the pinned
BP+OSD. One Kaggle session cannot do it, so the work is cumulative across
sessions. **All of it lives in one pilot directory:**

- ``manifest.json``: what every session must agree on (``MANIFEST_KEYS``);
- ``population.parquet``: the population, with ``n``, ``k``, ``d_upper`` and
  ``n_d_upper`` (``n * d_upper``);
- one checkpoint directory per ``code_id`` (``qecscreen.evaluate.checkpoint``);
- ``stale/``: partial checkpoints that could not be continued, moved aside,
  never deleted;
- one ``session_NNN.json`` summary per session;
- ``inventory.json``: the sha256 of every other file, rewritten at each snapshot.

**The archive** (D-033 amendment 2). Kaggle keeps at most 500 files of a
version's output, and the pilot directory reaches ~10,000. So the pilot
directory lives in a scratch directory (the notebook's ``/kaggle/tmp/m0-pilot``)
and the only pilot file in ``archive_dir`` (``/kaggle/working``) is one
uncompressed tar, ``m0-pilot.tar``, with a sidecar ``m0-pilot.tar.sha256``,
beside the session summary without its inventory. The tar is written to
``.tmp``, fsynced and renamed, every ``SNAPSHOT_MINUTES`` and at session end,
so a session that dies still leaves its last snapshot. ``pilot_cost_report``
and ``assemble_measurements`` take the tar or an extracted directory.

**Session start** (``run_session``). With ``previous`` (a notebook's earlier
output, attached under ``/kaggle/input``), the one ``m0-pilot.tar`` under it is
checked against its sidecar's sha256 and extracted into ``out_dir``; zero or
two tars are refused. (A ``previous`` holding no tar but one pilot directory is
copied verbatim.) Either way the files are checked against the inventory the
last snapshot, or failing that the last session, recorded, so an output Kaggle
truncated is refused rather than resumed. A pilot with a manifest but no
session summary is a probe that died before its end, and is resumed as the
probe. The first session writes the manifest; every
later one refuses to start if the protocol hash, the installed ldpc or stim,
the commit or the population digest differ, and says which. The population is
enumerated every session and checked against ``POPULATION_SIZE`` and
``POPULATION_SHA256``, pinned here, so a change to enumeration fails loudly.

**Scheduling.** One spawned worker per code, ``processes`` at a time, longest
first by ``n * d_upper``. Each runs ``sample_and_decode`` with the code's
checkpoint directory and the session deadline, which it checks between
batches: it flushes its shard and exits cleanly, so the session ends before
Kaggle's limit rather than by being killed. No new worker starts after the
deadline. A partial code whose shards were written on another ``cpu_class``,
or whose re-drawn shots do not reproduce its digests (D-032), is moved to
``stale/<code_id>-<cpu_class>-<utc>/`` and restarted from batch 0. A worker
that dies is recorded with its exit code and retried in the next session;
a code that dies in two sessions is failed and not run again (AGENTS §4: two
failures, stop). A finished code is never re-run.

**Session 1 is the probe.** The runner knows it is session 1 because the
manifest is absent. It runs ``PROBE_CODES`` codes at evenly spaced ranks of
``n * d_upper``, the largest included, for ``PROBE_WALL_HOURS``, and stops;
its work counts toward the pilot. Every later session refuses to start
unless ``cost_gate`` names the ``spec/evals.md §7`` entry that approved the
probe's cost report (``pilot_cost_report``, run locally on the downloaded
probe), and records it in the manifest.

**Final assembly** (``assemble_measurements``) builds every row, checks one
protocol and all 244 rows, and writes ``data/m0_measurements.parquet``. It
refuses while any code is unfinished.
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime
import hashlib
import json
import multiprocessing
import multiprocessing.connection
import os
import shutil
import sys
import tarfile
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from qecscreen import provenance
from qecscreen.circuits.build import build_memory_circuit
from qecscreen.codes import ids
from qecscreen.codes.bb import generate
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.codes.sample import admissible_codes
from qecscreen.codes.validate import validate
from qecscreen.evaluate.checkpoint import (
    RESULT_FILE,
    CodeCheckpoint,
    ProvenanceMismatchError,
    SampleDigestMismatchError,
)
from qecscreen.evaluate.rows import build_row, reject_calibration, rows_table
from qecscreen.evaluate.run import sample_and_decode
from qecscreen.protocol import (
    MAX_SHOTS,
    MIN_FAILURES,
    P_PILOT,
    SHOT_BATCH,
    Protocol,
    assert_single_protocol,
    protocol_hash,
    sampling_seed,
)

__all__ = [
    "ARCHIVE_FILE",
    "BUDGET",
    "EXIT_STALE",
    "MANIFEST_KEYS",
    "MEASUREMENTS_FILE",
    "POPULATION_SHA256",
    "POPULATION_SIZE",
    "PROCESSES",
    "PROBE_CODES",
    "PROBE_WALL_HOURS",
    "SESSION_WALL_HOURS",
    "SNAPSHOT_MINUTES",
    "PilotConfig",
    "PilotRefusal",
    "assemble_measurements",
    "format_cost_report",
    "format_session",
    "locate_pilot",
    "m0_population",
    "pilot_cost_report",
    "population_digest",
    "probe_codes",
    "run_session",
]

# D-031: M0's population is every admissible code at n <= 72.
BUDGET = 72
POPULATION_SIZE = 244
# population_digest(m0_population()). Pinned so that any change to the
# templates, the (l, m) grid, validate or estimate_d_upper fails loudly here.
POPULATION_SHA256 = "5008e14eb8292df8549aa5fddada442938ce52f91950e4612dfbb85dc6e3d94f"

PROCESSES = 4  # Kaggle's 4 cores, one code per process (D-026)
SESSION_WALL_HOURS = 10.5  # owner, 2026-09-28 (D-033): under Kaggle's 12 h, with margin
PROBE_CODES = 12  # owner, 2026-09-28 (D-033): session 1 runs this many codes
PROBE_WALL_HOURS = 3.0  # owner, 2026-09-28 (D-033); proposed 2.0

# spec/architecture.md §6: the budget-72 re-projection at P_PILOT, and its 3x ceiling.
PROJECTED_CORE_HOURS = 52.5
CEILING_CORE_HOURS = 158.0

MEASUREMENTS_FILE = "m0_measurements.parquet"  # owner, 2026-09-28, under data/ (architecture §2)
MANIFEST_FILE = "manifest.json"
POPULATION_FILE = "population.parquet"
STALE_DIR = "stale"
INVENTORY_FILE = "inventory.json"
FORMAT = "qecscreen_m0_pilot_v1"

# D-033 amendment 2 (owner, 2026-09-28): Kaggle keeps at most 500 output files.
KAGGLE_WORKING = "/kaggle/working"  # what Kaggle keeps as a version's output
ARCHIVE_FILE = "m0-pilot.tar"  # uncompressed; the only pilot file in archive_dir
ARCHIVE_ROOT = "m0-pilot"  # the tar's one top-level directory
SHA256_SUFFIX = ".sha256"  # sidecar: "<sha256>  m0-pilot.tar", as sha256sum writes it
SNAPSHOT_MINUTES = 60.0  # owner: the tar is refreshed this often, and at session end
EXIT_STALE = 75  # a worker's exit code for "this partial checkpoint cannot be continued"

# Every session must agree on these with the first (D-033).
MANIFEST_KEYS = ("protocol_hash", "decoder_version", "stim_version", "commit_sha",
                 "population_sha256", "p", "batch_size", "max_shots")

_POPULATION_KEYS = ("code_id", "construction_program_id", "params_json", "n", "k", "d_upper")
_POPULATION_SCHEMA = pa.schema([
    pa.field("code_id", pa.string()),
    pa.field("construction_program_id", pa.string()),
    pa.field("params_json", pa.string()),
    pa.field("n", pa.int64()),
    pa.field("k", pa.int64()),
    pa.field("d_upper", pa.int64()),
    pa.field("n_d_upper", pa.int64()),
])


class PilotRefusal(RuntimeError):
    """A session refuses to start, or assembly refuses to write."""


@dataclasses.dataclass(frozen=True)
class PilotConfig:
    """One session's settings. The notebook sets ``previous`` and ``cost_gate`` only.

    ``previous`` is ``None`` or a path (under ``/kaggle/input``) holding
    exactly one ``m0-pilot.tar``. ``cost_gate`` is required from session 2 on:
    the ``spec/evals.md §7`` entry that approved the probe's cost report.
    ``archive_dir`` is where the tar, its sidecar and the session summary go:
    ``/kaggle/working`` by default, which must exist; ``None`` writes no archive
    (tests, and a local run). The underscored fields are for tests only: a small
    population, small batches, a hook run first in each worker, and the
    snapshot period.
    """

    previous: str | None = None
    cost_gate: str | None = None
    session_wall_hours: float = SESSION_WALL_HOURS
    probe_wall_hours: float = PROBE_WALL_HOURS
    probe_codes: int = PROBE_CODES
    processes: int = PROCESSES
    archive_dir: str | None = KAGGLE_WORKING
    _population: tuple[Mapping[str, Any], ...] | None = None
    _batch_size: int = SHOT_BATCH
    _max_shots: int = MAX_SHOTS
    _worker_setup: Callable[[Mapping[str, Any]], None] | None = None
    _snapshot_minutes: float = SNAPSHOT_MINUTES

    def __post_init__(self) -> None:
        if min(self.session_wall_hours, self.probe_wall_hours) < 0 or min(self.processes, self.probe_codes) < 1:
            raise ValueError("wall hours must be >= 0, and processes and probe_codes >= 1")
        if not self._snapshot_minutes > 0:
            raise ValueError("the snapshot period must be > 0")
        if not 0 < self._max_shots <= MAX_SHOTS or self._max_shots % self._batch_size:
            raise ValueError("max_shots must be a whole number of batches, at most MAX_SHOTS")


# --- population ---------------------------------------------------------------


def _record(params: Mapping[str, Any]) -> dict[str, Any]:
    pj = ids.params_json(params["l"], params["m"], params["a_exps"], params["b_exps"])
    rec = {"code_id": ids.code_id(params["construction_program_id"], pj),
           "construction_program_id": params["construction_program_id"], "params_json": pj}
    if {"n", "k", "d_upper"} <= set(params):
        n, k, d = params["n"], params["k"], params["d_upper"]
    else:
        h_x, h_z = generate(params["l"], params["m"], [tuple(e) for e in params["a_exps"]],
                            [tuple(e) for e in params["b_exps"]], seed=0)
        n, k = validate(h_x, h_z)
        d, _ = estimate_d_upper(h_x, h_z, seed=0)
    return {**rec, "n": int(n), "k": int(k), "d_upper": int(d), "n_d_upper": int(n) * int(d)}


def population_digest(records: Sequence[Mapping[str, Any]]) -> str:
    """sha256 of the population's canonical JSON, sorted by ``code_id``."""
    canon = sorted(({k: r[k] for k in _POPULATION_KEYS} for r in records), key=lambda r: r["code_id"])
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def m0_population() -> list[dict[str, Any]]:
    """The M0 population (D-031), checked against ``POPULATION_SIZE`` and ``POPULATION_SHA256``."""
    records = [_record(p) for p in admissible_codes(BUDGET)]
    digest = population_digest(records)
    if len(records) != POPULATION_SIZE or digest != POPULATION_SHA256:
        raise PilotRefusal(
            f"the enumerated M0 population has {len(records)} codes and digest {digest}; pinned: "
            f"{POPULATION_SIZE} and {POPULATION_SHA256}. Enumeration changed (templates, (l, m) "
            "grid, validate or estimate_d_upper); the pilot cannot continue on another population"
        )
    return records


def _code(rec: Mapping[str, Any]) -> dict[str, Any]:
    """A population record as the mapping ``build_memory_circuit`` and ``build_row`` take."""
    return {**json.loads(rec["params_json"]), **{k: rec[k] for k in (
        "code_id", "construction_program_id", "n", "k", "d_upper")}}


def _read_population(pilot: Path) -> list[dict[str, Any]]:
    return pq.read_table(pilot / POPULATION_FILE).to_pylist()


def _longest_first(population: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(population, key=lambda r: (-r["n_d_upper"], r["code_id"]))


def probe_codes(population: Sequence[Mapping[str, Any]], count: int = PROBE_CODES) -> list[str]:
    """``count`` code_ids at evenly spaced ranks of ``n * d_upper``, largest first.

    Ranks ``round(i * (N - 1) / (count - 1))`` (half up) for ``i = 0 .. count - 1``
    of the population sorted by ``n * d_upper`` descending, ties by ``code_id``,
    so the largest and the smallest code are both in. Every code if ``count >= N``.
    """
    order = _longest_first(population)
    n = len(order)
    if count >= n:
        return [r["code_id"] for r in order]
    if count == 1:
        return [order[0]["code_id"]]
    ranks = [(2 * i * (n - 1) + (count - 1)) // (2 * (count - 1)) for i in range(count)]
    return [order[r]["code_id"] for r in ranks]


# --- files --------------------------------------------------------------------


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path) -> dict[str, str]:
    """Every file under ``root``: relative posix path -> sha256. ``.tmp`` files excluded."""
    return {p.relative_to(root).as_posix(): _sha256(p)
            for p in sorted(root.rglob("*")) if p.is_file() and not p.name.endswith(".tmp")}


def _write_json(path: Path, obj: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _summaries(pilot: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pilot.glob("session_*.json"))]


def _is_pilot_manifest(path: Path) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("format") == FORMAT
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False


def locate_pilot(previous: str | os.PathLike[str]) -> Path:
    """The one pilot directory under ``previous``; refuses zero or several."""
    root = Path(previous)
    if not root.is_dir():
        raise PilotRefusal(f"PREVIOUS={root} is not a directory")
    found = sorted({m.parent for m in root.rglob(MANIFEST_FILE) if _is_pilot_manifest(m)})
    if len(found) != 1:
        raise PilotRefusal(
            f"PREVIOUS={root} holds no {ARCHIVE_FILE} and {len(found)} pilot directories, not exactly one: "
            f"{[str(f) for f in found]}. Attach only the previous session's output"
        )
    return found[0]


def _check_inventory(pilot: Path, files: Mapping[str, str] | None = None) -> None:
    """Refuse a pilot lacking or altering a file its last snapshot (else its last session) recorded."""
    files = _files(pilot) if files is None else files
    if (pilot / INVENTORY_FILE).is_file():
        recorded, by = json.loads((pilot / INVENTORY_FILE).read_text(encoding="utf-8"))["files"], "snapshot"
    elif summaries := _summaries(pilot):
        recorded, by = summaries[-1]["inventory"], "session"
    else:
        return
    missing = {p: h for p, h in recorded.items() if files.get(p) != h}
    if missing:
        raise PilotRefusal(
            f"the attached pilot {pilot} lacks or differs in {len(missing)} of the files its last "
            f"{by} recorded, e.g. {sorted(missing)[:5]}; its output was truncated or altered"
        )


def _write_bytes_synced(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _write_archive(pilot: Path, archive_dir: Path, *, reason: str) -> str:
    """Snapshot ``pilot`` as ``<archive_dir>/m0-pilot.tar`` and its sidecar; return the tar's sha256.

    Writes ``inventory.json`` into ``pilot`` first, so the tar carries the
    inventory it is checked against. Shards are only ever renamed into place,
    so a snapshot taken while workers run holds whole shards; a code's newest
    shard may be missing, which costs a batch, not the code. The tar goes to
    ``.tmp``, is fsynced and renamed, then the sidecar the same way: a death
    between the two renames leaves a pair whose sha256 disagrees, which the
    next session refuses.
    """
    files = {p: h for p, h in _files(pilot).items() if p != INVENTORY_FILE}
    _write_json(pilot / INVENTORY_FILE, {"format": FORMAT, "taken_at": _utc(), "reason": reason, "files": files})
    target = archive_dir / ARCHIVE_FILE
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "wb") as f:
        with tarfile.open(fileobj=f, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for rel in sorted([*files, INVENTORY_FILE]):
                tar.add(pilot / rel, arcname=f"{ARCHIVE_ROOT}/{rel}", recursive=False)
        f.flush()
        os.fsync(f.fileno())
    sha = _sha256(tmp)
    os.replace(tmp, target)
    _write_bytes_synced(target.with_name(ARCHIVE_FILE + SHA256_SUFFIX), f"{sha}  {ARCHIVE_FILE}\n".encode())
    return sha


def _verify_archive(tar_path: Path) -> str:
    """The tar's sha256, after checking it against its sidecar; refuses a mismatch or no sidecar."""
    sidecar = tar_path.with_name(tar_path.name + SHA256_SUFFIX)
    if not sidecar.is_file():
        raise PilotRefusal(f"{tar_path} has no {sidecar.name} beside it; its sha256 cannot be checked")
    recorded = (sidecar.read_text(encoding="utf-8").split() or [""])[0].lower()
    actual = _sha256(tar_path)
    if recorded != actual:
        raise PilotRefusal(f"{tar_path} has sha256 {actual}, but {sidecar.name} records {recorded!r}; "
                           "the archive is corrupt or not the one its sidecar describes")
    return actual


def _extract_archive(tar_path: Path, dest: Path) -> None:
    """Extract a pilot tar's ``m0-pilot/`` into ``dest``. Only plain files and
    directories under that one root; anything else is refused, not skipped."""
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, mode="r:") as tar:
        for member in tar:
            parts = PurePosixPath(member.name).parts
            if (not parts or parts[0] != ARCHIVE_ROOT or ".." in parts or member.name.startswith("/")
                    or not (member.isfile() or member.isdir())):
                raise PilotRefusal(f"{tar_path} is not a pilot archive: member {member.name!r}")
            target = dest.joinpath(*parts[1:])
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as src, open(target, "xb") as out:
                shutil.copyfileobj(src, out)
    if not _is_pilot_manifest(dest / MANIFEST_FILE):
        raise PilotRefusal(f"{tar_path} holds no pilot manifest")


@contextlib.contextmanager
def _opened(pilot_or_archive: str | os.PathLike[str]) -> Iterator[Path]:
    """A pilot directory, or a verified ``m0-pilot.tar`` extracted into a temporary one."""
    path = Path(pilot_or_archive)
    if not path.is_file():
        yield path
        return
    _verify_archive(path)
    with tempfile.TemporaryDirectory(prefix="qecscreen-pilot-") as tmp:
        pilot = Path(tmp) / ARCHIVE_ROOT
        _extract_archive(path, pilot)
        _check_inventory(pilot)
        yield pilot


def _copy_previous(previous: str, out: Path, archive: Path | None) -> Path:
    """Bring the previous session's pilot into ``out``: its one tar, or failing that its one pilot directory."""
    root = Path(previous)
    if not root.is_dir():
        raise PilotRefusal(f"PREVIOUS={root} is not a directory")
    tars = sorted(p for p in root.rglob(ARCHIVE_FILE) if p.is_file())
    if len(tars) > 1:
        raise PilotRefusal(
            f"PREVIOUS={root} holds {len(tars)} {ARCHIVE_FILE} files, not exactly one: "
            f"{[str(t) for t in tars]}. Attach only the previous session's output"
        )
    src = tars[0] if tars else locate_pilot(root)
    if out.exists() and any(out.iterdir()):
        raise PilotRefusal(
            f"OUT_DIR={out} is not empty; a session with PREVIOUS copies into an empty OUT_DIR. "
            "To continue in this same session, set PREVIOUS = None"
        )
    if tars:
        if archive is not None and src.parent.resolve() == archive.resolve():
            raise PilotRefusal(f"PREVIOUS's {src} would be overwritten by this session's archive")
        _verify_archive(src)
        _extract_archive(src, out)
        _check_inventory(out)
        return src
    if out.resolve().is_relative_to(src.resolve()) or src.resolve().is_relative_to(out.resolve()):
        raise PilotRefusal(f"OUT_DIR={out} and the previous pilot {src} overlap")
    source = _files(src)
    _check_inventory(src, source)  # what the previous session wrote, against what was attached
    shutil.copytree(src, out, dirs_exist_ok=True)
    copied = _files(out)
    if copied != source:
        bad = sorted(set(copied) ^ set(source) | {p for p in source if copied.get(p) != source[p]})
        raise PilotRefusal(f"the copy of {src} into {out} differs in {len(bad)} files, e.g. {bad[:5]}")
    return src


# --- manifest -----------------------------------------------------------------


def _current(population_sha: str, config: PilotConfig) -> dict[str, Any]:
    prov = provenance.record()
    if not prov["commit_sha"]:
        raise PilotRefusal(
            "no resolved commit: qecscreen is not installed from a pinned git commit, so no row "
            "could carry a commit_sha (D-017). Install by SHA, as the notebook's cell 1 does"
        )
    return {
        "protocol_hash": protocol_hash(Protocol(p=P_PILOT, decoder_version=prov["decoder_version"])),
        "decoder_version": prov["decoder_version"],
        "stim_version": prov["stim_version"],
        "commit_sha": prov["commit_sha"],
        "population_sha256": population_sha,
        "p": P_PILOT,
        "batch_size": config._batch_size,
        "max_shots": config._max_shots,
    }


def _check_manifest(out: Path, current: Mapping[str, Any], population: Sequence[Mapping[str, Any]]) -> dict:
    """The manifest, written by the first session and checked by every later one."""
    path = out / MANIFEST_FILE
    if not path.exists():
        if out.exists() and any(out.iterdir()):
            raise PilotRefusal(f"{out} holds files but no manifest; it is not a pilot directory")
        out.mkdir(parents=True, exist_ok=True)
        rows = [{**{k: r[k] for k in _POPULATION_KEYS}, "n_d_upper": r["n_d_upper"]} for r in population]
        pq.write_table(pa.Table.from_pylist(rows, schema=_POPULATION_SCHEMA), out / POPULATION_FILE)
        manifest = {"format": FORMAT, "created_at": _utc(), **current}
        _write_json(path, manifest)
        return manifest
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise PilotRefusal(f"{path} is not a pilot manifest")
    differs = [f"{k}: recorded {manifest.get(k)!r}, this session {current[k]!r}"
               for k in MANIFEST_KEYS if manifest.get(k) != current[k]]
    if differs:
        raise PilotRefusal("refusing to start: this session differs from the pilot's manifest in "
                           + "; ".join(differs))
    stored = population_digest(_read_population(out))
    if stored != manifest["population_sha256"]:
        raise PilotRefusal(f"{out / POPULATION_FILE} does not match the manifest's population digest")
    return manifest


# --- one code -----------------------------------------------------------------


def _pilot_worker(job: Mapping[str, Any]) -> None:
    """Worker process entry point: run (or resume) one code until it stops or the deadline."""
    if job["setup"] is not None:
        job["setup"](job)
    code = job["code"]
    circuit = build_memory_circuit(code, job["p"], code["d_upper"])  # r = d_upper (D-006)
    try:
        sample_and_decode(circuit, seed=job["seed"], batch_size=job["batch_size"],
                          max_shots=job["max_shots"], checkpoint_dir=job["dir"], deadline=job["deadline"])
    except SampleDigestMismatchError:
        sys.exit(EXIT_STALE)
    except ProvenanceMismatchError as exc:
        if exc.field == "cpu_class":
            sys.exit(EXIT_STALE)
        raise


def _start_worker(ctx: Any, job: Mapping[str, Any]) -> Any:
    proc = ctx.Process(target=_pilot_worker, args=(job,), daemon=True)
    proc.start()
    return proc


def _shard_tables(directory: Path) -> list[dict[str, Any]]:
    return [pq.read_table(p).to_pylist()[0] for p in sorted(directory.glob("batch_*.parquet"))]


def _decode_seconds(pilot: Path) -> float:
    """Decode seconds in every shard under ``pilot``, stale ones included."""
    return sum(r["batch_decode_seconds"] for p in pilot.rglob("batch_*.parquet")
               for r in pq.read_table(p, columns=["batch_decode_seconds"]).to_pylist())


def _move_stale(out: Path, code_id: str, cpu_class: str | None, reason: str) -> dict[str, Any]:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = out / STALE_DIR / f"{code_id}-{(cpu_class or 'unknown').replace('/', '_')}-{stamp}"
    dest.parent.mkdir(exist_ok=True)
    os.replace(out / code_id, dest)
    return {"code_id": code_id, "reason": reason, "cpu_class": cpu_class,
            "moved_to": dest.relative_to(out).as_posix()}


# --- a session ----------------------------------------------------------------


def run_session(config: PilotConfig, out_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Run one session of the pilot into ``out_dir``; write and return its summary."""
    started_at, t0 = _utc(), time.time()
    out = Path(out_dir)
    archive = None if config.archive_dir is None else Path(config.archive_dir)
    if archive is not None:
        if not archive.is_dir():
            raise PilotRefusal(f"archive_dir={archive} is not a directory (on Kaggle: {KAGGLE_WORKING})")
        if out.resolve().is_relative_to(archive.resolve()):
            raise PilotRefusal(
                f"OUT_DIR={out} is inside archive_dir={archive}: Kaggle keeps at most 500 output files, "
                f"and the pilot directory holds up to ~10,000. Put OUT_DIR in a scratch directory"
            )
    copied_from = _copy_previous(config.previous, out, archive) if config.previous is not None else None
    # Session 1 is the probe. A manifest with no session summary is a probe that
    # died before its end (its last snapshot was attached): it is resumed as the probe.
    probe = not (out / MANIFEST_FILE).exists() or not _summaries(out)
    gate = (config.cost_gate or "").strip()
    if probe and gate:
        raise PilotRefusal(
            f"{out} holds no completed session, so this session is the probe; but COST_GATE is set, "
            "which only a later session needs. Did you forget PREVIOUS?"
        )

    population = ([_record(p) for p in config._population] if config._population is not None
                  else m0_population())
    current = _current(population_digest(population), config)
    manifest = _check_manifest(out, current, population)
    previous_summaries = _summaries(out)
    session = len(previous_summaries) + 1
    if probe:
        manifest = {**manifest, "probe_codes": probe_codes(population, config.probe_codes)}
    elif not gate:
        raise PilotRefusal(
            "refusing to start: session 1 was the probe, and every later session needs COST_GATE, "
            "the spec/evals.md §7 entry that approved the probe's cost report (pilot_cost_report)"
        )
    else:
        manifest = {**manifest, "cost_gates": manifest.get("cost_gates", [])
                    + [{"session": session, "cost_gate": gate, "at": _utc()}]}
    _write_json(out / MANIFEST_FILE, manifest)
    deadline = t0 + (config.probe_wall_hours if probe else config.session_wall_hours) * 3600.0
    here_cpu = provenance.cpu_class()
    seconds_before = _decode_seconds(out)

    deaths = Counter(d["code_id"] for s in previous_summaries for d in s["died"])
    failed = sorted(cid for cid, n in deaths.items() if n >= 2)
    stale: list[dict[str, Any]] = []
    todo = []
    for rec in _longest_first(population):
        cid = rec["code_id"]
        d = out / cid
        if (d / RESULT_FILE).exists() or cid in failed or (probe and cid not in manifest["probe_codes"]):
            continue
        shards = _shard_tables(d) if d.exists() else []
        if shards and shards[-1]["cpu_class"] != here_cpu:
            stale.append(_move_stale(out, cid, shards[-1]["cpu_class"], "cpu_class"))
        todo.append(rec)

    def job(rec: Mapping[str, Any]) -> dict[str, Any]:
        return {"code": _code(rec), "p": manifest["p"], "seed": sampling_seed(rec["code_id"], manifest["protocol_hash"]),
                "batch_size": manifest["batch_size"], "max_shots": manifest["max_shots"],
                "dir": str(out / rec["code_id"]), "deadline": deadline, "setup": config._worker_setup}

    ctx = multiprocessing.get_context("spawn")  # no fork of a threaded kernel
    pending, running = list(todo), {}
    started, died, restarted = [], [], set()
    period = config._snapshot_minutes * 60.0
    next_snapshot = t0 + period
    while pending or running:
        while pending and len(running) < config.processes and time.time() < deadline:
            rec = pending.pop(0)
            proc = _start_worker(ctx, job(rec))
            running[proc.sentinel] = (rec, proc)
            started.append(rec["code_id"])
            print(f"started {rec['code_id']} (n*d_upper={rec['n_d_upper']})", flush=True)
        if not running:
            break
        multiprocessing.connection.wait(
            list(running), timeout=None if archive is None else max(0.0, next_snapshot - time.time()))
        if archive is not None and time.time() >= next_snapshot:
            sha = _write_archive(out, archive, reason="periodic")
            next_snapshot = time.time() + period
            print(f"snapshot {archive / ARCHIVE_FILE} sha256 {sha}", flush=True)
        for sentinel, (rec, proc) in list(running.items()):
            if proc.is_alive():
                continue
            proc.join()
            del running[sentinel]
            cid = rec["code_id"]
            if proc.exitcode == 0:
                state = "finished" if (out / cid / RESULT_FILE).exists() else "stopped at the deadline"
                print(f"{state}: {cid}", flush=True)
            elif proc.exitcode == EXIT_STALE and cid not in restarted:
                shards = _shard_tables(out / cid)
                stale.append(_move_stale(out, cid, shards[-1]["cpu_class"] if shards else None, "digest"))
                restarted.add(cid)
                pending.insert(0, rec)
                print(f"STALE, restarting from batch 0: {cid}", flush=True)
            else:
                died.append({"code_id": cid, "exitcode": proc.exitcode})
                print(f"DIED (exit code {proc.exitcode}): {cid}", flush=True)

    summary = _finish_session(out, config, manifest, population, session, started_at, deadline,
                              copied_from, started, died, stale, seconds_before,
                              kind="probe" if probe else "session", cost_gate=gate or None)
    if archive is not None:
        sha = _write_archive(out, archive, reason="session_end")
        summary = {**summary, "archive": {"file": ARCHIVE_FILE, "sha256": sha}}
        _write_json(archive / f"session_{session:03d}.json",  # small: the inventory stays in the tar
                    {k: v for k, v in summary.items() if k != "inventory"})
        print(f"archive {archive / ARCHIVE_FILE} sha256 {sha}", flush=True)
    return summary


def _finish_session(out, config, manifest, population, session, started_at, deadline,
                    copied_from, started, died, stale, seconds_before, *, kind, cost_gate) -> dict:
    """Classify every code, build the rows that can be built, write the summary."""
    deaths = Counter(d["code_id"] for s in _summaries(out) for d in s["died"])
    deaths.update(d["code_id"] for d in died)
    codes: dict[str, list] = {"done": [], "partial": [], "not_started": [], "failed": [], "row_errors": []}
    per_code = {}
    for rec in population:
        cid, d = rec["code_id"], out / rec["code_id"]
        shards = _shard_tables(d) if d.exists() else []
        if shards:
            shots, fails = shards[-1]["shots"], shards[-1]["failures"]
            per_code[cid] = {"shots": shots, "failures": fails, "failure_fraction": fails / shots,
                             "seconds_per_shot": sum(s["batch_decode_seconds"] for s in shards) / shots,
                             "finished": (d / RESULT_FILE).exists(), "n_d_upper": rec["n_d_upper"]}
        if (d / RESULT_FILE).exists():
            try:
                build_row(_code(rec), d, p=manifest["p"], batch_size=manifest["batch_size"],
                          max_shots=manifest["max_shots"])
                codes["done"].append(cid)
            except ValueError as exc:
                codes["row_errors"].append({"code_id": cid, "error": str(exc)})
        elif deaths[cid] >= 2:
            codes["failed"].append(cid)
        elif shards:
            codes["partial"].append(cid)
        else:
            codes["not_started"].append(cid)
    seconds = _decode_seconds(out)
    summary = {
        "format": FORMAT,
        "session": session,
        "kind": kind,
        "probe_codes": manifest["probe_codes"] if kind == "probe" else None,
        "cost_gate": cost_gate,
        "started_at": started_at,
        "ended_at": _utc(),
        "session_wall_hours": config.session_wall_hours,
        "deadline_passed": time.time() >= deadline,
        "previous": config.previous,
        "copied_from": None if copied_from is None else str(copied_from),
        "provenance": provenance.record(),
        "counts": {k: len(v) for k, v in codes.items()} | {"population": len(population)},
        "codes": codes,
        "started": started,
        "stale_restarted": stale,
        "died": died,
        "decode_core_hours": {"this_session": (seconds - seconds_before) / 3600.0,
                              "cumulative": seconds / 3600.0},
        "per_code": per_code,
    }
    summary["inventory"] = _files(out)  # before the summary itself is written
    _write_json(out / f"session_{session:03d}.json", summary)
    print(format_session(summary), flush=True)
    return summary


def format_session(summary: Mapping[str, Any]) -> str:
    """A session summary as text."""
    c, h = summary["counts"], summary["decode_core_hours"]
    lines = [f"session {summary['session']} ({summary['kind']}): {c['done']} done, {c['partial']} partial, "
             f"{c['not_started']} not started, {c['failed']} failed, {c['row_errors']} row errors, "
             f"of {c['population']}",
             f"stale-restarted {len(summary['stale_restarted'])}, died {len(summary['died'])}",
             f"decode core-hours: this session {h['this_session']:.2f}, cumulative {h['cumulative']:.2f}"]
    for d in summary["died"]:
        lines.append(f"  DIED {d['code_id']} exit code {d['exitcode']}")
    for s in summary["stale_restarted"]:
        lines.append(f"  STALE {s['code_id']} ({s['reason']}, cpu_class {s['cpu_class']}) -> {s['moved_to']}")
    for cid, r in sorted(summary["per_code"].items(), key=lambda kv: -kv[1]["n_d_upper"]):
        lines.append(f"  {cid}: {r['shots']} shots, failure fraction {r['failure_fraction']:.4f}, "
                     f"{r['seconds_per_shot']:.3f} s/shot{'' if r['finished'] else ' (partial)'}")
    return "\n".join(lines)


# --- final assembly -----------------------------------------------------------


def assemble_measurements(pilot_dir: str | os.PathLike[str], data_dir: str | os.PathLike[str]) -> Path:
    """Build every row and write ``<data_dir>/m0_measurements.parquet``; return its path.

    ``pilot_dir`` is a pilot directory or an ``m0-pilot.tar`` (checked against
    its sidecar's sha256, and against its inventory once extracted).
    ``data_dir`` must be a directory named ``data`` (architecture §2), and the
    file must not exist yet. Refuses while any code is unfinished, if the
    population is not the pinned M0 population, if the rows do not share one
    protocol hash (INV-6) equal to the manifest's, or if there are not
    ``POPULATION_SIZE`` of them.
    """
    data = Path(data_dir)
    if data.name != "data":
        raise PilotRefusal(f"measurements go under data/ (architecture §2), not {data}")
    target = data / MEASUREMENTS_FILE
    if target.exists():
        raise PilotRefusal(f"{target} exists; assembly does not overwrite the measurements")
    with _opened(pilot_dir) as pilot:
        return _assemble(pilot, data, target)


def _assemble(pilot: Path, data: Path, target: Path) -> Path:
    reject_calibration(pilot)
    manifest = json.loads((pilot / MANIFEST_FILE).read_text(encoding="utf-8"))
    population = _read_population(pilot)
    if (population_digest(population) != manifest["population_sha256"]
            or manifest["population_sha256"] != POPULATION_SHA256 or len(population) != POPULATION_SIZE):
        raise PilotRefusal("the pilot's population is not the pinned M0 population")
    if (manifest["batch_size"], manifest["max_shots"], manifest["p"]) != (SHOT_BATCH, MAX_SHOTS, P_PILOT):
        raise PilotRefusal("the pilot did not run at CONTRACT's SHOT_BATCH, MAX_SHOTS and P_PILOT")
    unfinished = [r["code_id"] for r in population if not (pilot / r["code_id"] / RESULT_FILE).exists()]
    if unfinished:
        raise PilotRefusal(f"{len(unfinished)} codes are unfinished, e.g. {unfinished[:5]}")
    rows = [build_row(_code(r), pilot / r["code_id"], p=manifest["p"], batch_size=manifest["batch_size"],
                      max_shots=manifest["max_shots"]) for r in population]
    table = rows_table(rows)
    h = assert_single_protocol(table.to_pandas()["protocol_hash"])
    if h != manifest["protocol_hash"] or table.num_rows != POPULATION_SIZE:
        raise PilotRefusal(f"{table.num_rows} rows under {h}; expected {POPULATION_SIZE} under the manifest's")
    data.mkdir(exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, target)
    return target


# --- the probe's cost report --------------------------------------------------


def pilot_cost_report(pilot_dir: str | os.PathLike[str], calibration_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """The probe's measured cost and failure fractions, against the D-029 projection.

    Run locally, on the probe session's downloaded ``m0-pilot.tar`` (or an
    extracted pilot directory), before any later session is approved
    (``cost_gate``). Decodes nothing and enumerates
    nothing: the population comes from ``population.parquet``. The projection
    is ``calibrate._project_pilot`` over the calibration's completed BP+OSD
    cells at ``P_PILOT``, with ``MAX_SHOTS`` and ``SHOT_BATCH``: seconds/shot a
    power law in ``n * d_upper``, and the failure fraction borrowed from the
    calibration code nearest in ``d_upper`` (the donor).

    It reports, and recommends nothing:

    - per probe code, measured vs projected BP+OSD seconds/shot (their ratio),
      and measured vs donor failure fraction;
    - total core-hours re-projected: a finished probe code at its measured
      decode seconds; a partial one at its measured seconds/shot times the
      model's run shots (at least the shots it has done); every other code at
      its projected core-hours times the median ratio, and again times the
      maximum ratio. Both against architecture §6's 52.5 core-hours and its
      158 core-hour ceiling;
    - censoring projected at ``MAX_SHOTS``, overall and in the top third by
      ``d_upper`` (probe codes by their own measurements, others by their
      donors), and among the probe codes with the lowest measured failure
      fractions, all of them listed in order.
    """
    with _opened(pilot_dir) as pilot:
        return _cost_report(pilot, Path(calibration_dir))


def _cost_report(pilot: Path, cal: Path) -> dict[str, Any]:
    import math
    import statistics

    from qecscreen.evaluate import calibrate  # scipy.stats and ldpc's LSD: not for workers

    manifest = json.loads((pilot / MANIFEST_FILE).read_text(encoding="utf-8"))
    if "probe_codes" not in manifest or not any(s.get("kind") == "probe" for s in _summaries(pilot)):
        raise PilotRefusal(f"{pilot} holds no probe session")
    population = _read_population(pilot)
    plan = json.loads((cal / "plan.json").read_text(encoding="utf-8"))
    cells = [c for c in calibrate._load_cells(cal, plan) if c["status"] == "completed" and c["p"] == P_PILOT]
    proj = calibrate._project_pilot(cells, population, "bposd", max_shots=MAX_SHOTS,
                                    shot_batch=SHOT_BATCH, per_code=True)
    if proj is None:
        raise PilotRefusal(f"{cal} has no completed cells at P_PILOT={P_PILOT}")
    model = {m["code_id"]: m for m in proj["per_code"]}
    by_id = {r["code_id"]: r for r in population}

    probe = []
    for cid in manifest["probe_codes"]:
        rec, m, d = by_id[cid], model[cid], pilot / cid
        shards = _shard_tables(d) if d.is_dir() else []
        finished = (d / RESULT_FILE).exists()
        shots = shards[-1]["shots"] if shards else 0
        fails = shards[-1]["failures"] if shards else 0
        seconds = sum(s["batch_decode_seconds"] for s in shards)
        measured = seconds / shots if shots else None
        if finished:
            censored = fails < MIN_FAILURES
        elif shots:
            censored = calibrate._shots_needed(shots, fails, MAX_SHOTS)["exceeds_max_shots"]
        else:
            censored = None
        probe.append({
            "code_id": cid, "n": rec["n"], "k": rec["k"], "d_upper": rec["d_upper"],
            "n_d_upper": rec["n_d_upper"], "shots": shots, "failures": fails, "finished": finished,
            "measured_decode_seconds": seconds, "measured_seconds_per_shot": measured,
            "projected_seconds_per_shot": m["seconds_per_shot"],
            "ratio": None if measured is None else measured / m["seconds_per_shot"],
            "measured_failure_fraction": fails / shots if shots else None,
            "donor": m["donor"], "donor_failure_fraction": m["donor_failure_fraction"],
            "censored_at_max_shots": censored,
        })
    measured_probe = {e["code_id"]: e for e in probe if e["shots"]}
    ratios = [e["ratio"] for e in measured_probe.values()]

    def reproject(factor: float | None) -> float | None:
        if factor is None:
            return None
        seconds = 0.0
        for rec in population:
            e = measured_probe.get(rec["code_id"])
            if e is None:
                seconds += model[rec["code_id"]]["core_hours"] * 3600.0 * factor
            elif e["finished"]:
                seconds += e["measured_decode_seconds"]
            else:
                seconds += e["measured_seconds_per_shot"] * max(model[rec["code_id"]]["run_shots"], e["shots"])
        return seconds / 3600.0

    median = statistics.median(ratios) if ratios else None
    worst = max(ratios) if ratios else None
    at_median, at_max = reproject(median), reproject(worst)

    def censoring(codes: Sequence[str]) -> dict[str, int]:
        status = [measured_probe[c]["censored_at_max_shots"] if c in measured_probe
                  else model[c]["shots_to_min_failures"]["exceeds_max_shots"] for c in codes]
        return {"codes": len(codes), "projected_censored": sum(s is True for s in status),
                "unknown": sum(s is None for s in status)}

    top = sorted(population, key=lambda r: (-r["d_upper"], -r["n"], r["code_id"]))
    top = [r["code_id"] for r in top[: math.ceil(len(top) / 3)]]
    lowest = sorted(measured_probe.values(), key=lambda e: (e["measured_failure_fraction"], e["code_id"]))
    lowest_third = [e["code_id"] for e in lowest[: math.ceil(len(lowest) / 3)]]
    return {
        "format": "qecscreen_m0_pilot_cost_report_v1",
        "pilot": {k: manifest[k] for k in ("protocol_hash", "commit_sha", "probe_codes")},
        "calibration_dir": str(cal),
        "constants": {"P_PILOT": P_PILOT, "MAX_SHOTS": MAX_SHOTS, "SHOT_BATCH": SHOT_BATCH,
                      "MIN_FAILURES": MIN_FAILURES},
        "model": {"seconds_per_shot": proj["seconds_per_shot_model"],
                  "failure_fraction": proj["failure_fraction_model"]},
        "probe": probe,
        "ratio": {"codes": len(ratios), "median": median, "max": worst,
                  "min": min(ratios) if ratios else None},
        "core_hours": {
            "projected": proj["core_hours"],
            "reprojected_at_median_ratio": at_median,
            "reprojected_at_max_ratio": at_max,
            "architecture_projection": PROJECTED_CORE_HOURS,
            "architecture_ceiling": CEILING_CORE_HOURS,
            "median_case_over_projection": None if at_median is None else at_median / PROJECTED_CORE_HOURS,
            "max_case_over_ceiling": None if at_max is None else at_max / CEILING_CORE_HOURS,
        },
        "censoring": {
            "overall": censoring([r["code_id"] for r in population]),
            "top_third_by_d_upper": censoring(top) | {"d_upper_min": min(by_id[c]["d_upper"] for c in top)},
            "model_only": {"overall": proj["censored_overall"], "top_third_by_d_upper": proj["top_third_by_d_upper"]},
            "probe_by_measured_failure_fraction": [
                {k: e[k] for k in ("code_id", "d_upper", "shots", "failures", "measured_failure_fraction",
                                   "finished", "censored_at_max_shots")} for e in lowest],
            "lowest_third_of_probe": censoring(lowest_third),
        },
    }


def format_cost_report(report: Mapping[str, Any]) -> str:
    """A cost report as text. Measurements and projections only."""
    def f(x: float | None, spec: str = ".3g") -> str:
        return "-" if x is None else format(x, spec)

    ch, r, c = report["core_hours"], report["ratio"], report["censoring"]
    lines = ["probe codes (measured vs projected BP+OSD s/shot; measured vs donor failure fraction):"]
    for e in report["probe"]:
        lines.append(
            f"  {e['code_id']} [[{e['n']},{e['k']},<={e['d_upper']}]] {e['shots']} shots"
            f"{'' if e['finished'] else ' (partial)'}: s/shot {f(e['measured_seconds_per_shot'])} vs "
            f"{f(e['projected_seconds_per_shot'])} (x{f(e['ratio'])}); failure fraction "
            f"{f(e['measured_failure_fraction'])} vs {f(e['donor_failure_fraction'])} ({e['donor']})")
    lines += [
        f"ratio measured/projected over {r['codes']} codes: median {f(r['median'])}, max {f(r['max'])}, "
        f"min {f(r['min'])}",
        f"core-hours: projected {f(ch['projected'], '.1f')}; re-projected at the median ratio "
        f"{f(ch['reprojected_at_median_ratio'], '.1f')} (architecture §6: {ch['architecture_projection']}), "
        f"at the max ratio {f(ch['reprojected_at_max_ratio'], '.1f')} (ceiling {ch['architecture_ceiling']})",
        f"censored at MAX_SHOTS: overall {c['overall']['projected_censored']}/{c['overall']['codes']} "
        f"(+{c['overall']['unknown']} unknown); top third by d_upper "
        f"{c['top_third_by_d_upper']['projected_censored']}/{c['top_third_by_d_upper']['codes']} "
        f"(+{c['top_third_by_d_upper']['unknown']}); lowest-failure-fraction third of the probe "
        f"{c['lowest_third_of_probe']['projected_censored']}/{c['lowest_third_of_probe']['codes']} "
        f"(+{c['lowest_third_of_probe']['unknown']})",
    ]
    return "\n".join(lines)
