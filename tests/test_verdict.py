"""M0-RUN-04 on synthetic measurement and feature frames: the baseline and ``run_m0_evaluation``.

Nothing here is a real label. A few programs, tens of codes; the real run, on
242 of the 244 codes (D-036), is the owner's.
"""

import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from qecscreen.evaluate.rows import MEASUREMENT_SCHEMA
from qecscreen.features.table import FEATURE_SCHEMA, FEATURE_SET
from qecscreen.models import baseline
from qecscreen.models.baseline import (
    MODEL_FEATURES,
    MODEL_VERSION,
    PREDICTION_COLUMNS,
    PREDICTIONS_FILE,
    out_of_fold_predictions,
    write_predictions,
)
from qecscreen.protocol import logical_error_rate
from qecscreen.verdict import (
    BOOTSTRAP_SEED,
    GROUPING,
    LABEL_NOISE_DRAWS,
    LABEL_NOISE_SEED,
    RESULTS_FILE,
    TABLE_FILE,
    label_noise_ceiling,
    run_m0_evaluation,
)

HASH = "a" * 64
PROGRAMS = ("bb_v1_alpha", "bb_v1_beta", "bb_v1_gamma", "bb_v1_delta", "bb_v1_eps")
PER_PROGRAM = 8
CENSORED = ("bb_v1_beta-0003", "bb_v1_delta-0000", "bb_v1_eps-0007")
N_ROWS = len(PROGRAMS) * PER_PROGRAM


def _frames(seed=0):
    """(measurements, features): 40 codes over 5 programs, 3 censored; LER falls with d_upper, plus noise.

    ``check_weight_mean`` is unique per code, so a row seen by a fit can be traced to its code.
    """
    rng = np.random.default_rng(seed)
    code_ids, programs = [], []
    for p in PROGRAMS:
        for i in range(PER_PROGRAM):
            code_ids.append(f"{p}-{i:04d}")
            programs.append(p)
    n = rng.integers(2, 7, N_ROWS) * 12
    k = rng.integers(1, 7, N_ROWS) * 2
    d = rng.integers(3, 10, N_ROWS)
    phi = k * d**2 / n
    log_ler = -1.5 - 0.25 * d + rng.normal(0, 0.2, N_ROWS)
    ler = 10.0**log_ler
    censored = np.isin(code_ids, CENSORED)
    measurements = pd.DataFrame({
        "code_id": code_ids,
        "construction_program_id": programs,
        "family": "BB",
        "params_json": "{}",
        "seed": 0,
        "n": n, "k": k, "d_exact": None, "d_upper": d,
        "phi_from_d_upper": phi,
        "n_ancilla": n, "n_total": 2 * n,
        "protocol_hash": HASH,
        "commit_sha": "1" * 40,
        "sampling_seed": np.arange(N_ROWS),
        "stim_version": "1.16.0",
        "cpu_class": "x86_64/sse2",
        "p": 0.002,
        "rounds": d,
        "shots": 40_960,
        "failures": np.where(censored, 50, 500),
        "true_ler": np.where(censored, np.nan, ler),
        "true_ler_ub": ler * 1.3,
        "true_ler_ci_low": ler * 0.8,
        "true_ler_ci_high": ler * 1.3,
        "censored": censored,
        "decode_seconds": 1.0,
        "schema_version": 1,
        "created_at": "2026-10-01T00:00:00+00:00",
    })
    features = {"code_id": code_ids, "feature_set": FEATURE_SET}
    for field in FEATURE_SCHEMA:
        if field.name in features:
            continue
        if field.name in measurements:
            features[field.name] = measurements[field.name].to_numpy()
        elif pa.types.is_floating(field.type):
            features[field.name] = rng.uniform(0, 1, N_ROWS)
        else:
            features[field.name] = rng.integers(0, 50, N_ROWS)
    features["check_weight_mean"] = np.arange(N_ROWS) + 0.5
    return measurements, pd.DataFrame(features)[list(FEATURE_SCHEMA.names)]


def _write(tmp_path, measurements, features):
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    m_path, f_path = data / "m0_measurements.parquet", data / "m0_features.parquet"
    pq.write_table(pa.Table.from_pandas(measurements, schema=MEASUREMENT_SCHEMA, preserve_index=False), m_path)
    pq.write_table(pa.Table.from_pandas(features, schema=FEATURE_SCHEMA, preserve_index=False), f_path)
    return m_path, f_path


def _run(tmp_path, measurements=None, features=None, **kw):
    if measurements is None:
        measurements, features = _frames()
    m_path, f_path = _write(tmp_path, measurements, features)
    out = tmp_path / "evidence" / "m0"
    return run_m0_evaluation(m_path, f_path, out, expected_rows=N_ROWS, n_resamples=50, **kw), tmp_path / "data", out


def _joined():
    measurements, features = _frames()
    cols = ["code_id", "construction_program_id", "censored", "true_ler"]
    return measurements[cols].merge(features, on="code_id")


# --- the baseline -------------------------------------------------------------


def test_features_are_every_feature_column_but_the_identity_ones_phi_included():
    assert "code_id" not in MODEL_FEATURES and "feature_set" not in MODEL_FEATURES
    assert "phi_from_d_upper" in MODEL_FEATURES
    assert set(MODEL_FEATURES) | {"code_id", "feature_set"} == set(FEATURE_SCHEMA.names)


def test_lightgbm_params_are_pinned():
    assert baseline.LGBM_PARAMS == {
        "n_estimators": 300, "learning_rate": 0.05, "num_leaves": 15, "min_child_samples": 10,
        "subsample": 1.0, "colsample_bytree": 1.0, "random_state": 0, "deterministic": True,
        "n_jobs": 1, "verbose": -1,
    }


class _Recording:
    """Wraps ``make_model``: records the codes (by their unique ``check_weight_mean``) each fit saw."""

    def __init__(self, monkeypatch):
        self.fits = []
        real = baseline.make_model
        col = MODEL_FEATURES.index("check_weight_mean")
        recorder = self

        def make():
            model = real()
            fit = model.fit

            def recording_fit(x, y, **kw):
                recorder.fits.append((x[:, col].copy(), np.asarray(y).copy()))
                return fit(x, y, **kw)

            model.fit = recording_fit
            return model

        monkeypatch.setattr(baseline, "make_model", make)


def test_leave_one_program_out_no_program_on_both_sides(monkeypatch):
    rec = _Recording(monkeypatch)
    frame = _joined()
    pred = out_of_fold_predictions(frame)
    assert len(rec.fits) == len(PROGRAMS)
    code_of = dict(zip(frame["check_weight_mean"], frame["code_id"]))
    program_of = dict(zip(frame["code_id"], frame["construction_program_id"]))
    for i, (seen, _) in enumerate(rec.fits):
        trained = {program_of[code_of[v]] for v in seen}
        tested = set(frame.loc[pred["fold"] == i, "construction_program_id"])
        assert len(tested) == 1  # one program per fold
        assert not trained & tested  # INV-2
        assert trained | tested == set(PROGRAMS)


def test_censored_rows_are_excluded_from_the_fit_but_predicted(monkeypatch):
    rec = _Recording(monkeypatch)
    frame = _joined()
    pred = out_of_fold_predictions(frame)
    censored_marks = set(frame.loc[frame["censored"], "check_weight_mean"])
    for seen, y in rec.fits:
        assert not censored_marks & set(seen)
        assert np.isfinite(y).all()
    assert set(CENSORED) <= set(pred["code_id"])
    assert np.isfinite(pred["pred_log10_ler"]).all()
    assert list(pred["code_id"]) == list(frame["code_id"]) and len(pred) == N_ROWS


def test_the_target_is_log10_true_ler(monkeypatch):
    rec = _Recording(monkeypatch)
    frame = _joined()
    out_of_fold_predictions(frame)
    by_mark = dict(zip(frame["check_weight_mean"], np.log10(frame["true_ler"])))
    for seen, y in rec.fits:
        assert y == pytest.approx([by_mark[v] for v in seen], rel=1e-12)


def test_out_of_fold_predictions_are_deterministic():
    a = out_of_fold_predictions(_joined())
    b = out_of_fold_predictions(_joined())
    pd.testing.assert_frame_equal(a, b)
    assert tuple(a.columns) == PREDICTION_COLUMNS and set(a["model_version"]) == {MODEL_VERSION}


def test_write_predictions_refuses_to_overwrite_and_a_dir_not_named_data(tmp_path):
    pred = out_of_fold_predictions(_joined())
    with pytest.raises(ValueError, match="data/"):
        write_predictions(pred, tmp_path / "elsewhere")
    path = write_predictions(pred, tmp_path / "data")
    assert path.name == PREDICTIONS_FILE
    assert tuple(pq.read_schema(path).names) == PREDICTION_COLUMNS
    with pytest.raises(FileExistsError):
        write_predictions(pred, tmp_path / "data")


# --- run_m0_evaluation --------------------------------------------------------


def test_run_writes_predictions_results_and_table(tmp_path, capsys):
    results, data, out = _run(tmp_path)
    pred = pq.read_table(data / PREDICTIONS_FILE).to_pandas()
    assert tuple(pred.columns) == PREDICTION_COLUMNS and len(pred) == N_ROWS
    stored = json.loads((out / RESULTS_FILE).read_text(encoding="utf-8"))
    assert stored == json.loads(json.dumps(results))
    table = (out / TABLE_FILE).read_text(encoding="utf-8")
    assert table.strip() == capsys.readouterr().out.strip()
    assert results["grouping"] == GROUPING == "leave_one_program_out"
    assert "family-holdout" in results["grouping_note"] and "INV-2" in results["grouping_note"]
    assert "leave_one_program_out" in table
    assert results["bootstrap"]["seed"] == BOOTSTRAP_SEED
    assert results["n_programs"] == len(PROGRAMS) and results["n_censored"] == len(CENSORED)
    assert set(results["metrics"]) == {"recall_at_30_of_top_10_leave_one_program_out",
                                       "spearman_leave_one_program_out"}
    for m in results["metrics"].values():
        for scorer in ("model", "phi"):
            assert m[scorer]["n_censored"] == len(CENSORED)
            assert m[scorer]["low"] <= m[scorer]["estimate"] <= m[scorer]["high"]
        assert m["model_minus_phi"]["estimate"] == pytest.approx(m["model"]["estimate"] - m["phi"]["estimate"])
    text = (table + json.dumps(results)).lower()
    assert "proceed" not in text and "kill" not in text


def test_size_scaling_diagnostic_per_template(tmp_path):
    results, _, _ = _run(tmp_path)
    scaling = {t["construction_program_id"]: t for t in results["size_scaling"]}
    assert set(scaling) == set(PROGRAMS)
    for t in scaling.values():
        d = [r["d_upper"] for r in t["rows"]]
        assert d == sorted(d)
        for r in t["rows"]:
            if r["censored"]:
                assert r["true_ler"] is None and r["true_ler_ub"] is not None
            else:
                assert r["true_ler_ci_low"] <= r["true_ler"] <= r["true_ler_ci_high"]
        assert "proceed" not in t["reading"]


def test_size_scaling_without_two_distinct_d_upper_has_no_reading(tmp_path):
    measurements, features = _frames()
    alpha = measurements["construction_program_id"] == "bb_v1_alpha"
    measurements.loc[alpha, ["d_upper", "rounds"]] = 5
    features.loc[alpha.to_numpy(), "d_upper"] = 5
    results, _, _ = _run(tmp_path, measurements, features)
    t = next(t for t in results["size_scaling"] if t["construction_program_id"] == "bb_v1_alpha")
    assert t["reading"].startswith("no reading") and t["spearman_d_upper_vs_true_ler"] is None


def test_run_is_deterministic(tmp_path):
    first, data1, _ = _run(tmp_path / "one")
    second, data2, _ = _run(tmp_path / "two")
    pd.testing.assert_frame_equal(pq.read_table(data1 / PREDICTIONS_FILE).to_pandas(),
                                  pq.read_table(data2 / PREDICTIONS_FILE).to_pandas())
    assert first["metrics"] == second["metrics"]
    assert first["size_scaling"] == second["size_scaling"]
    assert first["label_noise_ceiling"] == second["label_noise_ceiling"]


def test_run_does_not_depend_on_input_row_order(tmp_path):
    measurements, features = _frames()
    first, _, _ = _run(tmp_path / "one", measurements, features)
    second, _, _ = _run(tmp_path / "two", measurements.sample(frac=1, random_state=3),
                        features.sample(frac=1, random_state=4))
    assert first["metrics"] == second["metrics"]


def test_run_refuses_mismatched_code_ids(tmp_path):
    measurements, features = _frames()
    features.loc[0, "code_id"] = "bb_v1_alpha-9999"
    with pytest.raises(ValueError, match="code_id sets differ"):
        _run(tmp_path, measurements, features)
    assert not (tmp_path / "data" / PREDICTIONS_FILE).exists()


def test_run_refuses_mixed_hashes(tmp_path):
    measurements, features = _frames()
    measurements.loc[0, "protocol_hash"] = "b" * 64
    with pytest.raises(ValueError, match="distinct protocols"):
        _run(tmp_path, measurements, features)
    assert not (tmp_path / "data" / PREDICTIONS_FILE).exists()


def test_run_refuses_the_wrong_row_count(tmp_path):
    measurements, features = _frames()
    m_path, f_path = _write(tmp_path, measurements, features)
    with pytest.raises(ValueError, match="expected 242"):
        run_m0_evaluation(m_path, f_path, tmp_path / "evidence" / "m0")


def test_run_refuses_files_that_disagree_on_a_shared_column(tmp_path):
    measurements, features = _frames()
    features.loc[3, "d_upper"] += 1
    with pytest.raises(ValueError, match="d_upper differs"):
        _run(tmp_path, measurements, features)


def test_run_refuses_an_out_dir_outside_evidence_and_an_existing_output(tmp_path):
    measurements, features = _frames()
    m_path, f_path = _write(tmp_path, measurements, features)
    with pytest.raises(ValueError, match="evidence/"):
        run_m0_evaluation(m_path, f_path, tmp_path / "results", expected_rows=N_ROWS)
    with pytest.raises(ValueError, match="evidence/"):
        run_m0_evaluation(m_path, f_path, tmp_path / "evidence" / "data", expected_rows=N_ROWS)
    run_m0_evaluation(m_path, f_path, tmp_path / "evidence" / "m0", expected_rows=N_ROWS, n_resamples=10)
    with pytest.raises(FileExistsError):
        run_m0_evaluation(m_path, f_path, tmp_path / "evidence" / "m0", expected_rows=N_ROWS, n_resamples=10)


# --- the label-noise ceiling ----------------------------------------------------


def _label_frame(failures, shots, rounds, k):
    """Rows whose observed labels follow from their counts (INV-4), none censored."""
    ler = [logical_error_rate(f / n, r, kk) for f, n, r, kk in zip(failures, shots, rounds, k)]
    return pd.DataFrame({"protocol_hash": HASH, "failures": failures, "shots": shots, "rounds": rounds, "k": k,
                         "censored": False, "true_ler": ler, "true_ler_ub": [x * 1.3 for x in ler]})


def test_the_label_noise_ceiling_is_reported_and_decides_nothing(tmp_path):
    results, _, out = _run(tmp_path)
    c = results["label_noise_ceiling"]
    assert c["seed"] == LABEL_NOISE_SEED == 20261002 and c["n_draws"] == LABEL_NOISE_DRAWS == 1_000
    assert c["metric"] == "recall_at_30_of_top_10" and "decides nothing" in c["note"]
    assert 0.0 <= c["p05"] <= c["p95"] <= 1.0 and c["p05"] - 1e-12 <= c["mean"] <= c["p95"] + 1e-12
    assert "label_noise_ceiling" in (out / TABLE_FILE).read_text(encoding="utf-8")


def test_the_label_noise_ceiling_draws_beta_jeffreys_per_code_with_the_pinned_seed():
    """Two codes, top 1 of top 1: recall is 1 on a draw exactly when the observed-better code draws lower."""
    frame = _label_frame([30, 40], [1_000, 1_000], [1, 1], [1, 1])  # observed: code 0 better
    c = label_noise_ceiling(frame, k=1, top_n=1)
    draws = np.random.default_rng(LABEL_NOISE_SEED).beta([30.5, 40.5], [970.5, 960.5], size=(LABEL_NOISE_DRAWS, 2))
    hits = (draws[:, 0] < draws[:, 1]).astype(float)
    assert c["mean"] == pytest.approx(hits.mean(), abs=1e-15)
    assert 0.5 < c["mean"] < 1.0  # noisy enough to miss sometimes
    assert c == label_noise_ceiling(frame, k=1, top_n=1)


def test_the_label_noise_ceiling_ranks_by_ler_not_by_failure_fraction():
    """P_L 0.1 over r * k = 1 is a worse LER than P_L 0.2 over r * k = 10 (INV-4)."""
    frame = _label_frame([100_000, 200_000], [1_000_000, 1_000_000], [1, 5], [1, 2])
    assert frame["true_ler"].iloc[1] < frame["true_ler"].iloc[0]
    assert label_noise_ceiling(frame, k=1, top_n=1)["mean"] == 1.0


def test_the_label_noise_ceiling_is_one_for_well_separated_labels_and_below_for_noisy_ones():
    rng = np.random.default_rng(0)
    n = 40
    rounds, k = rng.integers(3, 8, n), rng.integers(1, 7, n)
    separated = _label_frame((np.arange(n) + 1) * 10_000, [10**8] * n, rounds, k)
    assert label_noise_ceiling(separated)["p05"] == 1.0
    noisy = _label_frame([100 + i for i in range(n)], [40_960] * n, [1] * n, [1] * n)
    c = label_noise_ceiling(noisy)
    assert c["mean"] < 1.0 and c["p05"] < c["p95"]
