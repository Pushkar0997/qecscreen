"""Ranking metrics over codes: Spearman (M0-METRIC-01) and bootstrap intervals (M0-METRIC-02).

**Orientation, pinned (owner, 2026-10-01).** Every score is "higher =
predicted better". Φ (``phi_from_d_upper``) is used as it is. The model's
score is ``-pred_log10_ler``, column ``MODEL_SCORE`` (``with_model_score``).
The truth ranking is ascending in each row's ranking value (``ranking_value``):
``true_ler``, or ``true_ler_ub`` for a censored row (D-035, CONTRACT INV-3).

Every metric returns a ``RankingMetric``: its value, the number of censored
rows in its input, and its value with censored rows excluded (D-035).

Every entry point first checks that its input has one ``protocol_hash`` and
no null one (INV-6): rows measured under different protocols are never ranked
together.

``recall_at_k`` is not here yet: how ties at the top-n and top-k cut-offs
count is not pinned (AGENT_LOG 2026-10-01 (zz)).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from qecscreen.protocol import assert_single_protocol

__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "MODEL_SCORE",
    "PHI_SCORE",
    "BootstrapComparison",
    "Interval",
    "RankingMetric",
    "bootstrap_compare",
    "ranking_value",
    "spearman",
    "with_model_score",
]

BOOTSTRAP_RESAMPLES = 1_000  # tasks.md M0-METRIC-02
MODEL_SCORE = "pred_score"  # -pred_log10_ler: a prediction, so pred_-prefixed (INV-1)
PHI_SCORE = "phi_from_d_upper"


@dataclass(frozen=True)
class RankingMetric:
    """A metric's value, the censored rows it ranked, and its value without them (D-035).

    ``value_censored_excluded`` is null when the metric is undefined on the
    non-censored rows alone (fewer than two, or a constant column).
    """

    value: float
    n_censored: int
    value_censored_excluded: float | None


def _check_protocol(frame: pd.DataFrame) -> str:
    """INV-6: one ``protocol_hash``, and none null (a null set of hashes would pass as one)."""
    hashes = frame["protocol_hash"]
    if hashes.isna().any():
        raise ValueError("a row has a null protocol_hash; it cannot be ranked (CONTRACT INV-6)")
    return assert_single_protocol(hashes)


def ranking_value(frame: pd.DataFrame) -> pd.Series:
    """The truth ranking's key, ascending = better: ``true_ler``, or ``true_ler_ub`` if censored (D-035).

    Refuses a row that breaks INV-3's shape: a censored row with a non-null
    ``true_ler`` or no finite ``true_ler_ub``, a non-censored row without a
    finite ``true_ler``.
    """
    censored = frame["censored"]
    if censored.isna().any() or censored.dtype != bool:
        raise ValueError("censored must be a non-null bool column (INV-3)")
    ler = frame["true_ler"].astype("float64")
    ub = frame["true_ler_ub"].astype("float64")
    if ler[censored].notna().any():
        raise ValueError("a censored row has a true_ler; INV-3 stores it as null")
    if not np.isfinite(ub[censored]).all():
        raise ValueError("a censored row has no finite true_ler_ub to rank by (D-035)")
    if not np.isfinite(ler[~censored]).all():
        raise ValueError("a non-censored row has no finite true_ler")
    return ler.where(~censored, ub)


def with_model_score(frame: pd.DataFrame) -> pd.DataFrame:
    """``frame`` with ``MODEL_SCORE`` = ``-pred_log10_ler``: higher = predicted better."""
    return frame.assign(**{MODEL_SCORE: -frame["pred_log10_ler"].astype("float64")})


def _score(frame: pd.DataFrame, score_col: str) -> np.ndarray:
    score = frame[score_col].to_numpy(dtype="float64")
    if not np.isfinite(score).all():
        raise ValueError(f"{score_col} has a null or non-finite score")
    return score


def _spearman_rho(truth: np.ndarray, score: np.ndarray) -> float | None:
    """Spearman's rho between ``score`` and ``-truth``: Pearson on average ranks; null if undefined."""
    if len(truth) < 2:
        return None
    a, b = rankdata(score), rankdata(-truth)
    a, b = a - a.mean(), b - b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    if denom == 0:
        return None
    return float((a * b).sum() / denom)


def spearman(frame: pd.DataFrame, score_col: str) -> RankingMetric:
    """Spearman's rho between ``score_col`` and the negated ranking value; 1 = the true order.

    Ties take average ranks (scipy's ``rankdata``), on both sides. Raises if
    rho is undefined on the whole frame (fewer than two rows, or a constant
    score or truth).
    """
    _check_protocol(frame)
    truth = ranking_value(frame).to_numpy()
    score = _score(frame, score_col)
    rho = _spearman_rho(truth, score)
    if rho is None:
        raise ValueError(f"Spearman is undefined on these {len(frame)} rows (too few, or a constant column)")
    kept = ~frame["censored"].to_numpy()
    return RankingMetric(
        value=rho,
        n_censored=int((~kept).sum()),
        value_censored_excluded=_spearman_rho(truth[kept], score[kept]),
    )


@dataclass(frozen=True)
class Interval:
    """A point estimate on the full frame and its percentile bootstrap 95% interval."""

    estimate: float
    low: float
    high: float


@dataclass(frozen=True)
class BootstrapComparison:
    """The model, Φ, and the paired difference model − Φ, each with its interval.

    ``model_metric`` and ``phi_metric`` are the full-frame metrics, with their
    censored counts and censored-excluded values (D-035).
    """

    model: Interval
    phi: Interval
    difference: Interval
    model_metric: RankingMetric
    phi_metric: RankingMetric
    n_resamples: int
    seed: int


def bootstrap_compare(
    frame: pd.DataFrame,
    metric: Callable[[pd.DataFrame, str], RankingMetric],
    *,
    seed: int,
    model_col: str = MODEL_SCORE,
    phi_col: str = PHI_SCORE,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
) -> BootstrapComparison:
    """Percentile bootstrap 95% intervals for ``metric`` of the model, of Φ, and of model − Φ.

    Each resample draws ``len(frame)`` codes (rows) with replacement, from
    ``numpy.random.default_rng(seed)``, and evaluates both scores on the same
    draw, so the difference is paired: its interval is the M0 question. The
    interval is the 2.5th and 97.5th percentiles of the resampled values
    (``numpy.percentile``, linear). A resample on which the metric is
    undefined raises rather than being dropped.
    """
    _check_protocol(frame)
    if n_resamples < 1:
        raise ValueError(f"n_resamples must be >= 1; got {n_resamples}")
    model_metric, phi_metric = metric(frame, model_col), metric(frame, phi_col)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(frame), size=(n_resamples, len(frame)))
    model_values = np.empty(n_resamples)
    phi_values = np.empty(n_resamples)
    for i, rows in enumerate(draws):
        sample = frame.iloc[rows]
        model_values[i] = metric(sample, model_col).value
        phi_values[i] = metric(sample, phi_col).value

    def interval(estimate: float, values: np.ndarray) -> Interval:
        low, high = np.percentile(values, [2.5, 97.5])
        return Interval(estimate=estimate, low=float(low), high=float(high))

    return BootstrapComparison(
        model=interval(model_metric.value, model_values),
        phi=interval(phi_metric.value, phi_values),
        difference=interval(model_metric.value - phi_metric.value, model_values - phi_values),
        model_metric=model_metric,
        phi_metric=phi_metric,
        n_resamples=n_resamples,
        seed=seed,
    )
