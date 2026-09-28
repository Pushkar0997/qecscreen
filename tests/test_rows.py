"""M0-RUN-01: the measurement-row writer (D-009, D-017, D-027, D-032).

Most checkpoints here are synthetic: shards and a result written directly with
chosen counts, so a row can be built at 99 or 100 failures without decoding
anything. One is a real ``sample_and_decode`` run on the [[12,2,3]] code.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import qecscreen.evaluate.rows as rows_mod
import qecscreen.provenance as prov_mod
from qecscreen.circuits.build import build_memory_circuit
from qecscreen.codes import ids
from qecscreen.codes.bb import generate
from qecscreen.evaluate.checkpoint import (
    BatchRecord,
    CodeCheckpoint,
    ProvenanceMismatchError,
)
from qecscreen.evaluate.rows import (
    MEASUREMENT_COLUMNS,
    MEASUREMENT_SCHEMA,
    CalibrationOutputError,
    RowBuildError,
    build_row,
    rows_table,
)
from qecscreen.evaluate.run import sample_and_decode
from qecscreen.protocol import (
    MIN_FAILURES,
    P_PILOT,
    Protocol,
    installed_decoder_version,
    logical_error_rate,
    protocol_hash,
    sampling_seed,
    wilson_interval,
)

ROOT = Path(__file__).resolve().parents[1]
# [[12,2,3]], the pair_2_2 template at l=2, m=3; in the M0 population.
CODE = {"construction_program_id": "bb_v1_pair_2_2", "l": 2, "m": 3,
        "a_exps": [[1, 0], [0, 2]], "b_exps": [[0, 1], [2, 0]]}
CODE_ID = ids.code_id(CODE["construction_program_id"],
                      ids.params_json(CODE["l"], CODE["m"], CODE["a_exps"], CODE["b_exps"]))
BATCH, MAX = 64, 512
PROV_A = {"commit_sha": "a" * 40, "stim_version": "1.16.0", "cpu_class": "x86_64/sse2"}
PROV_B = {"commit_sha": "b" * 40, "stim_version": "1.15.0", "cpu_class": "x86_64/avx2"}


def _seed() -> int:
    return sampling_seed(CODE_ID, protocol_hash(Protocol(p=P_PILOT, decoder_version=installed_decoder_version())))


def _patch_provenance(monkeypatch, prov):
    monkeypatch.setattr(prov_mod, "resolved_commit", lambda: prov["commit_sha"])
    monkeypatch.setattr(prov_mod, "stim_version", lambda: prov["stim_version"])
    monkeypatch.setattr(prov_mod, "cpu_class", lambda: prov["cpu_class"])


def write_checkpoint(directory, batch_failures, provenances=None, *, finish=True, seed=None):
    """A synthetic checkpoint: one shard per entry of ``batch_failures``.

    ``provenances`` gives each shard's provenance (default: PROV_A on all).
    """
    seed = _seed() if seed is None else seed
    shots = failures = 0
    for i, f in enumerate(batch_failures):
        prov = (provenances or [PROV_A] * len(batch_failures))[i]
        ck = CodeCheckpoint(directory, seed=seed, batch_size=BATCH, max_shots=MAX, provenance=prov)
        shots += BATCH
        failures += f
        ck.write_batch(BatchRecord(
            batch_index=i, batch_shots=BATCH, batch_failures=f, batch_osd_invocations=0,
            batch_decode_seconds=0.25, batch_samples_sha256=f"{i:064x}", shots=shots,
            failures=failures, samples_sha256=f"{i + 1:064x}"))
    if finish:
        CodeCheckpoint(directory, seed=seed, batch_size=BATCH, max_shots=MAX).write_result({
            "seed": seed, "batch_size": BATCH, "shots": shots, "failures": failures,
            "stopped_by": "min_failures" if failures >= MIN_FAILURES else "max_shots",
            "osd_invocations": 0, "samples_sha256": f"{len(batch_failures):064x}",
            "decode_seconds": 0.25 * len(batch_failures)})
    return Path(directory)


def _build(directory, **kw):
    return build_row(CODE, directory, batch_size=BATCH, max_shots=MAX, **kw)


# --- a real run -----------------------------------------------------------------


def test_a_row_from_a_real_checkpointed_run(tmp_path, monkeypatch):
    _patch_provenance(monkeypatch, PROV_A)
    circuit = build_memory_circuit(CODE, P_PILOT, 3)
    result = sample_and_decode(circuit, seed=_seed(), batch_size=BATCH, max_shots=MAX,
                               checkpoint_dir=tmp_path / CODE_ID)
    row = _build(tmp_path / CODE_ID)
    assert tuple(row) == MEASUREMENT_COLUMNS
    assert row["code_id"] == CODE_ID and row["sampling_seed"] == _seed()
    assert (row["shots"], row["failures"]) == (result.shots, result.failures)
    assert (row["n"], row["k"], row["d_upper"], row["rounds"]) == (12, 2, 3, 3)
    assert row["n_ancilla"] == 12 and row["n_total"] == 24
    assert {k: row[k] for k in PROV_A} == PROV_A
    assert row["family"] == "BB" and row["d_exact"] is None and row["seed"] == 0
    assert math.isclose(row["phi_from_d_upper"], 2 * 9 / 12, rel_tol=1e-15)
    assert row["p"] == P_PILOT and row["schema_version"] == 1
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00", row["created_at"])


def test_a_resume_by_another_provenance_is_refused(tmp_path, monkeypatch):
    """D-032: a resuming process with another commit or CPU class never continues."""
    circuit = build_memory_circuit(CODE, P_PILOT, 3)
    write_checkpoint(tmp_path, [0], finish=False)  # one shard, written under PROV_A
    for field in ("commit_sha", "stim_version", "cpu_class"):
        _patch_provenance(monkeypatch, {**PROV_A, field: PROV_B[field]})
        with pytest.raises(ProvenanceMismatchError) as err:
            sample_and_decode(circuit, seed=_seed(), batch_size=BATCH, max_shots=MAX,
                              checkpoint_dir=tmp_path)
        assert err.value.field == field


# --- refusals -------------------------------------------------------------------


def test_calibration_input_is_rejected(tmp_path):
    d = write_checkpoint(tmp_path / "c", [60, 60])
    with pytest.raises(CalibrationOutputError):
        build_row({**CODE, "calibration": True}, d, batch_size=BATCH, max_shots=MAX)
    (d / "cell.json").write_text(json.dumps({"calibration": True}), encoding="utf-8")
    with pytest.raises(CalibrationOutputError):
        _build(d)
    (d / "cell.json").unlink()
    pq.write_table(pa.table({"calibration": [True]}), d / "stray.parquet")
    with pytest.raises(CalibrationOutputError):
        _build(d)
    with pytest.raises(CalibrationOutputError):
        rows_table([{**_build(write_checkpoint(tmp_path / "ok", [60, 60])), "calibration": True}])


@pytest.mark.parametrize("commit", [None, "", "unset", "0" * 40, "abc123", "A" * 40])
def test_a_missing_or_placeholder_commit_sha_is_refused(tmp_path, commit):
    d = write_checkpoint(tmp_path, [60, 60], [{**PROV_A, "commit_sha": commit}] * 2)
    with pytest.raises(RowBuildError, match="commit_sha"):
        _build(d)


def test_an_unfinished_code_is_refused(tmp_path):
    with pytest.raises(RowBuildError, match="not finished"):
        _build(write_checkpoint(tmp_path, [10, 10], finish=False))


def test_a_checkpoint_under_another_decoder_version_is_refused(tmp_path, monkeypatch):
    """The hash carries the installed ldpc version: a row built where another is
    installed than the one that decoded it would carry the wrong hash and seed."""
    d = write_checkpoint(tmp_path, [60, 60])
    monkeypatch.setattr(rows_mod, "installed_decoder_version", lambda: "9.9.9")
    with pytest.raises(RowBuildError, match="belongs to the run"):
        _build(d)


def test_a_code_record_that_disagrees_with_its_parameters_is_refused(tmp_path):
    d = write_checkpoint(tmp_path, [60, 60])
    with pytest.raises(RowBuildError, match="d_upper"):
        build_row({**CODE, "d_upper": 4}, d, batch_size=BATCH, max_shots=MAX)


# --- provenance -----------------------------------------------------------------


def test_every_provenance_column_is_present_and_non_null(tmp_path):
    row = _build(write_checkpoint(tmp_path, [60, 60]))
    for col in ("commit_sha", "stim_version", "cpu_class", "sampling_seed", "protocol_hash"):
        assert row[col] not in (None, ""), col
    table = rows_table([row])
    for col in ("commit_sha", "stim_version", "cpu_class", "sampling_seed", "protocol_hash"):
        assert table.column(col).null_count == 0


def test_provenance_is_read_from_the_shards_not_the_building_process(tmp_path, monkeypatch):
    d = write_checkpoint(tmp_path, [60, 60])  # PROV_A
    _patch_provenance(monkeypatch, PROV_B)
    row = _build(d)
    assert {k: row[k] for k in PROV_A} == PROV_A


@pytest.mark.parametrize("field", ["commit_sha", "stim_version", "cpu_class"])
def test_shards_with_mixed_provenance_are_refused(tmp_path, field):
    d = write_checkpoint(tmp_path, [30, 30, 50], [PROV_A, {**PROV_A, field: PROV_B[field]}, PROV_A])
    with pytest.raises(RowBuildError, match=field):
        _build(d)


# --- invariants on built rows ---------------------------------------------------


def _architecture_columns() -> list[str]:
    text = (ROOT / "spec" / "architecture.md").read_text(encoding="utf-8")
    section = text.split("## 3. Data model", 1)[1].split("## 4.", 1)[0]
    cols = []
    for line in section.splitlines():
        m = re.match(r"\| (`[^|]+`) \|", line)
        if m:
            cols += re.findall(r"`([^`]+)`", m.group(1))
    return cols


def test_inv1_columns_are_exactly_architecture_s3_and_none_is_a_prediction(tmp_path):
    assert list(MEASUREMENT_COLUMNS) == _architecture_columns()
    row = _build(write_checkpoint(tmp_path, [60, 60]))
    assert not [c for c in row if c.startswith("pred_")]
    assert {c for c in row if c.startswith("true_")} == {
        "true_ler", "true_ler_ub", "true_ler_ci_low", "true_ler_ci_high"}


@pytest.mark.parametrize("failures", [99, 100])
def test_inv3_at_99_and_100_failures(tmp_path, failures):
    # 100 stops at MIN_FAILURES after 2 batches; 99 runs on to MAX with no more.
    batches = [50, 50] if failures == 100 else [50, 49] + [0] * (MAX // BATCH - 2)
    row = _build(write_checkpoint(tmp_path, batches))
    r, k, shots = 3, 2, len(batches) * BATCH
    lo, hi = wilson_interval(failures, shots)
    assert row["failures"] == failures and row["shots"] == shots
    if failures < MIN_FAILURES:
        assert row["censored"] is True and row["true_ler"] is None
    else:
        assert row["censored"] is False
        assert math.isclose(row["true_ler"], logical_error_rate(failures / shots, r, k), rel_tol=1e-12)
    assert math.isclose(row["true_ler_ci_low"], logical_error_rate(lo, r, k), rel_tol=1e-12)
    assert math.isclose(row["true_ler_ci_high"], logical_error_rate(hi, r, k), rel_tol=1e-12)
    assert row["true_ler_ub"] == row["true_ler_ci_high"]
    table = rows_table([row])
    assert table.schema.equals(MEASUREMENT_SCHEMA)
    for col in ("true_ler", "true_ler_ub", "true_ler_ci_low", "true_ler_ci_high", "p", "decode_seconds"):
        assert table.schema.field(col).type == pa.float64()


def test_inv7_regenerate_roundtrip_on_built_rows(tmp_path):
    row = _build(write_checkpoint(tmp_path, [60, 60]))
    h_x, h_z = ids.regenerate(row)
    want = generate(2, 3, [(1, 0), (0, 2)], [(0, 1), (2, 0)], seed=0)
    assert h_x.dtype == np.uint8 and np.array_equal(h_x, want[0]) and np.array_equal(h_z, want[1])
    with pytest.raises(ValueError, match="does not match"):
        ids.regenerate({**row, "params_json": row["params_json"].replace('"l":2', '"l":3')})


def test_code_ids_are_the_calibrations():
    """One formula: the committed calibration's code_ids are what codes.ids gives."""
    plan = json.loads((ROOT / "evidence/calibration/2026-09-27-7e91f82/plan.json").read_text(encoding="utf-8"))
    for c in plan["codes"]:
        pj = ids.params_json(c["l"], c["m"], c["a_exps"], c["b_exps"])
        assert ids.code_id(c["construction_program_id"], pj) == c["code_id"]
