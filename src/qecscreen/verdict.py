"""M0-RUN-04: the numbers the M0 verdict is read from. **It decides nothing.**

``run_m0_evaluation(measurements_path, features_path, out_dir)`` joins the
measurements (``data/m0_measurements.parquet``) and the features
(``data/m0_features.parquet``) on ``code_id``, fits the LightGBM baseline out
of fold (``models.baseline``), writes ``data/m0_predictions.parquet``
(D-009's third file), and reports, for the model and for Φ:

- Recall@30-of-top-10 and Spearman on the pooled out-of-fold predictions, with
  paired bootstrap 95% intervals and the model − Φ interval
  (``metrics.bootstrap_compare``, ``BOOTSTRAP_SEED``, recorded);
- each metric's censored count and censored-excluded value (D-035);
- the D-031 size-scaling diagnostic per template (``spec/evals.md §7``,
  "M0 verdict");
- the label-noise ceiling: how well the observed labels' own ranking recovers
  labels redrawn from their binomial noise (``label_noise_ceiling``),
  reported only.

The results go to ``<out_dir>/m0_results.json`` and ``m0_results.txt``, under
``evidence/``, never ``data/``. Nothing here says proceed or kill: the owner
records the verdict in ``spec/evals.md §7``.

**Grouping, stated in the output.** M0 has one family (BB), so the
family-holdout split INV-2 names as the headline does not exist here. The
split is leave-one-program-out over the construction programs, and the metric
names carry that suffix.

Lives outside ``evaluate/`` because that package is on the running pilot's
path (owner, 2026-10-01); it only imports constants from it.
"""

from __future__ import annotations

# First, so lightgbm loads before pyarrow (see models/baseline.py's import note).
from qecscreen.models.baseline import (  # isort: skip
    LGBM_PARAMS,
    MODEL_FEATURES,
    MODEL_VERSION,
    TARGET,
    out_of_fold_predictions,
    write_predictions,
)

import hashlib
import json
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from qecscreen import provenance
from qecscreen.evaluate.pilot import DATASET_SIZE
from qecscreen.evaluate.rows import MEASUREMENT_COLUMNS
from qecscreen.features.table import FEATURE_COLUMNS, FEATURE_SET
from qecscreen.metrics import (
    BOOTSTRAP_RESAMPLES,
    MODEL_SCORE,
    PHI_SCORE,
    BootstrapComparison,
    RankingMetric,
    _recall,
    bootstrap_compare,
    ranking_value,
    recall_at_k,
    spearman,
    with_model_score,
)
from qecscreen.protocol import assert_single_protocol, logical_error_rate

__all__ = [
    "BOOTSTRAP_SEED",
    "GROUPING",
    "LABEL_NOISE_DRAWS",
    "LABEL_NOISE_SEED",
    "RESULTS_FILE",
    "TABLE_FILE",
    "format_results",
    "label_noise_ceiling",
    "run_m0_evaluation",
]

BOOTSTRAP_SEED = 20261001  # pinned; recorded in the results
LABEL_NOISE_SEED = 20261002  # owner, 2026-10-02; recorded in the results
LABEL_NOISE_DRAWS = 1_000  # owner, 2026-10-02
GROUPING = "leave_one_program_out"
GROUPING_NOTE = (
    "M0 has one family (BB), so there is no family-holdout split: the headline here is "
    "leave-one-program-out over the construction programs, not the family-holdout metric "
    "INV-2 names as the headline. Each program is held out once; metrics are computed on "
    "the pooled out-of-fold predictions."
)
RESULTS_FILE = "m0_results.json"
TABLE_FILE = "m0_results.txt"
FORMAT = "qecscreen_m0_evaluation_v1"

_METRICS = {
    f"recall_at_30_of_top_10_{GROUPING}": recall_at_k,
    f"spearman_{GROUPING}": spearman,
}
_SHARED = ("n", "k", "d_upper", "n_ancilla", "n_total")  # in both files; must agree
_FROM_MEASUREMENTS = ("code_id", "construction_program_id", "family", "protocol_hash", "rounds", "shots",
                      "failures", "censored", "true_ler", "true_ler_ub", "true_ler_ci_low", "true_ler_ci_high")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(measurements_path: Path, features_path: Path, expected_rows: int) -> pd.DataFrame:
    """The joined frame, one row per code, sorted by ``code_id``; every check of the inputs is here."""
    measurements = pq.read_table(measurements_path).to_pandas()
    features = pq.read_table(features_path).to_pandas()
    if tuple(measurements.columns) != MEASUREMENT_COLUMNS:
        raise ValueError(f"{measurements_path} does not have the measurement columns (architecture §3)")
    if tuple(features.columns) != FEATURE_COLUMNS:
        raise ValueError(f"{features_path} does not have FEATURE_COLUMNS")
    if set(features["feature_set"]) != {FEATURE_SET}:
        raise ValueError(f"feature_set {sorted(set(features['feature_set']))} is not [{FEATURE_SET!r}]")
    for name, frame in (("measurements", measurements), ("features", features)):
        if len(frame) != expected_rows:
            raise ValueError(f"the {name} have {len(frame)} rows; expected {expected_rows}")
        if frame["code_id"].duplicated().any():
            raise ValueError(f"a code_id appears twice in the {name}")
    if measurements["protocol_hash"].isna().any():
        raise ValueError("a row has a null protocol_hash (CONTRACT INV-6)")
    assert_single_protocol(measurements["protocol_hash"])
    only_m = set(measurements["code_id"]) - set(features["code_id"])
    only_f = set(features["code_id"]) - set(measurements["code_id"])
    if only_m or only_f:
        raise ValueError(f"code_id sets differ: {len(only_m)} only in the measurements "
                         f"(e.g. {sorted(only_m)[:3]}), {len(only_f)} only in the features (e.g. {sorted(only_f)[:3]})")
    joined = measurements.loc[:, list(_FROM_MEASUREMENTS) + list(_SHARED) + [PHI_SCORE]].merge(
        features, on="code_id", suffixes=("_m", ""), validate="one_to_one")
    for col in _SHARED:
        if not (joined[f"{col}_m"].astype("int64") == joined[col].astype("int64")).all():
            raise ValueError(f"{col} differs between the measurements and the features")
    if not np.allclose(joined[f"{PHI_SCORE}_m"], joined[PHI_SCORE], rtol=1e-12, atol=0):
        raise ValueError(f"{PHI_SCORE} differs between the measurements and the features")
    joined = joined.drop(columns=[f"{c}_m" for c in (*_SHARED, PHI_SCORE)])
    return joined.sort_values("code_id", ignore_index=True)


def _metric_json(m: RankingMetric) -> dict[str, Any]:
    return {"value": m.value, "n_censored": m.n_censored, "value_censored_excluded": m.value_censored_excluded}


def _comparison_json(c: BootstrapComparison) -> dict[str, Any]:
    def interval(i):
        return {"estimate": i.estimate, "low": i.low, "high": i.high}

    return {
        "model": {**interval(c.model), **_metric_json(c.model_metric)},
        "phi": {**interval(c.phi), **_metric_json(c.phi_metric)},
        "model_minus_phi": interval(c.difference),
    }


def _none_if_nan(x: float) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def size_scaling(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """D-031's diagnostic, per template: its rows ordered by ``d_upper``, and no pass/fail.

    Non-censored rows carry ``true_ler`` and its 95% interval; censored rows
    carry only ``true_ler_ub``, an upper bound (INV-3). A template with fewer
    than two distinct ``d_upper`` among its non-censored rows has no reading.
    Otherwise ``spearman_d_upper_vs_true_ler`` (non-censored rows, average
    ranks) is reported as a description: negative means larger ``d_upper``
    goes with lower LER. Reading it is the owner's.
    """
    out = []
    for program, rows in frame.groupby("construction_program_id", sort=True):
        rows = rows.sort_values(["d_upper", "n", "code_id"])
        point = rows[~rows["censored"]]
        distinct = int(point["d_upper"].nunique())
        entry: dict[str, Any] = {
            "construction_program_id": program,
            "n_codes": len(rows),
            "n_censored": int(rows["censored"].sum()),
            "distinct_d_upper_non_censored": distinct,
            "rows": [{
                "code_id": r.code_id, "n": int(r.n), "k": int(r.k), "d_upper": int(r.d_upper),
                "censored": bool(r.censored),
                "true_ler": None if r.censored else float(r.true_ler),
                "true_ler_ci_low": None if r.censored else float(r.true_ler_ci_low),
                "true_ler_ci_high": None if r.censored else float(r.true_ler_ci_high),
                "true_ler_ub": float(r.true_ler_ub),
            } for r in rows.itertuples()],
        }
        if distinct < 2:
            entry["reading"] = "no reading: fewer than two distinct d_upper among non-censored rows"
            entry["spearman_d_upper_vs_true_ler"] = None
        else:
            rho = point["d_upper"].rank().corr(point["true_ler"].rank())
            entry["reading"] = "left to the owner"
            entry["spearman_d_upper_vs_true_ler"] = _none_if_nan(rho)
        out.append(entry)
    return out


def label_noise_ceiling(frame: pd.DataFrame, *, seed: int = LABEL_NOISE_SEED,
                        n_draws: int = LABEL_NOISE_DRAWS, k: int = 30, top_n: int = 10) -> dict[str, Any]:
    """Recall@``k``-of-top-``top_n`` of the observed labels against labels redrawn from their noise. Decides nothing.

    Per code, in ``frame``'s row order, the shot failure fraction is drawn from
    Beta(failures + 1/2, shots - failures + 1/2), censored rows included, and
    turned into an LER by ``protocol.logical_error_rate`` with the row's
    ``rounds`` and ``k`` (INV-4). Each draw's top ``top_n`` is the truth; the
    scorer is the observed ranking (``true_ler``, or ``true_ler_ub`` if
    censored, D-035), with ``recall_at_k``'s tie rule. Reported: the mean and
    the 5th and 95th percentiles over ``n_draws`` draws (``numpy.percentile``,
    linear). How far a perfect ranking of these labels can be from a ranking
    of the true LERs, given only the shots taken.
    """
    observed = ranking_value(frame).to_numpy()
    failures = frame["failures"].to_numpy(dtype="int64")
    shots = frame["shots"].to_numpy(dtype="int64")
    rounds = frame["rounds"].to_numpy(dtype="int64")
    k_logical = frame["k"].to_numpy(dtype="int64")
    rng = np.random.default_rng(seed)
    draws = rng.beta(failures + 0.5, shots - failures + 0.5, size=(n_draws, len(frame)))
    values = []
    for draw in draws:
        ler = np.array([logical_error_rate(float(p), int(r), int(kl)) for p, r, kl in zip(draw, rounds, k_logical)])
        recall = _recall(ler, -observed, k, top_n)
        if recall is None:
            raise ValueError(f"Recall@{k}-of-top-{top_n} is undefined on {len(frame)} rows")
        values.append(recall)
    values = np.asarray(values)
    return {
        "metric": f"recall_at_{k}_of_top_{top_n}",
        "note": "Reported only; decides nothing.",
        "draw": "per code, P_L ~ Beta(failures + 0.5, shots - failures + 0.5), censored rows included; "
                "LER = logical_error_rate(P_L, rounds, k)",
        "truth": f"each draw's top {top_n} by drawn LER",
        "scorer": "the observed ranking: true_ler, or true_ler_ub if censored (D-035); same tie rule",
        "seed": seed,
        "n_draws": n_draws,
        "mean": float(values.mean()),
        "p05": float(np.percentile(values, 5)),
        "p95": float(np.percentile(values, 95)),
    }


def _check_out_dir(out_dir: Path) -> Path:
    parts = out_dir.resolve().parts
    if "evidence" not in parts or "data" in parts:
        raise ValueError(f"results go under evidence/, never data/: {out_dir}")
    for name in (RESULTS_FILE, TABLE_FILE):
        if (out_dir / name).exists():
            raise FileExistsError(f"{out_dir / name} exists; results are not overwritten")
    return out_dir


def run_m0_evaluation(
    measurements_path: str | os.PathLike[str],
    features_path: str | os.PathLike[str],
    out_dir: str | os.PathLike[str],
    *,
    data_dir: str | os.PathLike[str] | None = None,
    expected_rows: int = DATASET_SIZE,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """Fit out of fold, write the predictions and the results, print the table; return the results.

    ``data_dir`` (default: the measurements' directory) receives
    ``m0_predictions.parquet``; ``out_dir`` must lie under ``evidence/``.
    Refuses before writing anything if: either input does not have
    ``expected_rows`` rows (242 of 244, D-036), a ``code_id`` is
    repeated, the two ``code_id`` sets differ, the measurements carry more
    than one ``protocol_hash`` or a null one (INV-6), the feature set is not
    ``FEATURE_SET``, the files disagree on ``n``, ``k``, ``d_upper``,
    ``n_ancilla``, ``n_total`` or Φ, or an output already exists.
    """
    m_path, f_path, out = Path(measurements_path), Path(features_path), Path(out_dir)
    data = Path(data_dir) if data_dir is not None else m_path.parent
    _check_out_dir(out)
    frame = _load(m_path, f_path, expected_rows)
    predictions = out_of_fold_predictions(frame)
    predictions_path = write_predictions(predictions, data)
    scored = with_model_score(frame.merge(predictions[["code_id", "pred_log10_ler"]], on="code_id",
                                          validate="one_to_one"))
    metrics = {name: _comparison_json(bootstrap_compare(scored, fn, seed=BOOTSTRAP_SEED, n_resamples=n_resamples,
                                                        model_col=MODEL_SCORE, phi_col=PHI_SCORE))
               for name, fn in _METRICS.items()}
    programs = sorted(frame["construction_program_id"].unique())
    results = {
        "format": FORMAT,
        "note": "Numbers only. No verdict is recorded here; the owner records it in spec/evals.md §7.",
        "grouping": GROUPING,
        "grouping_note": GROUPING_NOTE,
        "inputs": {
            "measurements": {"path": str(m_path), "sha256": _sha256(m_path)},
            "features": {"path": str(f_path), "sha256": _sha256(f_path), "feature_set": FEATURE_SET},
            "predictions": {"path": str(predictions_path), "sha256": _sha256(predictions_path)},
        },
        "protocol_hash": frame["protocol_hash"].iloc[0],
        "families": sorted(frame["family"].unique()),
        "n_codes": len(frame),
        "n_programs": len(programs),
        "programs": {p: int((frame["construction_program_id"] == p).sum()) for p in programs},
        "n_censored": int(frame["censored"].sum()),
        "censoring_rate": float(frame["censored"].mean()),
        "model": {
            "model_version": MODEL_VERSION,
            "params": LGBM_PARAMS,
            "target": TARGET + " on non-censored rows only (INV-3); censored rows are predicted and ranked",
            "features": list(MODEL_FEATURES),
        },
        "scores": {"model": f"{MODEL_SCORE} = -pred_log10_ler", "phi": PHI_SCORE,
                   "truth": "ascending true_ler, or true_ler_ub if censored (D-035)"},
        "bootstrap": {"seed": BOOTSTRAP_SEED, "n_resamples": n_resamples, "resampled_unit": "code",
                      "interval": "percentile 95% (2.5th, 97.5th), paired over model and phi"},
        "recall_ties": "expected recall under uniformly random tie-breaking at both cut-offs",
        "metrics": metrics,
        "size_scaling": size_scaling(frame),
        "label_noise_ceiling": label_noise_ceiling(frame),
        "provenance": provenance.record(),
    }
    table = format_results(results)
    out.mkdir(parents=True, exist_ok=True)
    (out / RESULTS_FILE).write_text(json.dumps(results, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    (out / TABLE_FILE).write_text(table + "\n", encoding="utf-8")
    print(table)
    return results


def _f(x: float | None, spec: str = ".3f") -> str:
    return "–" if x is None else format(x, spec)


def format_results(results: Mapping[str, Any]) -> str:
    """The printed table: each metric for the model, Φ and model − Φ, then the size-scaling diagnostic."""
    lines = [
        f"M0 evaluation - {results['n_codes']} codes, {results['n_programs']} programs, "
        f"{results['n_censored']} censored ({results['censoring_rate']:.1%})",
        f"protocol_hash {results['protocol_hash']}",
        f"grouping: {results['grouping']}. {results['grouping_note']}",
        f"model {results['model']['model_version']}; bootstrap {results['bootstrap']['n_resamples']} resamples, "
        f"seed {results['bootstrap']['seed']}, percentile 95%",
        "",
        f"{'metric':<52} {'scorer':<14} {'estimate':>9} {'95% low':>9} {'95% high':>9} "
        f"{'censored':>9} {'excl. censored':>15}",
    ]
    for name, m in results["metrics"].items():
        for scorer in ("model", "phi"):
            s = m[scorer]
            lines.append(f"{name:<52} {scorer:<14} {_f(s['estimate']):>9} {_f(s['low']):>9} {_f(s['high']):>9} "
                         f"{s['n_censored']:>9} {_f(s['value_censored_excluded']):>15}")
        d = m["model_minus_phi"]
        lines.append(f"{name:<52} {'model - phi':<14} {_f(d['estimate']):>9} {_f(d['low']):>9} {_f(d['high']):>9}")
    c = results["label_noise_ceiling"]
    lines.append(f"{c['metric'] + '_label_noise_ceiling':<52} {'observed':<14} {_f(c['mean']):>9} "
                 f"{_f(c['p05']):>9} {_f(c['p95']):>9}   mean [5th, 95th] over {c['n_draws']} draws, "
                 f"seed {c['seed']}; {c['note']}")
    lines += ["", "Size scaling per template (D-031): non-censored true_ler [95%]; censored rows as <= ub"]
    for t in results["size_scaling"]:
        lines.append(f"{t['construction_program_id']}: {t['n_codes']} codes, {t['n_censored']} censored, "
                     f"{t['distinct_d_upper_non_censored']} distinct d_upper non-censored; "
                     f"rho(d_upper, true_ler) {_f(t['spearman_d_upper_vs_true_ler'])}; {t['reading']}")
        for r in t["rows"]:
            value = (f"<= {r['true_ler_ub']:.2e} (censored)" if r["censored"] else
                     f"{r['true_ler']:.2e} [{r['true_ler_ci_low']:.2e}, {r['true_ler_ci_high']:.2e}]")
            lines.append(f"    [[{r['n']},{r['k']},<={r['d_upper']}]] {r['code_id']}: {value}")
    return "\n".join(lines)
