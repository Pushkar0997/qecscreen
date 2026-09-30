"""Golden-value tests for the frozen protocol (spec/evals.md G-01..G-06).

These are deterministic arithmetic, so they are asserted tightly. If one of
these fails, every label in the dataset is suspect.
"""

import math

import pandas as pd
import pytest

from qecscreen.protocol import (
    DECODER_PARAMS,
    MAX_SHOTS,
    MEMORY_BASIS,
    P_PILOT,
    SHOT_BATCH,
    ROUNDS_RULE,
    SCHEDULING,
    Protocol,
    assert_single_protocol,
    installed_decoder_version,
    is_censored,
    logical_error_rate,
    protocol_hash,
    sampling_seed,
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


@pytest.mark.parametrize("shots", [1, 2, 21, 37, 100, 1_000, 10_000, 123_457, 200_000])
def test_d026_wilson_clamped_at_zero_failures(shots):
    """D-026: the unclamped formula returns ~-1e-18 at 0 failures for some
    shots (21 is the first), which logical_error_rate rejects."""
    low, high = wilson_interval(0, shots)
    assert low >= 0.0
    assert 0.0 < high <= 1.0
    logical_error_rate(low, 6, 12)  # must not raise


def test_d026_wilson_residue_case_is_exactly_zero():
    """shots=21 is the first n whose unclamped lower bound is negative."""
    assert wilson_interval(0, 21)[0] == 0.0


@pytest.mark.parametrize("shots", [1, 21, 1_000, 200_000])
def test_d026_wilson_clamped_at_all_failures(shots):
    low, high = wilson_interval(shots, shots)
    assert 0.0 <= low < 1.0
    assert high <= 1.0


def test_d026_p_pilot_exported():
    import qecscreen.protocol as module

    assert P_PILOT == 0.002  # CONTRACT.md exact values; D-031 (supersedes D-016)
    assert "P_PILOT" in module.__all__


def test_d031_shot_cap_is_a_whole_number_of_batches():
    """CONTRACT: batches of exactly SHOT_BATCH, and MAX_SHOTS a hard cap. Both
    hold only if the cap is a whole number of batches; 10,000 over 256 was not."""
    assert (MAX_SHOTS, SHOT_BATCH) == (40_960, 256)  # CONTRACT.md exact values; D-031, D-034
    assert MAX_SHOTS % SHOT_BATCH == 0


def test_d026_label_changing_decoder_settings_are_pinned():
    assert DECODER_PARAMS["schedule"] == "parallel"
    assert DECODER_PARAMS["dem_to_matrix"] == "dem_undecomposed_merge_by_symptom_v1"


@pytest.mark.parametrize(
    "key, other",
    [("schedule", "serial"), ("dem_to_matrix", "dem_undecomposed_one_column_per_instruction_v1")],
)
def test_d026_decoder_settings_enter_the_hash(monkeypatch, key, other):
    before = _protocol().hash()
    monkeypatch.setitem(DECODER_PARAMS, key, other)
    assert _protocol().hash() != before


def test_single_protocol_guard():
    """INV-6-T, N-02: refuse to combine rows from two protocols. CONTRACT INV-6 names this test."""
    a = _protocol(p=0.005).hash()
    b = _protocol(p=0.010).hash()
    assert a != b
    assert assert_single_protocol([a, a, a]) == a
    with pytest.raises(ValueError):
        assert_single_protocol([a, b])
    with pytest.raises(ValueError):
        assert_single_protocol([])


def test_single_protocol_guard_on_a_dataframe_column():
    """INV-6-T on the input it guards in use: a frame's ``protocol_hash`` column (M0-EVAL-03)."""
    a = _protocol(p=0.005).hash()
    b = _protocol(p=0.010).hash()
    single = pd.DataFrame({"code_id": ["c0", "c1", "c2"], "protocol_hash": [a, a, a]})
    assert assert_single_protocol(single["protocol_hash"]) == a
    mixed = pd.DataFrame({"code_id": ["c0", "c1", "c2"], "protocol_hash": [a, b, a]})
    with pytest.raises(ValueError, match="2 distinct protocols"):
        assert_single_protocol(mixed["protocol_hash"])
    with pytest.raises(ValueError):
        assert_single_protocol(single.iloc[0:0]["protocol_hash"])


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


# --- D-025: circuit protocol v1 ------------------------------------------------


def test_d025_memory_basis_is_z_and_in_the_hash():
    """The label is a Z-memory LER; an X-memory row is a different protocol."""
    assert MEMORY_BASIS == "Z"
    assert _protocol().memory_basis == "Z"
    assert _protocol().hash() != _protocol(memory_basis="X").hash()


def test_d025_scheduling_string_is_pinned_and_in_the_hash():
    assert SCHEDULING == "bb_monomial_matching_xz_phased_v2"
    assert _protocol().hash() != _protocol(scheduling="tanner_edge_colouring_v1").hash()
    # The pre-amendment ancilla timing (D-025 amendment) is a different protocol.
    assert _protocol().hash() != _protocol(scheduling="bb_monomial_matching_xz_phased_v1").hash()


def test_inv6_decoder_version_is_required_and_real():
    """A hash that omits the version it claims to carry is worse than no hash."""
    with pytest.raises(TypeError):
        Protocol(p=0.005)  # type: ignore[call-arg]  # decoder_version has no default any more
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


# --- D-027: the sampling seed is derived from the row, never chosen ----------

SEED_CODE_ID = "bb_v1_ref-0123456789ab"
SEED_HASH = "a" * 64
# sha256("bb_v1_ref-0123456789ab|" + "a" * 64), first 8 bytes big-endian,
# masked to 63 bits. Recomputed independently below from the hex digest.
SEED_GOLDEN = 6435667380748351026


def test_d027_sampling_seed_golden():
    assert sampling_seed(SEED_CODE_ID, SEED_HASH) == SEED_GOLDEN


def test_d027_sampling_seed_matches_an_independent_derivation():
    import hashlib

    for code_id in (SEED_CODE_ID, "bb_v1_tri_3_3-ffffffffffff", "x"):
        h = protocol_hash(_protocol())
        hexdigest = hashlib.sha256(f"{code_id}|{h}".encode()).hexdigest()
        assert sampling_seed(code_id, h) == int(hexdigest[:16], 16) % 2**63


def test_d027_sampling_seed_is_stable():
    h = protocol_hash(_protocol())
    assert sampling_seed(SEED_CODE_ID, h) == sampling_seed(SEED_CODE_ID, h)


def test_d027_sampling_seed_changes_with_code_id():
    h = protocol_hash(_protocol())
    assert sampling_seed(SEED_CODE_ID, h) != sampling_seed("bb_v1_ref-0123456789ac", h)


def test_d027_sampling_seed_changes_with_protocol_hash():
    h1 = protocol_hash(_protocol(p=0.005))
    h2 = protocol_hash(_protocol(p=0.004))
    assert h1 != h2
    assert sampling_seed(SEED_CODE_ID, h1) != sampling_seed(SEED_CODE_ID, h2)


def test_d027_sampling_seed_fits_int64_and_seeds_stim():
    import stim

    seeds = [sampling_seed(f"bb_v1_t-{i:012x}", SEED_HASH) for i in range(2000)]
    assert all(0 <= s < 2**63 for s in seeds)
    assert max(seeds) >= 2**62  # the mask keeps 63 bits, it does not truncate to 32
    stim.Circuit("M 0").compile_detector_sampler(seed=max(seeds))


@pytest.mark.parametrize(
    "code_id,h",
    [
        ("", SEED_HASH),
        (None, SEED_HASH),
        (SEED_CODE_ID, ""),
        (SEED_CODE_ID, "A" * 64),   # uppercase: not what protocol_hash() returns
        (SEED_CODE_ID, "a" * 63),
        (SEED_CODE_ID, 12345),
    ],
)
def test_d027_sampling_seed_rejects_bad_inputs(code_id, h):
    with pytest.raises(ValueError):
        sampling_seed(code_id, h)
