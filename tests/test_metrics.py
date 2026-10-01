"""Ranking metrics on synthetic frames (M0-METRIC-01/02, D-035, INV-6)."""

import math

import numpy as np
import pandas as pd
import pytest

from qecscreen import metrics
from qecscreen.metrics import MODEL_SCORE, ranking_value, spearman, with_model_score

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
