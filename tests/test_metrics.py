"""Ranking metrics on synthetic frames (M0-METRIC-01/02, D-035, INV-6)."""

import itertools
import math

import numpy as np
import pandas as pd
import pytest

from qecscreen import metrics
from qecscreen.metrics import (
    MODEL_SCORE,
    bootstrap_compare,
    ranking_value,
    recall_at_k,
    spearman,
    with_model_score,
)

HASH = "a" * 64


def _frame(n=20, censored=(), seed=0):
    """``n`` codes with distinct true LERs, best first; rows in ``censored`` are censored.

    A censored row keeps its place in the truth order through ``true_ler_ub``
    (its ``true_ler`` is null, INV-3). ``perfect`` scores the true order,
    ``reversed`` its opposite; ``pred_log10_ler`` is the model's perfect prediction.
    """
    rng = np.random.default_rng(seed)
    ler = np.sort(rng.uniform(1e-4, 1e-2, n))
    is_censored = np.isin(np.arange(n), list(censored))
    frame = pd.DataFrame({
        "code_id": [f"c{i:03d}" for i in range(n)],
        "protocol_hash": HASH,
        "censored": is_censored,
        "true_ler": np.where(is_censored, np.nan, ler),
        "true_ler_ub": np.where(is_censored, ler, ler * 1.2),
        "pred_log10_ler": np.log10(ler),
        "phi_from_d_upper": -ler,
    })
    frame["perfect"] = -ler
    frame["reversed"] = ler
    return frame.sample(frac=1, random_state=seed).reset_index(drop=True)  # order must not matter


def test_ranking_value_is_true_ler_or_the_upper_bound_when_censored():
    frame = _frame(censored=(0, 5))
    value = ranking_value(frame)
    c = frame["censored"]
    assert (value[~c] == frame["true_ler"][~c]).all()
    assert (value[c] == frame["true_ler_ub"][c]).all()


def test_perfect_scorer_gives_rho_one_and_reversed_minus_one():
    frame = _frame()
    assert math.isclose(spearman(frame, "perfect").value, 1.0, rel_tol=1e-12)
    assert math.isclose(spearman(frame, "reversed").value, -1.0, rel_tol=1e-12)


def test_the_model_score_is_minus_pred_log10_ler():
    frame = with_model_score(_frame())
    assert (frame[MODEL_SCORE] == -frame["pred_log10_ler"]).all()
    assert math.isclose(spearman(frame, MODEL_SCORE).value, 1.0, rel_tol=1e-12)


def test_a_censored_row_ranks_by_its_upper_bound_not_at_the_bottom():
    """The best code is censored (D-035): a scorer that ranks it first is perfect."""
    frame = _frame(censored=(0,))
    best = frame["censored"]
    assert ranking_value(frame)[best].iloc[0] == ranking_value(frame).min()
    assert math.isclose(spearman(frame, "perfect").value, 1.0, rel_tol=1e-12)
    at_bottom = frame["perfect"].where(~best, frame["perfect"].min() - 1)
    assert spearman(frame.assign(at_bottom=at_bottom), "at_bottom").value < 0.95


def test_censored_count_and_the_censored_excluded_value():
    frame = _frame(censored=(0, 1, 2))
    # A scorer perfect on the non-censored rows, and wrong on the censored ones.
    wrong = frame["perfect"].copy()
    wrong[frame["censored"]] = frame["perfect"].min() - np.arange(1, 4)
    result = spearman(frame.assign(wrong=wrong), "wrong")
    assert result.n_censored == 3
    assert math.isclose(result.value_censored_excluded, 1.0, rel_tol=1e-12)
    assert result.value < 0.9
    none = spearman(_frame(), "perfect")
    assert none.n_censored == 0 and none.value_censored_excluded == none.value


def test_the_censored_excluded_value_is_null_when_undefined():
    result = spearman(_frame(n=5, censored=(0, 1, 2, 3)), "perfect")
    assert result.n_censored == 4 and result.value_censored_excluded is None


@pytest.mark.parametrize("bad", ["censored_with_ler", "censored_without_ub", "point_without_ler", "null_score"])
def test_rows_that_break_inv3s_shape_are_refused(bad):
    frame = _frame(censored=(0,))
    c = frame.index[frame["censored"]][0]
    p = frame.index[~frame["censored"]][0]
    if bad == "censored_with_ler":
        frame.loc[c, "true_ler"] = 1e-3
    elif bad == "censored_without_ub":
        frame.loc[c, "true_ler_ub"] = np.nan
    elif bad == "point_without_ler":
        frame.loc[p, "true_ler"] = np.nan
    else:
        frame.loc[p, "perfect"] = np.nan
    with pytest.raises(ValueError):
        spearman(frame, "perfect")


def _mixed(frame):
    frame = frame.copy()
    frame.loc[0, "protocol_hash"] = "b" * 64
    return frame


def _null_hash(frame):
    frame = frame.copy()
    frame["protocol_hash"] = None
    return frame


ENTRY_POINTS = {
    "spearman": lambda f: spearman(f, "perfect"),
    "recall_at_k": lambda f: recall_at_k(f, "perfect", k=5, top_n=2),
    "bootstrap_compare": lambda f: bootstrap_compare(
        f, spearman, seed=1, model_col="perfect", phi_col="reversed", n_resamples=5),
}


@pytest.mark.parametrize("name", list(ENTRY_POINTS))
def test_single_protocol_guard_every_ranking_entry_point_raises_on_a_mixed_hash_frame(name):
    """INV-6-T: every public ranking entry point refuses a frame with two protocol hashes."""
    with pytest.raises(ValueError, match="distinct protocols"):
        ENTRY_POINTS[name](_mixed(_frame()))


@pytest.mark.parametrize("name", list(ENTRY_POINTS))
def test_every_ranking_entry_point_raises_on_null_hashes(name):
    with pytest.raises(ValueError, match="null protocol_hash"):
        ENTRY_POINTS[name](_null_hash(_frame()))


def test_every_public_ranking_function_is_a_guarded_entry_point():
    """A new public metric must be added to ENTRY_POINTS, so the two guard tests cover it."""
    helpers = {"ranking_value", "with_model_score"}
    public = {name for name in metrics.__all__ if callable(getattr(metrics, name))
              and not isinstance(getattr(metrics, name), type)}
    assert public - helpers == set(ENTRY_POINTS)


def test_bootstrap_defaults_to_1000_resamples_and_is_deterministic_in_its_seed():
    frame = _frame(n=30, censored=(3,), seed=4)
    noisy = frame["perfect"] + np.random.default_rng(9).normal(0, 2e-3, len(frame))
    frame = frame.assign(noisy=noisy)
    import inspect

    assert inspect.signature(bootstrap_compare).parameters["n_resamples"].default == 1000
    kw = dict(model_col="noisy", phi_col="reversed", n_resamples=200)
    first = bootstrap_compare(frame, spearman, seed=20261001, **kw)
    again = bootstrap_compare(frame, spearman, seed=20261001, **kw)
    other = bootstrap_compare(frame, spearman, seed=20261002, **kw)
    assert first.n_resamples == 200 and first.seed == 20261001
    assert first == again
    assert (other.model.low, other.model.high) != (first.model.low, first.model.high)
    assert first.model.low <= first.model.estimate <= first.model.high


def test_bootstrap_difference_is_paired_model_minus_phi():
    """Perfect model, reversed Φ: rho is 1 and -1 on every resample, so the difference is exactly 2."""
    frame = with_model_score(_frame(n=25, censored=(0, 7)))
    result = bootstrap_compare(frame.assign(phi_from_d_upper=frame["reversed"]), spearman, seed=3, n_resamples=200)
    assert (result.model.low, result.model.estimate, result.model.high) == pytest.approx((1, 1, 1))
    assert (result.phi.low, result.phi.estimate, result.phi.high) == pytest.approx((-1, -1, -1))
    assert (result.difference.low, result.difference.estimate, result.difference.high) == pytest.approx((2, 2, 2))
    assert result.model_metric.n_censored == result.phi_metric.n_censored == 2
    assert result.model_metric.value_censored_excluded == pytest.approx(1)


def test_bootstrap_intervals_are_the_percentiles_of_resampled_codes():
    """Recomputed by hand from the same generator: draws of row positions, 2.5th/97.5th percentiles."""
    frame = _frame(n=15, seed=2)
    frame = frame.assign(noisy=frame["perfect"] + np.random.default_rng(5).normal(0, 3e-3, len(frame)))
    result = bootstrap_compare(frame, spearman, seed=11, model_col="noisy", phi_col="perfect", n_resamples=200)
    draws = np.random.default_rng(11).integers(0, len(frame), size=(200, len(frame)))
    model = np.array([spearman(frame.iloc[d], "noisy").value for d in draws])
    phi = np.array([spearman(frame.iloc[d], "perfect").value for d in draws])
    assert [result.model.low, result.model.high] == pytest.approx(list(np.percentile(model, [2.5, 97.5])))
    assert [result.difference.low, result.difference.high] == pytest.approx(
        list(np.percentile(model - phi, [2.5, 97.5])))


# --- recall_at_k (expected recall under uniformly random tie-breaking, owner 2026-10-01) ---


def test_recall_perfect_scorer_is_one():
    frame = _frame(n=50, censored=(0, 3))
    assert recall_at_k(frame, "perfect").value == 1.0
    assert recall_at_k(with_model_score(frame), MODEL_SCORE).value == 1.0


@pytest.mark.parametrize("n", [40, 41, 60])
def test_recall_reversed_scorer_is_zero_when_n_is_at_least_40(n):
    assert recall_at_k(_frame(n=n), "reversed").value == 0.0


def test_recall_below_40_rows_the_reversed_top_30_reaches_the_true_top_10():
    assert recall_at_k(_frame(n=39), "reversed").value == pytest.approx(0.1)


def _tied_example():
    """Truth [1, 2, 2, 3, 4] and score [10, 5, 5, 5, 1] for rows a..e, top_n = 2, k = 3.

    True top-2: a surely, b and c each 1/2 (one slot, a tie of two). Score
    top-3: a surely, b, c and d each 2/3 (two slots, a tie of three).
    Expected recall = (1·1 + ½·⅔ + ½·⅔) / 2 = 5/6.
    """
    truth = [1e-4, 2e-4, 2e-4, 3e-4, 4e-4]
    return pd.DataFrame({
        "code_id": list("abcde"),
        "protocol_hash": HASH,
        "censored": False,
        "true_ler": truth,
        "true_ler_ub": [2 * t for t in truth],
        "score": [10.0, 5.0, 5.0, 5.0, 1.0],
    })


def test_recall_with_a_tie_at_each_cut_off_is_the_known_fraction():
    assert recall_at_k(_tied_example(), "score", k=3, top_n=2).value == pytest.approx(5 / 6, rel=1e-12)


def test_recall_equals_the_average_over_every_tie_breaking_order():
    """Brute force: average |top-2 ∩ top-3| / 2 over every strict order consistent with the ties."""
    frame = _tied_example()
    truth, score = frame["true_ler"].to_numpy(), frame["score"].to_numpy()
    rows = range(len(frame))
    total = count = 0
    for t_perm in itertools.permutations(rows):
        if any(truth[a] > truth[b] for a, b in zip(t_perm, t_perm[1:])):
            continue
        for s_perm in itertools.permutations(rows):
            if any(score[a] < score[b] for a, b in zip(s_perm, s_perm[1:])):
                continue
            total += len(set(t_perm[:2]) & set(s_perm[:3])) / 2
            count += 1
    assert recall_at_k(frame, "score", k=3, top_n=2).value == pytest.approx(total / count, rel=1e-12)


def test_recall_is_invariant_under_row_order():
    frame = _frame(n=60, censored=(2, 9), seed=7)
    coarse = np.round(frame["perfect"] * 300) + np.random.default_rng(1).integers(0, 2, len(frame))
    frame = frame.assign(coarse=coarse)  # Φ-like: few distinct values, ties at both cut-offs
    expected = recall_at_k(frame, "coarse")
    for seed in range(5):
        shuffled = frame.sample(frac=1, random_state=seed).reset_index(drop=True)
        assert recall_at_k(shuffled, "coarse") == pytest.approx(expected)
        assert recall_at_k(shuffled.set_index("code_id"), "coarse") == pytest.approx(expected)
    assert 0 < expected.value < 1


def test_recall_censored_count_and_the_censored_excluded_value():
    frame = _frame(n=50, censored=(0, 1))
    # Perfect on the non-censored rows; the two best (censored) codes ranked last.
    wrong = frame["perfect"].where(~frame["censored"], frame["perfect"].min() - 1)
    result = recall_at_k(frame.assign(wrong=wrong), "wrong")
    assert result.n_censored == 2
    assert result.value == pytest.approx(0.8)
    assert result.value_censored_excluded == 1.0


def test_recall_is_undefined_below_k_rows():
    with pytest.raises(ValueError, match="undefined"):
        recall_at_k(_frame(n=29), "perfect")
    result = recall_at_k(_frame(n=35, censored=tuple(range(10))), "perfect")
    assert result.n_censored == 10 and result.value_censored_excluded is None


def test_recall_plugs_into_bootstrap_compare():
    """Perfect model, reversed Φ, 60 codes: recall 1 and 0 on every resample, so the difference is exactly 1."""
    frame = with_model_score(_frame(n=60, censored=(4,)))
    frame = frame.assign(phi_from_d_upper=frame["reversed"])
    result = bootstrap_compare(frame, recall_at_k, seed=5, n_resamples=200)
    assert (result.model.low, result.model.estimate, result.model.high) == pytest.approx((1, 1, 1))
    assert (result.phi.low, result.phi.estimate, result.phi.high) == pytest.approx((0, 0, 0))
    assert (result.difference.low, result.difference.estimate, result.difference.high) == pytest.approx((1, 1, 1))
    assert result.model_metric.n_censored == 1
    again = bootstrap_compare(frame, recall_at_k, seed=5, n_resamples=200)
    assert again == result
