"""Golden-value tests for the frozen protocol (spec/evals.md G-01..G-06).

These are deterministic arithmetic, so they are asserted tightly. If one of
these fails, every label in the dataset is suspect.
"""

import math

import pytest

from qecscreen.protocol import (
    Protocol,
    assert_single_protocol,
    is_censored,
    logical_error_rate,
    protocol_hash,
    wilson_interval,
)

REL = 1e-12


@pytest.mark.parametrize(
    "p_fail,rounds,k,expected",
    [
        (0.5, 12, 12, 0.004801955655646228),   # G-01
        (0.01, 6, 6, 0.0002791370299384255),   # G-02
        (0.25, 4, 2, 0.0353213700396906),      # G-03
        (0.0, 12, 12, 0.0),                    # G-04
    ],
)
def test_ler_formula_golden(p_fail, rounds, k, expected):
    assert math.isclose(logical_error_rate(p_fail, rounds, k), expected, rel_tol=REL)


@pytest.mark.parametrize(
    "failures,shots,expected",
    [
        (100, 10000, (0.008229336148148417, 0.012146982255114645)),  # G-05
        (1, 1000, (0.00017654637062607809, 0.0056425585979579355)),  # G-06
    ],
)
def test_wilson_golden(failures, shots, expected):
    low, high = wilson_interval(failures, shots)
    assert math.isclose(low, expected[0], rel_tol=REL)
    assert math.isclose(high, expected[1], rel_tol=REL)


def test_n05_total_failure_raises():
    """N-05: p_fail == 1.0 means a malformed circuit, not a rate of 1.0."""
    with pytest.raises(ValueError):
        logical_error_rate(1.0, 12, 12)


def test_ler_rejects_bad_arguments():
    with pytest.raises(ValueError):
        logical_error_rate(-0.1, 12, 12)
    with pytest.raises(ValueError):
        logical_error_rate(0.1, 0, 12)
    with pytest.raises(ValueError):
        logical_error_rate(0.1, 12, 0)


def test_inv3_censoring_threshold():
    assert is_censored(99) is True
    assert is_censored(100) is False


def test_wilson_lower_bound_never_negative():
    """The reason we use Wilson rather than the normal approximation."""
    low, _ = wilson_interval(0, 200_000)
    assert low >= 0.0


def test_inv6_single_protocol_guard():
    """N-02: refuse to combine rows from two protocols."""
    a = Protocol(p=0.005, rounds=6).hash()
    b = Protocol(p=0.010, rounds=6).hash()
    assert a != b
    assert assert_single_protocol([a, a, a]) == a
    with pytest.raises(ValueError):
        assert_single_protocol([a, b])
    with pytest.raises(ValueError):
        assert_single_protocol([])


def test_protocol_hash_is_stable():
    assert Protocol(p=0.005, rounds=6).hash() == Protocol(p=0.005, rounds=6).hash()


def test_protocol_hash_function_matches_the_method():
    """One implementation, two names — the column is called protocol_hash."""
    import qecscreen.protocol as module

    proto = Protocol(p=0.005, rounds=6)
    assert protocol_hash(proto) == proto.hash()
    assert "protocol_hash" in module.__all__
    assert "is_censored" in module.__all__
