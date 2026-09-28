"""M0-RUN-01: the pilot runner, chained across sessions (D-032, D-033).

Every session here runs real spawned workers on three [[12]] codes of the M0
population, with 64-shot batches and a 512-shot cap. The workers' provenance
is faked by a hook (``tests/_pilot_fakes.py``), because an editable install
has no commit for a row to carry. A session's "Kaggle input" is the previous
session's output directory; its pilot directory sits one level below, as on
Kaggle.

The tests that spawn workers take 5-30 s each and are marked ``slow``: CI runs
them on every leg; the default local run does not (AGENTS §5).
"""

from __future__ import annotations

import functools
import json
import multiprocessing
import time
from pathlib import Path

import pyarrow.parquet as pq
import pytest

import _pilot_fakes as fakes
import qecscreen.evaluate.pilot as pilot
import qecscreen.protocol as protocol_mod
import qecscreen.provenance as prov_mod
from qecscreen.circuits.build import build_memory_circuit
from qecscreen.codes import ids
from qecscreen.evaluate.checkpoint import RESULT_FILE
from qecscreen.evaluate.pilot import PilotConfig, PilotRefusal, assemble_measurements, run_session
from qecscreen.evaluate.rows import build_row
from qecscreen.evaluate.run import sample_and_decode
from qecscreen.protocol import P_PILOT, Protocol, installed_decoder_version, protocol_hash, sampling_seed

POP = (  # n * d_upper = 48, 36, 36: quad first, then pair and sq by code_id
    {"construction_program_id": "bb_v1_quad_4_2", "l": 2, "m": 3,
     "a_exps": [[1, 0], [0, 1], [2, 0], [0, 2]], "b_exps": [[1, 1], [2, 2]]},
    {"construction_program_id": "bb_v1_pair_2_2", "l": 2, "m": 3,
     "a_exps": [[1, 0], [0, 2]], "b_exps": [[0, 1], [2, 0]]},
    {"construction_program_id": "bb_v1_sq_4_2", "l": 3, "m": 2,
     "a_exps": [[0, 0], [1, 0], [0, 1], [1, 1]], "b_exps": [[2, 0], [0, 3]]},
)
IDS = [ids.code_id(c["construction_program_id"], ids.params_json(c["l"], c["m"], c["a_exps"], c["b_exps"]))
       for c in POP]
BATCH, MAX = 64, 512
TIMING = ("decode_seconds", "created_at")
SSE2 = {"commit": "a" * 40, "cpu": "x86_64/sse2"}
AVX2 = {"commit": "a" * 40, "cpu": "x86_64/avx2"}


def _parent(monkeypatch, commit="a" * 40, cpu="x86_64/sse2", stim="1.16.0"):
    monkeypatch.setattr(prov_mod, "resolved_commit", lambda: commit)
    monkeypatch.setattr(prov_mod, "cpu_class", lambda: cpu)
    monkeypatch.setattr(prov_mod, "stim_version", lambda: stim)


def cfg(previous=None, *, wall=1.0, setup=None, processes=2, population=POP):
    return PilotConfig(previous=None if previous is None else str(previous), session_wall_hours=wall,
                       processes=processes, _population=population, _batch_size=BATCH, _max_shots=MAX,
                       _worker_setup=setup or functools.partial(fakes.fake_provenance, **SSE2))


def _code(i):
    rec = pilot._record(POP[i])
    return pilot._code(rec)


def reference_rows(tmp_path, monkeypatch, cpu="x86_64/sse2"):
    """Each code run once, uninterrupted, in this process, then built into a row."""
    _parent(monkeypatch, cpu=cpu)
    h = protocol_hash(Protocol(p=P_PILOT, decoder_version=installed_decoder_version()))
    rows = {}
    for i, cid in enumerate(IDS):
        code = _code(i)
        d = tmp_path / "reference" / cid
        sample_and_decode(build_memory_circuit(code, P_PILOT, code["d_upper"]), seed=sampling_seed(cid, h),
                          batch_size=BATCH, max_shots=MAX, checkpoint_dir=d)
        rows[cid] = build_row(code, d, batch_size=BATCH, max_shots=MAX)
    return rows


def pilot_rows(pilot_dir):
    return {cid: build_row(_code(i), Path(pilot_dir) / cid, batch_size=BATCH, max_shots=MAX)
            for i, cid in enumerate(IDS)}


def without_timing(row):
    return {k: v for k, v in row.items() if k not in TIMING}


def _files(root):
    return pilot._files(Path(root))


# --- the chain ------------------------------------------------------------------


@pytest.mark.slow
def test_a_three_session_chain_equals_one_uninterrupted_run(tmp_path, monkeypatch):
    ref = reference_rows(tmp_path, monkeypatch)
    _parent(monkeypatch)

    # Session 1 ends mid-code: two workers run one batch each, the third code never starts.
    s1 = run_session(cfg(wall=2.0 / 3600, setup=functools.partial(fakes.past_deadline, **SSE2)),
                     tmp_path / "k1" / "pilot")
    assert s1["session"] == 1 and s1["deadline_passed"]
    assert sorted(s1["codes"]["partial"]) == sorted(IDS[:2]) and s1["codes"]["not_started"] == [IDS[2]]
    assert all(s1["per_code"][cid]["shots"] == BATCH for cid in IDS[:2])
    assert s1["started"] == IDS[:2]  # longest first

    s2 = run_session(cfg(tmp_path / "k1"), tmp_path / "k2" / "pilot")
    assert s2["session"] == 2 and sorted(s2["codes"]["done"]) == sorted(IDS)
    assert s2["started"] == IDS

    before = {p: h for p, h in _files(tmp_path / "k2" / "pilot").items() if p.startswith(tuple(IDS))}
    s3 = run_session(cfg(tmp_path / "k2"), tmp_path / "k3" / "pilot")
    assert s3["session"] == 3 and s3["started"] == [] and sorted(s3["codes"]["done"]) == sorted(IDS)
    after = {p: h for p, h in _files(tmp_path / "k3" / "pilot").items() if p.startswith(tuple(IDS))}
    assert after == before  # completed codes are copied and never touched
    assert s3["decode_core_hours"]["this_session"] == 0.0
    assert s3["decode_core_hours"]["cumulative"] == pytest.approx(s2["decode_core_hours"]["cumulative"])

    rows = pilot_rows(tmp_path / "k3" / "pilot")
    assert {c: without_timing(r) for c, r in rows.items()} == {c: without_timing(r) for c, r in ref.items()}

    # Final assembly, with the pins pointed at this three-code pilot.
    monkeypatch.setattr(pilot, "POPULATION_SHA256", pilot.population_digest([pilot._record(c) for c in POP]))
    monkeypatch.setattr(pilot, "POPULATION_SIZE", 3)
    monkeypatch.setattr(pilot, "SHOT_BATCH", BATCH)
    monkeypatch.setattr(pilot, "MAX_SHOTS", MAX)
    out = assemble_measurements(tmp_path / "k3" / "pilot", tmp_path / "data")
    assert out == tmp_path / "data" / "m0_measurements.parquet"
    table = pq.read_table(out).to_pylist()
    assert {r["code_id"]: without_timing(r) for r in table} == {c: without_timing(r) for c, r in ref.items()}
    with pytest.raises(PilotRefusal, match="does not overwrite"):
        assemble_measurements(tmp_path / "k3" / "pilot", tmp_path / "data")


@pytest.mark.slow
def test_a_terminated_worker_resumes_correctly(tmp_path, monkeypatch):
    ref = reference_rows(tmp_path, monkeypatch)
    _parent(monkeypatch)
    out = tmp_path / "k1" / "pilot"
    run_session(cfg(wall=0.0), out)  # writes the manifest, starts nothing
    rec = pilot._record(POP[1])
    job = {"code": pilot._code(rec), "p": P_PILOT, "batch_size": BATCH, "max_shots": MAX,
           "seed": sampling_seed(rec["code_id"], json.loads((out / "manifest.json").read_text())["protocol_hash"]),
           "dir": str(out / rec["code_id"]), "deadline": None,
           "setup": functools.partial(fakes.slow_batches, seconds=0.3, **SSE2)}
    proc = pilot._start_worker(multiprocessing.get_context("spawn"), job)
    shard = out / rec["code_id"] / "batch_000001.parquet"
    t_end = time.time() + 120
    while not shard.exists() and proc.is_alive() and time.time() < t_end:
        time.sleep(0.02)
    proc.terminate()
    proc.join()
    assert proc.exitcode != 0 and shard.exists()
    assert not (out / rec["code_id"] / RESULT_FILE).exists()  # killed mid-code

    s = run_session(cfg(wall=1.0), out)
    assert sorted(s["codes"]["done"]) == sorted(IDS) and s["died"] == []
    rows = pilot_rows(out)
    assert without_timing(rows[rec["code_id"]]) == without_timing(ref[rec["code_id"]])


# --- refusals at session start ---------------------------------------------------


def _first_session(tmp_path, monkeypatch):
    _parent(monkeypatch)
    out = tmp_path / "pilot"
    run_session(cfg(wall=0.0), out)
    return out


@pytest.mark.parametrize("change, field", [
    (lambda m: m.setattr(protocol_mod, "installed_decoder_version", lambda: "2.4.2"), "decoder_version"),
    (lambda m: m.setattr(prov_mod, "resolved_commit", lambda: "c" * 40), "commit_sha"),
    (lambda m: m.setattr(prov_mod, "stim_version", lambda: "1.15.0"), "stim_version"),
])
def test_a_manifest_mismatch_refuses_to_start(tmp_path, monkeypatch, change, field):
    out = _first_session(tmp_path, monkeypatch)
    manifest = (out / "manifest.json").read_text()
    change(monkeypatch)
    with pytest.raises(PilotRefusal, match=field):
        run_session(cfg(wall=1.0), out)
    assert (out / "manifest.json").read_text() == manifest
    assert len(list(out.glob("session_*.json"))) == 1  # the refused session wrote nothing


def test_a_population_mismatch_refuses_to_start(tmp_path, monkeypatch):
    out = _first_session(tmp_path, monkeypatch)
    with pytest.raises(PilotRefusal, match="population_sha256"):
        run_session(cfg(wall=1.0, population=POP[:2]), out)


def test_no_resolved_commit_refuses_to_start(tmp_path, monkeypatch):
    _parent(monkeypatch)
    monkeypatch.setattr(prov_mod, "resolved_commit", lambda: None)
    with pytest.raises(PilotRefusal, match="no resolved commit"):
        run_session(cfg(wall=0.0), tmp_path / "pilot")


def test_previous_with_zero_or_two_pilot_directories_is_refused(tmp_path, monkeypatch):
    out = _first_session(tmp_path, monkeypatch)
    (tmp_path / "empty").mkdir()
    with pytest.raises(PilotRefusal, match="0 pilot directories"):
        run_session(cfg(tmp_path / "empty"), tmp_path / "w" / "pilot")
    two = tmp_path / "two"
    for name in ("a", "b"):
        pilot.shutil.copytree(out, two / name / "pilot")
    with pytest.raises(PilotRefusal, match="2 pilot directories"):
        run_session(cfg(two), tmp_path / "w" / "pilot")
    assert not (tmp_path / "w").exists()


def test_a_copy_that_differs_from_its_source_is_refused(tmp_path, monkeypatch):
    out = _first_session(tmp_path, monkeypatch)
    real = pilot.shutil.copytree

    def lossy(src, dst, **kw):
        real(src, dst, **kw)
        (Path(dst) / "population.parquet").unlink()

    monkeypatch.setattr(pilot.shutil, "copytree", lossy)
    with pytest.raises(PilotRefusal, match="differs in 1 files"):
        run_session(cfg(out.parent), tmp_path / "w" / "pilot")

@pytest.mark.slow
def test_a_truncated_previous_output_is_refused(tmp_path, monkeypatch):
    _parent(monkeypatch)
    run_session(cfg(wall=1.0), tmp_path / "k1" / "pilot")
    (tmp_path / "k1" / "pilot" / IDS[0] / "batch_000003.parquet").unlink()
    with pytest.raises(PilotRefusal, match="truncated or altered"):
        run_session(cfg(tmp_path / "k1"), tmp_path / "k2" / "pilot")


def test_a_population_that_changed_fails_loudly(monkeypatch):
    real = pilot.admissible_codes
    monkeypatch.setattr(pilot, "admissible_codes", lambda budget: real(24)[:-1])
    with pytest.raises(PilotRefusal, match="Enumeration changed"):
        pilot.m0_population()


# --- stale partial codes, deaths --------------------------------------------------


@pytest.mark.slow
def test_a_cpu_class_mismatch_moves_the_partial_code_aside_and_restarts_it(tmp_path, monkeypatch):
    ref = reference_rows(tmp_path, monkeypatch)
    _parent(monkeypatch)
    run_session(cfg(wall=2.0 / 3600, setup=functools.partial(fakes.past_deadline, **SSE2)), tmp_path / "k1" / "pilot")
    k1 = _files(tmp_path / "k1" / "pilot")

    _parent(monkeypatch, cpu="x86_64/avx2")
    s2 = run_session(cfg(tmp_path / "k1", setup=functools.partial(fakes.fake_provenance, **AVX2)),
                     tmp_path / "k2" / "pilot")
    moved = {s["code_id"]: s for s in s2["stale_restarted"]}
    assert set(moved) == set(IDS[:2]) and {s["reason"] for s in moved.values()} == {"cpu_class"}
    for cid, s in moved.items():
        assert s["moved_to"].startswith(f"stale/{cid}-x86_64_sse2-")
        kept = {p.split("/", 2)[2]: h for p, h in _files(tmp_path / "k2" / "pilot").items()
                if p.startswith(s["moved_to"] + "/")}
        assert kept == {p.split("/", 1)[1]: h for p, h in k1.items() if p.startswith(cid + "/")}
    rows = pilot_rows(tmp_path / "k2" / "pilot")
    assert {r["cpu_class"] for r in rows.values()} == {"x86_64/avx2"}
    for cid in IDS:  # restarted from batch 0 on the same seed: the same counts
        assert (rows[cid]["shots"], rows[cid]["failures"]) == (ref[cid]["shots"], ref[cid]["failures"])


@pytest.mark.slow
def test_a_digest_mismatch_moves_the_partial_code_aside_and_restarts_it(tmp_path, monkeypatch):
    ref = reference_rows(tmp_path, monkeypatch)
    _parent(monkeypatch)
    out = tmp_path / "pilot"
    run_session(cfg(wall=2.0 / 3600, setup=functools.partial(fakes.past_deadline, **SSE2)), out)
    shard = out / IDS[0] / "batch_000000.parquet"
    table = pq.read_table(shard)
    idx = table.schema.get_field_index("batch_samples_sha256")
    pq.write_table(table.set_column(idx, "batch_samples_sha256", [["f" * 64]]), shard)

    s2 = run_session(cfg(wall=1.0), out)  # the same session continuing: PREVIOUS unset
    assert [(s["code_id"], s["reason"]) for s in s2["stale_restarted"]] == [(IDS[0], "digest")]
    assert sorted(s2["codes"]["done"]) == sorted(IDS) and s2["died"] == []
    assert without_timing(pilot_rows(out)[IDS[0]]) == without_timing(ref[IDS[0]])


@pytest.mark.slow
def test_a_worker_that_dies_twice_fails_its_code(tmp_path, monkeypatch):
    _parent(monkeypatch)
    dies = functools.partial(fakes.die_on, code_id=IDS[2], exitcode=7, **SSE2)
    s1 = run_session(cfg(wall=1.0, setup=dies), tmp_path / "k1" / "pilot")
    assert s1["died"] == [{"code_id": IDS[2], "exitcode": 7}] and sorted(s1["codes"]["done"]) == sorted(IDS[:2])
    assert s1["codes"]["failed"] == []
    s2 = run_session(cfg(tmp_path / "k1", setup=dies), tmp_path / "k2" / "pilot")
    assert s2["started"] == [IDS[2]]  # retried once, in the next session; done codes not re-run
    assert s2["died"] == [{"code_id": IDS[2], "exitcode": 7}] and s2["codes"]["failed"] == [IDS[2]]
    s3 = run_session(cfg(tmp_path / "k2"), tmp_path / "k3" / "pilot")
    assert s3["started"] == [] and s3["codes"]["failed"] == [IDS[2]]
    monkeypatch.setattr(pilot, "POPULATION_SHA256", pilot.population_digest([pilot._record(c) for c in POP]))
    monkeypatch.setattr(pilot, "POPULATION_SIZE", 3)
    monkeypatch.setattr(pilot, "SHOT_BATCH", BATCH)
    monkeypatch.setattr(pilot, "MAX_SHOTS", MAX)
    with pytest.raises(PilotRefusal, match="1 codes are unfinished"):
        assemble_measurements(tmp_path / "k3" / "pilot", tmp_path / "data")


@pytest.mark.slow
def test_assembly_refuses_outside_data_and_on_the_real_pins(tmp_path, monkeypatch):
    _parent(monkeypatch)
    run_session(cfg(wall=1.0), tmp_path / "pilot")
    with pytest.raises(PilotRefusal, match="under data/"):
        assemble_measurements(tmp_path / "pilot", tmp_path / "rows")
    with pytest.raises(PilotRefusal, match="not the pinned M0 population"):
        assemble_measurements(tmp_path / "pilot", tmp_path / "data")
    assert not (tmp_path / "data").exists()


# --- the pinned population --------------------------------------------------------


@pytest.mark.slow
def test_the_m0_population_is_the_pinned_244_and_the_d031_draw():
    """D-031: 244 codes, equal to sample_bb_params(244, 72, CALIBRATION_CODE_SEED)."""
    from qecscreen.codes.sample import sample_bb_params
    from qecscreen.evaluate.calibrate import CALIBRATION_CODE_SEED

    pop = pilot.m0_population()  # asserts the count and the pinned digest itself
    assert len(pop) == 244 and pilot.population_digest(pop) == pilot.POPULATION_SHA256
    drawn = sample_bb_params(244, 72, seed=CALIBRATION_CODE_SEED)
    assert {pilot._record(p)["code_id"] for p in drawn} == {r["code_id"] for r in pop}
    assert min(r["d_upper"] for r in pop) == 3 and max(r["n"] for r in pop) == 72
