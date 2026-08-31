"""Golden-value tests for the frozen protocol (spec/evals.md G-01..G-06).

These are deterministic arithmetic, so they are asserted tightly. If one of
these fails, every label in the dataset is suspect.
"""

import math

import pytest

from qecscreen.protocol import (
    ROUNDS_RULE,
    Protocol,
    assert_single_protocol,
    installed_decoder_version,
    is_censored,
    logical_error_rate,
    protocol_hash,
    wilson_interval,
)

REL = 1e-12


def _protocol(**overrides):
    """A Protocol with the required decoder_version supplied."""
    kwargs = {"p": 0.005, "decoder_version": installed_decoder_version()}
    kwargs.update(overrides)
    return Protocol(**kwargs)


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
    a = _protocol(p=0.005).hash()
    b = _protocol(p=0.010).hash()
    assert a != b
    assert assert_single_protocol([a, a, a]) == a
    with pytest.raises(ValueError):
        assert_single_protocol([a, b])
    with pytest.raises(ValueError):
        assert_single_protocol([])


def test_protocol_hash_is_stable():
    assert _protocol().hash() == _protocol().hash()


def test_protocol_hash_function_matches_the_method():
    """One implementation, two names — the column is called protocol_hash."""
    import qecscreen.protocol as module

    proto = _protocol()
    assert protocol_hash(proto) == proto.hash()
    assert "protocol_hash" in module.__all__
    assert "is_censored" in module.__all__


# --- D-014: the hash carries the rounds rule, never the value of r ----------


def test_d014_rounds_value_is_not_in_the_hash():
    """The blocker D-014 fixes.

    Under D-006 r = d_upper varies per code. If r were hashed, every distance
    would be its own protocol and assert_single_protocol would raise on every
    legitimate cross-code ranking — M0-RUN-04 could not run.
    """
    # r is not a protocol attribute at all, so it cannot leak into the hash.
    assert "rounds" not in Protocol.__dataclass_fields__

    # Three codes of different d_upper, and therefore different r, share one
    # protocol. A frame mixing them now passes the INV-6 guard instead of
    # raising, which is what M0-RUN-04 needs.
    proto = _protocol()
    rows = [
        {"d_upper": 4, "rounds": 4},
        {"d_upper": 6, "rounds": 6},
        {"d_upper": 8, "rounds": 8},
    ]
    hashes = [proto.hash() for _ in rows]
    assert len(set(hashes)) == 1
    assert assert_single_protocol(hashes) == proto.hash()


def test_d014_rounds_rule_is_in_the_hash():
    """And the other direction: a different rounds rule is a different protocol.

    Dropping rounds from the hash entirely would make a fixed-r dataset and a
    variable-r dataset hash identically despite being incomparable.
    """
    assert ROUNDS_RULE == "r = d_upper"
    assert _protocol().hash() != _protocol(rounds_rule="r = 12").hash()


def test_inv6_decoder_version_is_required_and_real():
    """A hash that omits the version it claims to carry is worse than no hash."""
    with pytest.raises(TypeError):
        Protocol(p=0.005)  # decoder_version has no default any more
    with pytest.raises(ValueError):
        Protocol(p=0.005, decoder_version="unset")
    with pytest.raises(ValueError):
        Protocol(p=0.005, decoder_version="")


def test_inv6_decoder_version_changes_the_hash():
    assert _protocol().hash() != _protocol(decoder_version="0.0.0-fake").hash()


def test_installed_decoder_version_matches_the_installed_ldpc():
    from importlib.metadata import version

    assert installed_decoder_version() == version("ldpc")


# --- p is canonicalised to 6dp before hashing --------------------------------


def test_p_canonicalised_to_6dp_same_hash():
    """Two Protocol instances with p values that differ only beyond the 6th
    decimal place must hash identically — CONTRACT says p is stored to 6dp."""
    a = _protocol(p=0.005)
    b = _protocol(p=0.0050001)
    assert a.hash() == b.hash()


def test_p_canonicalised_to_6dp_different_hash():
    """Values that differ at or before the 6th decimal place are distinct."""
    a = _protocol(p=0.005)
    b = _protocol(p=0.006)
    assert a.hash() != b.hash()
