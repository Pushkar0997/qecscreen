"""Decoder calibration (qecscreen.evaluate.calibrate) and the row guard (evaluate.rows).

The smoke configuration is one small code ([[12,2,3]], ``pair_2_2``), one p,
two decoders and 300 shots, well under a second per run. What it checks is the
design, not the numbers: every decoder decodes exactly the shots the seeded
sampler produced, a restart skips completed cells, every file carries the
calibration marker, and the row guard refuses all of it.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

import qecscreen.evaluate.calibrate as cal
from _calibration_fakes import hang_factory
from qecscreen.circuits.build import build_memory_circuit
from qecscreen.evaluate.calibrate import (
    DECODERS,
    CalibrationConfig,
    calibration_codes,
    mcnemar_exact,
    run_calibration,
    select_spanning,
    summarize,
)
from qecscreen.evaluate.label import make_label
from qecscreen.evaluate.rows import CalibrationOutputError, reject_calibration
from qecscreen.protocol import (
    DECODER_PARAMS,
    MAX_SHOTS,
    Protocol,
    installed_decoder_version,
    protocol_hash,
    sampling_seed,
)

SMALL = {
    "construction_program_id": "bb_v1_pair_2_2",
    "l": 2,
    "m": 3,
    "a_exps": [(1, 0), (0, 2)],
    "b_exps": [(0, 1), (2, 0)],
}
SMOKE = CalibrationConfig(
    ps=(0.003,),
    decoders=("bposd", "bplsd_cs_4"),
    reference_codes=False,
    n_sampled_codes=0,
    population_size=0,
    codes=(SMALL,),
    max_shots=300,
    sample_batch=100,
    processes=1,
)


def _counts(summary):
    return [(c["p"], c["code_id"], c["shots"], {d: r["failures"] for d, r in c["decoders"].items()},
             c["paired"]) for c in summary["per_cell"]]


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    out = tmp_path_factory.mktemp("smoke") / "calibration"
    summary = run_calibration(SMOKE, out)
    (cell_path,) = out.glob("cell_*.json")
    return out, summary, json.loads(cell_path.read_text(encoding="utf-8"))


def test_every_decoder_decoded_exactly_the_seeded_shots(smoke):
    _, _, cell = smoke
    code = cell["code"]
    h = protocol_hash(Protocol(p=0.003, decoder_version=installed_decoder_version()))
    seed = sampling_seed(code["code_id"], h)
    assert cell["sampling_seed"] == seed and cell["protocol_hash_pinned"] == h

    # Re-sample independently: same seed, same batch size, first `shots` rows.
    circuit = build_memory_circuit(code, 0.003, code["d_upper"])
    sampler = circuit.compile_detector_sampler(seed=seed)
    dets = np.vstack([sampler.sample(100, separate_observables=True)[0] for _ in range(3)])
    expected = hashlib.sha256()
    for row in dets.astype(np.uint8)[: cell["shots"]]:
        expected.update(row.tobytes())

    assert cell["shots"] == 300 and cell["stopped_by"] == "max_shots"
    digests = {d: r["syndromes_sha256"] for d, r in cell["decoders"].items()}
    assert set(digests.values()) == {expected.hexdigest()}, digests


def test_paired_counts_are_consistent(smoke):
    _, _, cell = smoke
    osd, lsd = cell["decoders"]["bposd"], cell["decoders"]["bplsd_cs_4"]
    pair = cell["paired"]["bplsd_cs_4_vs_bposd"]
    assert osd["failures"] > 0 and lsd["failures"] > 0  # not vacuous
    assert pair["only_bposd_fails"] + pair["both_fail"] == osd["failures"]
    assert pair["only_bplsd_cs_4_fails"] + pair["both_fail"] == lsd["failures"]
    assert sum(pair[k] for k in ("only_bposd_fails", "only_bplsd_cs_4_fails", "both_fail",
                                 "neither_fails")) == cell["shots"]
    assert pair["mcnemar_exact_p"] == mcnemar_exact(pair["only_bposd_fails"],
                                                    pair["only_bplsd_cs_4_fails"])


def _forbid_worker_starts(monkeypatch):
    def must_not_start(ctx, job, progress):
        raise AssertionError(f"started a worker for a cell that is done: {job['path']}")

    monkeypatch.setattr(cal, "_start_worker", must_not_start)


def test_restart_skips_completed_cells(smoke, monkeypatch):
    out, summary, _ = smoke

    _forbid_worker_starts(monkeypatch)
    assert run_calibration(SMOKE, out) == summary


def test_restart_runs_only_the_missing_cells(tmp_path, monkeypatch):
    cfg = dataclasses.replace(SMOKE, ps=(0.003, 0.002), max_shots=100, processes=2)
    first = run_calibration(cfg, tmp_path)
    cells = sorted(tmp_path.glob("cell_*.json"))
    assert len(cells) == 2
    kept = cells[0].read_bytes()
    cells[1].unlink()

    ran = []
    real = cal._start_worker
    monkeypatch.setattr(
        cal, "_start_worker", lambda ctx, job, prog: ran.append(job["path"]) or real(ctx, job, prog)
    )
    # Seeded, so the re-run cell has the same shots and failures (timings differ).
    assert _counts(run_calibration(cfg, tmp_path)) == _counts(first)
    assert ran == [str(cells[1])]
    assert cells[0].read_bytes() == kept


def test_a_different_config_refuses_the_directory(smoke):
    out, _, _ = smoke
    with pytest.raises(ValueError, match="different calibration run"):
        run_calibration(dataclasses.replace(SMOKE, max_shots=200), out)


def test_every_file_carries_the_calibration_marker(smoke):
    out, summary, _ = smoke
    files = sorted(out.iterdir())
    assert {f.name for f in files} >= {"plan.json", "summary.json"}
    for f in files:
        assert f.suffix == ".json", f
        assert json.loads(f.read_text(encoding="utf-8"))["calibration"] is True, f
    assert summary["calibration"] is True


def test_row_guard_rejects_calibration_output(smoke):
    out, summary, cell = smoke
    with pytest.raises(CalibrationOutputError):
        reject_calibration(out)
    with pytest.raises(CalibrationOutputError):
        reject_calibration(str(out))
    for f in out.glob("*.json"):
        with pytest.raises(CalibrationOutputError):
            reject_calibration(f)
    for obj in (summary, cell, [cell], pd.DataFrame([{"calibration": True, "p": 0.003}])):
        with pytest.raises(CalibrationOutputError):
            reject_calibration(obj)


def test_row_guard_passes_non_calibration_input(tmp_path):
    label = dataclasses.asdict(
        make_label(p=0.003, rounds=3, k=2, shots=1000, failures=120, decode_seconds=1.0)
    )
    (tmp_path / "rows.json").write_text(json.dumps([label]), encoding="utf-8")
    for obj in (label, [label], pd.DataFrame([label]), tmp_path, tmp_path / "rows.json"):
        assert reject_calibration(obj) is None


def test_refuses_an_out_dir_under_data(tmp_path):
    out = tmp_path / "data" / "calibration"
    with pytest.raises(ValueError, match="'data'"):
        run_calibration(SMOKE, out)
    assert not out.exists()


def test_refuses_to_start_over_the_time_limit(tmp_path):
    cfg = dataclasses.replace(SMOKE, cell_wall_seconds=3600.0, max_hours=0.5)
    with pytest.raises(RuntimeError, match="exceeds max_hours"):
        run_calibration(cfg, tmp_path)
    assert not list(tmp_path.glob("cell_*.json"))


def test_wall_clock_cap_stops_a_cell_and_is_recorded(tmp_path):
    cfg = dataclasses.replace(SMOKE, cell_wall_seconds=1e-9)
    summary = run_calibration(cfg, tmp_path)
    (cell,) = summary["per_cell"]
    assert cell["stopped_by"] == "wall_clock" and cell["shots"] == 0
    assert summary["stopped_by"] == {"min_failures": 0, "max_shots": 0, "wall_clock": 1,
                                     "killed": 0, "died": 0}


def test_decoders_differ_only_where_intended():
    osd_cls, osd = DECODERS["bposd"]
    assert osd_cls == DECODER_PARAMS["decoder"]
    assert osd == {k: v for k, v in DECODER_PARAMS.items()
                   if k not in ("library", "decoder", "dem_to_matrix")}
    bp = {k: osd[k] for k in ("bp_method", "max_iter", "ms_scaling_factor", "schedule")}
    for name, order in (("bplsd_cs_0", 0), ("bplsd_cs_4", 4)):
        cls, params = DECODERS[name]
        assert cls == "BpLsdDecoder"
        assert params == {**bp, "lsd_method": "lsd_cs", "lsd_order": order}


def test_mcnemar_exact():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(10, 0) == pytest.approx(2 * 0.5**10)
    assert mcnemar_exact(3, 9) == mcnemar_exact(9, 3)


def test_select_spanning_covers_the_range():
    cands = [{"code_id": f"c{i}", "n": 10 + i, "d_upper": d}
             for i, d in enumerate([3, 3, 4, 6, 6, 8, 12])]
    picked = select_spanning(cands, 3)
    assert [c["d_upper"] for c in picked] == [3, 8, 12]
    assert picked[0]["code_id"] == "c0"  # tie on d broken by n
    assert len({c["code_id"] for c in select_spanning(cands, 7)}) == 7
    with pytest.raises(ValueError):
        select_spanning(cands, 8)


def test_shots_needed_and_censoring_projection():
    assert cal._shots_needed(1000, 50)["estimate"] == 2000
    assert cal._shots_needed(1000, 50)["exceeds_max_shots"] is False
    assert cal._shots_needed(1000, 1)["exceeds_max_shots"] is False
    assert cal._shots_needed(MAX_SHOTS, 10)["exceeds_max_shots"] is True
    # No failures: provably censored only if even the Wilson upper bound needs > MAX_SHOTS.
    assert cal._shots_needed(MAX_SHOTS, 0)["exceeds_max_shots"] is True
    assert cal._shots_needed(100, 0)["exceeds_max_shots"] is None
    assert cal._run_shots(2000, False) == (10_000, 2000)  # SHOT_BATCH granularity
    assert cal._run_shots(None, None) == (MAX_SHOTS, MAX_SHOTS)


def test_pilot_projection_on_synthetic_cells():
    def cell(cid, n, d, shots, failures, sec):
        return {"shots": shots, "rounds": d, "code": {"code_id": cid, "n": n, "d_upper": d},
                "decoders": {"x": {"failures": failures, "decode_seconds": sec * shots}}}

    cells = [cell("a", 12, 3, 1000, 500, 0.001), cell("b", 144, 12, MAX_SHOTS, 0, 0.1)]
    population = [{"code_id": f"p{i}", "n": n, "d_upper": d}
                  for i, (n, d) in enumerate([(12, 3), (12, 3), (144, 12)])]
    proj = cal._project_pilot(cells, population, "x")
    top = proj["top_third_by_d_upper"]
    assert top["codes"] == 1 and top["projected_censored"] == 1 and top["censored_fraction"] == 1.0
    # Two codes at 10,000 shots x 1 ms, one censored at MAX_SHOTS x 0.1 s.
    assert proj["core_hours"] == pytest.approx((2 * 10_000 * 0.001 + MAX_SHOTS * 0.1) / 3600)


@pytest.mark.slow
def test_default_codes_span_the_population():
    codes, population = calibration_codes(CalibrationConfig())
    assert len(population) == 300 and len(codes) == 8
    assert [(c["name"], c["n"], c["k"], c["d_upper"]) for c in codes[:2]] == [
        ("ref72", 72, 12, 6), ("gross144", 144, 12, 12)]
    sampled = codes[2:]
    d_pop = [c["d_upper"] for c in population]
    assert min(c["d_upper"] for c in sampled) == min(d_pop)
    assert max(c["d_upper"] for c in sampled) == max(d_pop)
    assert len({c["code_id"] for c in codes}) == 8


@pytest.mark.slow
def test_cells_run_in_worker_processes(tmp_path):
    cfg = dataclasses.replace(SMOKE, ps=(0.003, 0.002), max_shots=100, processes=2)
    summary = run_calibration(cfg, tmp_path)
    assert summary["cells_done"] == 2
    serial = run_calibration(dataclasses.replace(cfg, processes=1), tmp_path / "serial")
    assert _counts(summary) == _counts(serial)


def test_calibrate_notebook_follows_the_template():
    from pathlib import Path

    nbs = Path(__file__).resolve().parents[1] / "notebooks"
    cells = lambda name: [  # noqa: E731
        "".join(c["source"])
        for c in json.loads((nbs / name).read_text(encoding="utf-8"))["cells"]
        if c["cell_type"] == "code"
    ]
    template, calib = cells("template_run.ipynb"), cells("calibrate.ipynb")
    assert len(calib) == 6
    assert calib[:2] == template[:2]  # install by SHA, provenance read back
    assert "run_calibration(CONFIG, OUT_DIR)" in calib[4]
    assert '"calibration": True' in calib[5]


def test_a_hung_decoder_is_killed_recorded_and_never_retried(tmp_path, monkeypatch):
    """A decode() that never returns: the run completes, the cell is ``killed``
    with the shot that hung, the flushed partial is kept, and resume skips it."""
    hang_on = 150  # batch 1, row 50, with sample_batch=100
    factory = functools.partial(hang_factory, hang_decoder="bplsd_cs_4", hang_on=hang_on)
    cfg = dataclasses.replace(SMOKE, cell_wall_seconds=3.0, cell_kill_margin_seconds=2.0)
    summary = run_calibration(cfg, tmp_path, _decoder_factory=factory)

    (path,) = tmp_path.glob("cell_*.json")
    cell = json.loads(path.read_text(encoding="utf-8"))
    assert cell["status"] == "killed" and cell["calibration"] is True
    assert (cell["batch_index"], cell["shot_in_batch"], cell["shot_index"]) == (1, 50, hang_on)
    assert cell["decoder"] == "bplsd_cs_4"
    h = protocol_hash(Protocol(p=0.003, decoder_version=installed_decoder_version()))
    assert cell["sampling_seed"] == sampling_seed(cell["code"]["code_id"], h)
    # Kept: the tally flushed at the end of batch 0, every decoder done on each shot.
    part = cell["partial"]
    assert part["shots"] == 100 and set(part["decoders"]) == {"bposd", "bplsd_cs_4"}
    assert all(r["syndromes_sha256"] == part["decoders"]["bposd"]["syndromes_sha256"]
               for r in part["decoders"].values())
    assert not list(tmp_path.glob("partial_*.json"))
    assert summary["stopped_by"]["killed"] == 1 and summary["per_cell"] == []
    (u,) = summary["unfinished_cells"]
    assert u["shot_index"] == hang_on and u["partial"]["shots"] == 100

    # The shot is reproducible from the record alone.
    circuit = build_memory_circuit(cell["code"], cell["p"], cell["rounds"])
    sampler = circuit.compile_detector_sampler(seed=cell["sampling_seed"])
    for _ in range(cell["batch_index"] + 1):
        dets, _ = sampler.sample(cell["sample_batch"], separate_observables=True)
    assert dets[cell["shot_in_batch"]].any()  # a real, non-trivial syndrome row

    _forbid_worker_starts(monkeypatch)
    again = run_calibration(cfg, tmp_path, _decoder_factory=factory)
    assert again["unfinished_cells"] == summary["unfinished_cells"]
    with pytest.raises(CalibrationOutputError):
        reject_calibration(path)
