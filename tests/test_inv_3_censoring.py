"""M0-EVAL-02: the censoring rule (INV-3) and Wilson population.

INV-3-T: every row with ``failures < 100`` has ``censored == True`` and a
null ``true_ler``; every row with ``censored == False`` has ``failures >=
100`` and finite interval bounds. N-03: 3 failures in 200,000 shots is
censored, not ``1.5e-5``.

Every rate is checked against ``qecscreen.protocol`` directly, because INV-4
allows no second implementation of the LER formula or the interval.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from qecscreen.evaluate.label import Label, make_label
from qecscreen.protocol import MAX_SHOTS, MIN_FAILURES, logical_error_rate, wilson_interval


def _label(failures: int, shots: int, rounds: int = 6, k: int = 12, p: float = 0.005) -> Label:
    return make_label(p=p, rounds=rounds, k=k, shots=shots, failures=failures, decode_seconds=1.5)


def test_censoring_rule():
    """INV-3-T over a spread of counts, including both sides of the boundary."""
    rng = np.random.default_rng(0)
    cases = [(f, s) for f, s in [(0, MAX_SHOTS), (3, MAX_SHOTS), (99, 5_000), (100, 5_000),
                                  (101, 150), (100, 100 + 1)]]
    for _ in range(200):
        shots = int(rng.integers(100, MAX_SHOTS + 1))
        cases.append((int(rng.integers(0, min(shots, 400))), shots))
    for failures, shots in cases:
        lab = _label(failures, shots)
        if failures < MIN_FAILURES:
            assert lab.censored is True
            assert lab.true_ler is None
        else:
            assert lab.censored is False
            assert lab.failures >= MIN_FAILURES
            assert math.isfinite(lab.true_ler)
            assert math.isfinite(lab.true_ler_ci_low) and math.isfinite(lab.true_ler_ci_high)
            assert lab.true_ler_ci_low <= lab.true_ler <= lab.true_ler_ci_high
        # Populated on every row, censored or not.
        assert math.isfinite(lab.true_ler_ub)
        assert lab.true_ler_ub == lab.true_ler_ci_high
        assert 0.0 <= lab.true_ler_ci_low <= lab.true_ler_ci_high < 1.0


def test_n03_three_failures_at_max_shots_is_censored_not_a_rate():
    lab = _label(3, MAX_SHOTS)
    assert lab.censored is True
    assert lab.true_ler is None  # not 3/MAX_SHOTS, nor its per-round form
    lo, hi = wilson_interval(3, MAX_SHOTS)
    assert lab.true_ler_ub == logical_error_rate(hi, 6, 12)
    assert lab.true_ler_ci_low == logical_error_rate(lo, 6, 12)


def test_boundary_is_exactly_min_failures():
    assert _label(MIN_FAILURES - 1, 10_000).censored is True
    assert _label(MIN_FAILURES, 10_000).censored is False


def test_point_estimate_and_interval_come_from_protocol():
    """Wilson on the per-shot P_L, mapped through INV-4's one formula (monotone)."""
    lab = _label(100, 10_000, rounds=12, k=12)
    lo, hi = wilson_interval(100, 10_000)
    assert lab.true_ler == logical_error_rate(100 / 10_000, 12, 12)
    assert lab.true_ler_ci_low == logical_error_rate(lo, 12, 12)
    assert lab.true_ler_ci_high == logical_error_rate(hi, 12, 12)


def test_zero_failures_gives_a_zero_lower_bound_not_an_error():
    """The unclamped Wilson formula returns ~-1e-18 at 0 failures for some n
    (e.g. 21). protocol.wilson_interval clamps it (D-026); label.py no longer
    does, so this checks the clamp reaches the label."""
    for shots in (21, 37, 100, MAX_SHOTS):
        lab = _label(0, shots)
        assert lab.true_ler_ci_low == 0.0
        assert lab.censored and lab.true_ler is None
        assert lab.true_ler_ub > 0.0


def test_every_shot_failing_raises():
    """N-05 carried through: a code that fails every shot has no per-round rate."""
    with pytest.raises(ValueError):
        _label(500, 500)


def test_fields_carry_counts_and_rounded_p():
    lab = make_label(p=0.0050000001, rounds=6, k=12, shots=10_000, failures=150, decode_seconds=2.25)
    assert lab.p == 0.005  # CONTRACT: p stored to 6 decimal places
    assert (lab.rounds, lab.k, lab.shots, lab.failures, lab.decode_seconds) == (6, 12, 10_000, 150, 2.25)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(shots=0, failures=0),
        dict(shots=100, failures=101),
        dict(shots=100, failures=-1),
        dict(shots=MAX_SHOTS + 1, failures=0),
        dict(shots=100, failures=0, rounds=0),
        dict(shots=100, failures=0, k=0),
        dict(shots=100, failures=0, decode_seconds=-1.0),
    ],
)
def test_rejects_impossible_counts(kwargs):
    args = dict(p=0.005, rounds=6, k=12, decode_seconds=0.0) | kwargs
    with pytest.raises(ValueError):
        make_label(**args)


def test_only_true_prefixed_rate_fields():
    """INV-1: every rate field is a measurement and says so."""
    names = set(Label.__dataclass_fields__)
    assert {n for n in names if "ler" in n} == {
        "true_ler", "true_ler_ub", "true_ler_ci_low", "true_ler_ci_high"
    }
    assert not any(n.startswith("pred_") for n in names)
