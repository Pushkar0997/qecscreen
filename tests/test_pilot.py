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
import math
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


GATE = "evals §7 2026-09-28 — probe cost report (test)"


def cfg(previous=None, *, wall=1.0, setup=None, processes=2, population=POP, gate="auto", probe_codes=12,
        archive=None, snapshot_minutes=pilot.SNAPSHOT_MINUTES):
    """``wall`` applies to the probe and to later sessions alike. ``gate`` defaults to
    GATE for a session with ``previous`` (a later session) and to none otherwise.
    ``archive`` is the stand-in for /kaggle/working, created here; None writes no tar."""
    if gate == "auto":
        gate = GATE if previous is not None else None
    if archive is not None:
        Path(archive).mkdir(parents=True, exist_ok=True)
    return PilotConfig(previous=None if previous is None else str(previous), cost_gate=gate,
                       session_wall_hours=wall, probe_wall_hours=wall, probe_codes=probe_codes,
                       processes=processes, archive_dir=None if archive is None else str(archive),
                       _population=population, _batch_size=BATCH, _max_shots=MAX,
                       _worker_setup=setup or functools.partial(fakes.fake_provenance, **SSE2),
                       _snapshot_minutes=snapshot_minutes)


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


def _pin_to_pop(monkeypatch):
    """Point assembly's pins at this three-code pilot."""
    monkeypatch.setattr(pilot, "POPULATION_SHA256", pilot.population_digest([pilot._record(c) for c in POP]))
    monkeypatch.setattr(pilot, "POPULATION_SIZE", 3)
    monkeypatch.setattr(pilot, "SHOT_BATCH", BATCH)
    monkeypatch.setattr(pilot, "MAX_SHOTS", MAX)


@pytest.mark.slow
def test_a_three_session_chain_equals_one_uninterrupted_run(tmp_path, monkeypatch):
    """Through tars, as on Kaggle: session i's pilot directory is scratch<i>/m0-pilot,
    its kept output is working<i> (the stand-in for /kaggle/working), and session
    i + 1's PREVIOUS is working<i>."""
    ref = reference_rows(tmp_path, monkeypatch)
    _parent(monkeypatch)

    def scratch(i):
        return tmp_path / f"scratch{i}" / "m0-pilot"

    def working(i):
        return tmp_path / f"working{i}"

    # Session 1 ends mid-code: two workers run one batch each, the third code never starts.
    s1 = run_session(cfg(wall=2.0 / 3600, setup=functools.partial(fakes.past_deadline, **SSE2),
                         archive=working(1)), scratch(1))
    assert s1["session"] == 1 and s1["deadline_passed"]
    assert sorted(s1["codes"]["partial"]) == sorted(IDS[:2]) and s1["codes"]["not_started"] == [IDS[2]]
    assert all(s1["per_code"][cid]["shots"] == BATCH for cid in IDS[:2])
    assert s1["started"] == IDS[:2]  # longest first

    s2 = run_session(cfg(working(1), archive=working(2)), scratch(2))
    assert s2["session"] == 2 and sorted(s2["codes"]["done"]) == sorted(IDS)
    assert s2["started"] == IDS
    assert s2["copied_from"] == str(working(1) / "m0-pilot.tar")

    before = {p: h for p, h in _files(scratch(2)).items() if p.startswith(tuple(IDS))}
    s3 = run_session(cfg(working(2), archive=working(3)), scratch(3))
    assert s3["session"] == 3 and s3["started"] == [] and sorted(s3["codes"]["done"]) == sorted(IDS)
    after = {p: h for p, h in _files(scratch(3)).items() if p.startswith(tuple(IDS))}
    assert after == before  # completed codes are carried through the tar and never touched
    assert s3["decode_core_hours"]["this_session"] == 0.0
    assert s3["decode_core_hours"]["cumulative"] == pytest.approx(s2["decode_core_hours"]["cumulative"])

    # The kept output: the tar, its sidecar and the small session summary, nothing else.
    for i, s in enumerate((s1, s2, s3), start=1):
        kept = sorted(p.name for p in working(i).rglob("*"))
        assert kept == ["m0-pilot.tar", "m0-pilot.tar.sha256", f"session_{i:03d}.json"] and len(kept) < 10
        assert s["archive"]["sha256"] == pilot._sha256(working(i) / "m0-pilot.tar")
        assert "inventory" not in json.loads((working(i) / f"session_{i:03d}.json").read_text())

    rows = pilot_rows(scratch(3))
    assert {c: without_timing(r) for c, r in rows.items()} == {c: without_timing(r) for c, r in ref.items()}

    # Final assembly from the downloaded tar.
    _pin_to_pop(monkeypatch)
    out = assemble_measurements(working(3) / "m0-pilot.tar", tmp_path / "data")
    assert out == tmp_path / "data" / "m0_measurements.parquet"
    table = pq.read_table(out).to_pylist()
    assert {r["code_id"]: without_timing(r) for r in table} == {c: without_timing(r) for c, r in ref.items()}
    with pytest.raises(PilotRefusal, match="does not overwrite"):
        assemble_measurements(working(3) / "m0-pilot.tar", tmp_path / "data")


@pytest.mark.slow
def test_a_snapshot_taken_mid_session_resumes_correctly(tmp_path, monkeypatch):
    """A session that dies leaves its last periodic snapshot; the next session resumes from it."""
    ref = reference_rows(tmp_path, monkeypatch)
    _parent(monkeypatch)
    run_session(cfg(wall=0.0, archive=tmp_path / "working1"), tmp_path / "scratch1" / "m0-pilot")

    real, crashed = pilot._write_archive, tmp_path / "crashed"

    def keep_first_mid_code_snapshot(pilot_dir, archive_dir, *, reason):
        sha = real(pilot_dir, archive_dir, reason=reason)
        if reason == "periodic" and not crashed.exists():
            with pilot.tarfile.open(archive_dir / "m0-pilot.tar") as tar:
                names = tar.getnames()
            if any(f"m0-pilot/{c}/batch_000000.parquet" in names and f"m0-pilot/{c}/{RESULT_FILE}" not in names
                   for c in IDS):
                crashed.mkdir()
                for name in ("m0-pilot.tar", "m0-pilot.tar.sha256"):
                    pilot.shutil.copy2(archive_dir / name, crashed / name)
        return sha

    monkeypatch.setattr(pilot, "_write_archive", keep_first_mid_code_snapshot)
    slow = functools.partial(fakes.slow_batches, seconds=0.3, **SSE2)
    run_session(cfg(tmp_path / "working1", setup=slow, archive=tmp_path / "working2",
                    snapshot_minutes=0.25 / 60), tmp_path / "scratch2" / "m0-pilot")
    monkeypatch.setattr(pilot, "_write_archive", real)
    assert crashed.exists(), "no periodic snapshot caught a code mid-way"

    # The session is resumed from its snapshot, which holds no session_002.json: it is session 2 again.
    s = run_session(cfg(crashed, archive=tmp_path / "working3"), tmp_path / "scratch3" / "m0-pilot")
    assert s["session"] == 2 and s["kind"] == "session" and s["stale_restarted"] == [] and s["died"] == []
    assert sorted(s["codes"]["done"]) == sorted(IDS)
    rows = pilot_rows(tmp_path / "scratch3" / "m0-pilot")
    assert {c: without_timing(r) for c, r in rows.items()} == {c: without_timing(r) for c, r in ref.items()}


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

    s = run_session(cfg(wall=1.0, gate=GATE), out)
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


def _first_archive(tmp_path, monkeypatch):
    """Session 1 with a tar in working1 (starts nothing: no workers, fast)."""
    _parent(monkeypatch)
    run_session(cfg(wall=0.0, archive=tmp_path / "working1"), tmp_path / "scratch1" / "m0-pilot")
    return tmp_path / "working1"


def test_a_corrupted_tar_is_refused(tmp_path, monkeypatch):
    working = _first_archive(tmp_path, monkeypatch)
    tar = working / "m0-pilot.tar"
    data = bytearray(tar.read_bytes())
    data[len(data) // 2] ^= 0xFF
    tar.write_bytes(bytes(data))
    with pytest.raises(PilotRefusal, match="sha256"):
        run_session(cfg(working, archive=tmp_path / "working2"), tmp_path / "scratch2" / "m0-pilot")
    assert not (tmp_path / "scratch2").exists()
    with pytest.raises(PilotRefusal, match="sha256"):
        assemble_measurements(tar, tmp_path / "data")
    (working / "m0-pilot.tar.sha256").unlink()
    with pytest.raises(PilotRefusal, match="no m0-pilot.tar.sha256"):
        run_session(cfg(working, archive=tmp_path / "working2"), tmp_path / "scratch2" / "m0-pilot")


def test_two_tars_or_none_are_refused(tmp_path, monkeypatch):
    working = _first_archive(tmp_path, monkeypatch)
    two = tmp_path / "two"
    for name in ("a", "b"):
        pilot.shutil.copytree(working, two / name)
    with pytest.raises(PilotRefusal, match="2 m0-pilot.tar files"):
        run_session(cfg(two, archive=tmp_path / "working2"), tmp_path / "scratch2" / "m0-pilot")
    (tmp_path / "none").mkdir()
    with pytest.raises(PilotRefusal, match="no m0-pilot.tar and 0 pilot directories"):
        run_session(cfg(tmp_path / "none", archive=tmp_path / "working2"), tmp_path / "scratch2" / "m0-pilot")
    assert not (tmp_path / "scratch2").exists()


def test_a_tar_is_checked_against_its_inventory(tmp_path, monkeypatch):
    """A tar whose sha256 matches its sidecar but whose contents disagree with its inventory."""
    working = _first_archive(tmp_path, monkeypatch)
    scratch = tmp_path / "scratch1" / "m0-pilot"
    (scratch / "population.parquet").write_bytes(b"not the population")
    with pilot.tarfile.open(working / "m0-pilot.tar", "w") as tar:  # re-tar, inventory.json unchanged
        for p in sorted(scratch.rglob("*")):
            tar.add(p, arcname=f"m0-pilot/{p.relative_to(scratch).as_posix()}", recursive=False)
    (working / "m0-pilot.tar.sha256").write_text(f"{pilot._sha256(working / 'm0-pilot.tar')}  m0-pilot.tar\n")
    with pytest.raises(PilotRefusal, match="truncated or altered"):
        run_session(cfg(working, archive=tmp_path / "working2"), tmp_path / "scratch2" / "m0-pilot")


def test_the_pilot_directory_may_not_live_in_the_archive_dir(tmp_path, monkeypatch):
    _parent(monkeypatch)
    with pytest.raises(PilotRefusal, match="at most 500 output files"):
        run_session(cfg(wall=0.0, archive=tmp_path / "working"), tmp_path / "working" / "m0-pilot")
    with pytest.raises(PilotRefusal, match="not a directory"):
        run_session(PilotConfig(archive_dir=str(tmp_path / "missing"), _population=POP), tmp_path / "pilot")
    assert not (tmp_path / "working" / "m0-pilot").exists()


def test_a_probe_that_died_before_its_summary_is_resumed_as_the_probe(tmp_path, monkeypatch):
    out = _first_session(tmp_path, monkeypatch)
    (out / "session_001.json").unlink()  # its last snapshot was taken before the summary
    with pytest.raises(PilotRefusal, match="forget PREVIOUS"):
        run_session(cfg(wall=0.0, gate=GATE), out)
    s = run_session(cfg(wall=0.0, gate=None), out)
    assert (s["session"], s["kind"]) == (1, "probe")


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

    s2 = run_session(cfg(wall=1.0, gate=GATE), out)  # the same session continuing: PREVIOUS unset
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
    probe = pilot.probe_codes(pop)
    by_id = {r["code_id"]: r for r in pop}
    assert len(set(probe)) == 12 and by_id[probe[0]]["n_d_upper"] == max(r["n_d_upper"] for r in pop)


# --- the probe and the cost gate ----------------------------------------------------


def test_probe_codes_are_evenly_spaced_ranks_including_the_largest():
    pop = [{"code_id": f"c{i:03d}", "n_d_upper": 1000 - i} for i in range(244)]
    probe = pilot.probe_codes(pop, 12)
    ranks = [int(c[1:]) for c in probe]  # rank i is code c{i}: sorted by n_d_upper descending
    assert ranks[0] == 0 and ranks[-1] == 243 and len(set(ranks)) == 12
    assert all(21 <= b - a <= 23 for a, b in zip(ranks, ranks[1:]))
    assert pilot.probe_codes(pop[:5], 12) == [f"c{i:03d}" for i in range(5)]  # all, when fewer
    assert pilot.probe_codes(pop, 1) == ["c000"]


def test_session_1_is_the_probe_and_every_later_session_needs_a_cost_gate(tmp_path, monkeypatch):
    _parent(monkeypatch)
    out = tmp_path / "pilot"
    s1 = run_session(cfg(wall=0.0, probe_codes=2), out)
    assert s1["kind"] == "probe" and s1["probe_codes"] == [IDS[0], IDS[2]]  # largest and smallest
    assert json.loads((out / "manifest.json").read_text())["probe_codes"] == [IDS[0], IDS[2]]
    for gate in (None, "", "   "):
        with pytest.raises(PilotRefusal, match="COST_GATE"):
            run_session(cfg(wall=0.0, gate=gate), out)
    assert len(list(out.glob("session_*.json"))) == 1
    s2 = run_session(cfg(wall=0.0, gate=GATE), out)
    assert s2["kind"] == "session" and s2["cost_gate"] == GATE and s2["probe_codes"] is None
    gates = json.loads((out / "manifest.json").read_text())["cost_gates"]
    assert [(g["session"], g["cost_gate"]) for g in gates] == [(2, GATE)]
    with pytest.raises(PilotRefusal, match="forget PREVIOUS"):
        run_session(cfg(wall=0.0, gate=GATE), tmp_path / "fresh" / "pilot")


@pytest.mark.slow
def test_the_probe_runs_only_its_codes_and_its_work_counts(tmp_path, monkeypatch):
    _parent(monkeypatch)
    s1 = run_session(cfg(wall=1.0, probe_codes=2), tmp_path / "k1" / "pilot")
    assert s1["started"] == [IDS[0], IDS[2]] and s1["codes"]["not_started"] == [IDS[1]]
    s2 = run_session(cfg(tmp_path / "k1"), tmp_path / "k2" / "pilot")
    assert s2["started"] == [IDS[1]] and sorted(s2["codes"]["done"]) == sorted(IDS)


# --- the notebook --------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]


def test_pilot_notebook_follows_the_template_and_carries_the_runbook():
    def cells(name):
        return json.loads((ROOT / "notebooks" / name).read_text(encoding="utf-8"))["cells"]

    nb, template = cells("pilot.ipynb"), cells("template_run.ipynb")
    assert [c["cell_type"] for c in nb] == ["markdown"] + ["code"] * 6
    code = ["".join(c["source"]) for c in nb[1:]]
    assert code[:2] == ["".join(c["source"]) for c in template[:2]]  # install by SHA, provenance read back
    assert all(c["outputs"] == [] and c["execution_count"] is None for c in nb[1:])
    assert "PREVIOUS = None" in code[2] and 'COST_GATE = ""' in code[2]
    assert "run_session(PilotConfig(previous=PREVIOUS, cost_gate=COST_GATE or None), OUT_DIR)" in code[4]
    runbook = "".join(nb[0]["source"])
    mirror = (ROOT / "spec" / "architecture.md").read_text(encoding="utf-8").split("### M0 pilot runbook", 1)[1]
    for text in ("Save & Run All", "PREVIOUS", "/kaggle/input", "COST_GATE", "pilot_cost_report",
                 "assemble_measurements", "QECSCREEN_SHA", "Add Input"):
        assert text in runbook and text in mirror, text


# --- the cost report, on synthetic shards --------------------------------------------

CALIBRATION = Path(__file__).resolve().parents[1] / "evidence" / "calibration" / "2026-09-27-7e91f82"
# (n, k, d_upper); ranks by n * d_upper: 648, 432, 384, 252, 96, 54, 36. The probe of 3 is ranks 0, 3, 6.
SYNTH = [(72, 8, 9), (72, 12, 6), (48, 4, 8), (42, 6, 6), (24, 4, 4), (18, 4, 3), (12, 2, 3)]


def _synthetic_pilot(tmp_path):
    from qecscreen.evaluate.checkpoint import BatchRecord, CodeCheckpoint

    out = tmp_path / "pilot"
    out.mkdir()
    pop = [{"code_id": f"bb_v1_synth-{i:012d}", "construction_program_id": "bb_v1_synth", "params_json": "{}",
            "n": n, "k": k, "d_upper": d, "n_d_upper": n * d} for i, (n, k, d) in enumerate(SYNTH)]
    pq.write_table(pilot.pa.Table.from_pylist(pop, schema=pilot._POPULATION_SCHEMA), out / "population.parquet")
    probe = pilot.probe_codes(pop, 3)
    (out / "manifest.json").write_text(json.dumps({"format": pilot.FORMAT, "protocol_hash": "a" * 64,
                                                   "commit_sha": "a" * 40, "probe_codes": probe}))
    (out / "session_001.json").write_text(json.dumps({"kind": "probe", "died": []}))
    plan = json.loads((CALIBRATION / "plan.json").read_text(encoding="utf-8"))
    cells = [c for c in pilot_calibrate()._load_cells(CALIBRATION, plan) if c["status"] == "completed" and c["p"] == P_PILOT]
    model = {m["code_id"]: m for m in pilot_calibrate()._project_pilot(cells, pop, "bposd", per_code=True)["per_code"]}

    def shards(cid, failures, factor, finish):
        ck = CodeCheckpoint(out / cid, seed=1, batch_size=256, max_shots=pilot.MAX_SHOTS,
                            provenance={"commit_sha": "a" * 40, "stim_version": "1.16.0", "cpu_class": "x86_64/sse2"})
        shots = fails = 0
        for i, f in enumerate(failures):
            shots, fails = shots + 256, fails + f
            ck.write_batch(BatchRecord(i, 256, f, 0, 256 * factor * model[cid]["seconds_per_shot"],
                                       f"{i:064x}", shots, fails, f"{i:064x}"))
        if finish:
            ck.write_result({"seed": 1, "batch_size": 256, "shots": shots, "failures": fails,
                             "stopped_by": "min_failures", "osd_invocations": 0, "samples_sha256": "0" * 64,
                             "decode_seconds": 0.0})

    shards(probe[0], [60, 45], 2.0, finish=True)  # finished at 105 failures, 2x the projected cost
    shards(probe[1], [1], 3.0, finish=False)  # partial, 1 failure in 256, 3x the projected cost
    return out, pop, probe, model  # probe[2] has not started


def pilot_calibrate():
    from qecscreen.evaluate import calibrate

    return calibrate


def test_the_cost_report_on_synthetic_shards(tmp_path, monkeypatch):
    out, pop, probe, model = _synthetic_pilot(tmp_path)
    monkeypatch.setattr(pilot, "admissible_codes", lambda *a: pytest.fail("the report enumerated"))
    monkeypatch.setattr(pilot, "sample_and_decode", lambda *a, **k: pytest.fail("the report decoded"))
    report = pilot.pilot_cost_report(out, CALIBRATION)

    fin, part, unstarted = report["probe"]
    assert [e["code_id"] for e in report["probe"]] == probe
    assert fin["ratio"] == pytest.approx(2.0) and part["ratio"] == pytest.approx(3.0) and unstarted["ratio"] is None
    assert fin["measured_failure_fraction"] == 105 / 512 and part["measured_failure_fraction"] == 1 / 256
    assert fin["donor_failure_fraction"] == model[probe[0]]["donor_failure_fraction"]
    assert report["ratio"] == {"codes": 2, "median": pytest.approx(2.5), "max": pytest.approx(3.0),
                               "min": pytest.approx(2.0)}

    others = sum(model[r["code_id"]]["core_hours"] for r in pop if r["code_id"] not in probe[:2])
    measured_fin = 512 * 2.0 * model[probe[0]]["seconds_per_shot"] / 3600
    measured_part = 3.0 * model[probe[1]]["seconds_per_shot"] * max(model[probe[1]]["run_shots"], 256) / 3600
    ch = report["core_hours"]
    assert ch["projected"] == pytest.approx(sum(m["core_hours"] for m in model.values()))
    assert ch["reprojected_at_median_ratio"] == pytest.approx(measured_fin + measured_part + 2.5 * others)
    assert ch["reprojected_at_max_ratio"] == pytest.approx(measured_fin + measured_part + 3.0 * others)
    assert (ch["architecture_projection"], ch["architecture_ceiling"]) == (52.5, 158.0)

    # 1 failure in 256 shots needs ~25,600 shots to reach 100: censored at MAX_SHOTS. 105 failures: not.
    assert (fin["censored_at_max_shots"], part["censored_at_max_shots"]) == (False, True)
    c = report["censoring"]
    assert [e["code_id"] for e in c["probe_by_measured_failure_fraction"]] == [probe[1], probe[0]]
    assert c["lowest_third_of_probe"] == {"codes": 1, "projected_censored": 1, "unknown": 0}
    model_status = [model[r["code_id"]]["shots_to_min_failures"]["exceeds_max_shots"] for r in pop
                    if r["code_id"] not in probe[:2]]
    assert c["overall"]["projected_censored"] == 1 + sum(s is True for s in model_status)
    assert c["top_third_by_d_upper"]["codes"] == 3 and c["top_third_by_d_upper"]["d_upper_min"] == 6  # d 9, 8, 6
    assert "x2" in pilot.format_cost_report(report)


def test_the_cost_report_reads_the_tar_as_it_reads_the_directory(tmp_path):
    out, *_ = _synthetic_pilot(tmp_path)
    (tmp_path / "working").mkdir()
    pilot._write_archive(out, tmp_path / "working", reason="session_end")
    from_dir = pilot.pilot_cost_report(out, CALIBRATION)
    assert pilot.pilot_cost_report(tmp_path / "working" / "m0-pilot.tar", CALIBRATION) == from_dir


def test_the_cost_report_needs_a_probe(tmp_path):
    out, *_ = _synthetic_pilot(tmp_path)
    (out / "session_001.json").write_text(json.dumps({"kind": "session", "died": []}))
    with pytest.raises(PilotRefusal, match="no probe session"):
        pilot.pilot_cost_report(out, CALIBRATION)


def test_project_pilot_per_code_is_the_power_law_and_sums_to_the_total():
    calibrate = pilot_calibrate()
    plan = json.loads((CALIBRATION / "plan.json").read_text(encoding="utf-8"))
    cells = [c for c in calibrate._load_cells(CALIBRATION, plan) if c["status"] == "completed" and c["p"] == P_PILOT]
    pop = [{"code_id": f"x{i}", "n": n, "d_upper": d} for i, (n, _, d) in enumerate(SYNTH)]
    proj = calibrate._project_pilot(cells, pop, "bposd", per_code=True)
    a, b = proj["seconds_per_shot_model"]["a"], proj["seconds_per_shot_model"]["b"]
    for code, m in zip(pop, proj["per_code"]):
        assert m["seconds_per_shot"] == pytest.approx(math.exp(a + b * math.log(code["n"] * code["d_upper"])))
    assert sum(m["core_hours"] for m in proj["per_code"]) == pytest.approx(proj["core_hours"])
    assert "per_code" not in calibrate._project_pilot(cells, pop, "bposd")  # summarize's output is unchanged
