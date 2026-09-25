"""M0-CODES-05: sample_bb_params tests.

INV-2's grouping key is construction_program_id, so the specific thing this
file guards is that two codes from the same polynomial template always
share an id and two codes from different templates never do - getting that
wrong is the exact failure mode that makes a split-based score meaningless
(spec/decisions.md D-022 has the diversity measurement this file assumes).

Checking ids alone is not enough: D-024 found two pairs of templates that
were the same construction program under different ids, and one template
whose every code had d <= 2, while every id-level test here passed. So the
template tests below generate the codes and compare them.
"""

import itertools

import numpy as np
import pytest

from qecscreen.codes.bb import generate
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.codes.sample import MIN_D_UPPER, TEMPLATES, sample_bb_params, template_key
from qecscreen.codes.validate import validate
from qecscreen.linalg import gf2_rank

BUDGET = 150


# Every test using this fixture, and every test drawing >= 30 admitted codes, is
# marked slow: admission runs estimate_d_upper per candidate (D-024), so these
# dominate the suite. The default local run skips them; CI runs them all.
@pytest.fixture(scope="module")
def balanced_300():
    return sample_bb_params(300, BUDGET, seed=0, balanced=True)


def _same_rowspace(a: np.ndarray, b: np.ndarray) -> bool:
    r = gf2_rank(a)
    return r == gf2_rank(b) and gf2_rank(np.vstack([a, b])) == r


def _swap_halves(h: np.ndarray) -> np.ndarray:
    half = h.shape[1] // 2
    return np.hstack([h[:, half:], h[:, :half]])


# --- template set (D-024): the codes, not the ids ---------------------------


def test_no_two_templates_are_ab_swaps_of_each_other():
    """Swapping A and B gives the same code with the two qubit halves
    exchanged. l, m exceed every template exponent but 7, so distinct
    monomials stay distinct almost everywhere and a collision is not an
    artefact of wraparound."""
    l, m = 8, 9
    codes = {name: generate(l, m, a, b, seed=0) for name, a, b in TEMPLATES}
    for (n1, (hx1, hz1)), (n2, (hx2, hz2)) in itertools.combinations(codes.items(), 2):
        for hx, hz in [(hx2, hz2), (_swap_halves(hx2), _swap_halves(hz2))]:
            assert not (_same_rowspace(hx1, hx) and _same_rowspace(hz1, hz)), (n1, n2)


def test_template_keys_are_unique():
    """Also covers per-polynomial monomial shifts, which the lattice test above does not."""
    keys = [template_key(a, b) for _, a, b in TEMPLATES]
    assert len(keys) == len(set(keys))


def test_no_template_has_a_equal_to_b():
    """A == B (or A a monomial shift of B) gives d <= 2 whenever k >= 1."""
    for name, a, b in TEMPLATES:
        ka, kb = template_key(a, a), template_key(b, b)
        assert ka != kb, name


def test_template_names_are_unique():
    names = [name for name, _, _ in TEMPLATES]
    assert len(names) == len(set(names))


# --- sampler output -------------------------------------------------------


@pytest.mark.slow
def test_every_emitted_code_is_admissible(balanced_300):
    for p in balanced_300:
        assert 2 * p["l"] * p["m"] <= BUDGET
        h_x, h_z = generate(p["l"], p["m"], p["a_exps"], p["b_exps"], seed=0)
        validate(h_x, h_z)  # raises InvalidCodeError if this code shouldn't have been emitted
        d_upper, _ = estimate_d_upper(h_x, h_z, seed=0)
        assert d_upper >= MIN_D_UPPER, p


@pytest.mark.slow
def test_unbalanced_output_is_admissible_too():
    params = sample_bb_params(30, BUDGET, seed=1, balanced=False)
    assert len(params) == 30
    assert params.quota is None and params.exhausted == ()
    for p in params:
        h_x, h_z = generate(p["l"], p["m"], p["a_exps"], p["b_exps"], seed=0)
        validate(h_x, h_z)
        assert estimate_d_upper(h_x, h_z, seed=0)[0] >= MIN_D_UPPER


@pytest.mark.slow
def test_determinism_same_args_identical_list():
    for balanced in (True, False):
        assert sample_bb_params(30, BUDGET, seed=3, balanced=balanced) == sample_bb_params(
            30, BUDGET, seed=3, balanced=balanced
        )
    assert sample_bb_params(30, BUDGET, seed=7) != sample_bb_params(30, BUDGET, seed=8)


@pytest.mark.slow
def test_at_least_eight_distinct_templates_in_a_large_sample(balanced_300):
    pids = {p["construction_program_id"] for p in balanced_300}
    assert len(pids) >= 8


@pytest.mark.slow
def test_same_template_shares_id_different_templates_never_do(balanced_300):
    by_shape: dict[tuple[tuple[int, int], ...], set[str]] = {}
    id_to_shapes: dict[str, set[tuple[tuple[int, int], ...]]] = {}
    for p in balanced_300:
        shape = (tuple(p["a_exps"]), tuple(p["b_exps"]))
        by_shape.setdefault(shape, set()).add(p["construction_program_id"])
        id_to_shapes.setdefault(p["construction_program_id"], set()).add(shape)

    # Every occurrence of the same (a_exps, b_exps) shape carries exactly one id.
    for shape, ids in by_shape.items():
        assert len(ids) == 1, f"shape {shape} produced multiple ids: {ids}"

    # No id is ever shared by two different shapes.
    for pid, shapes in id_to_shapes.items():
        assert len(shapes) == 1, f"id {pid} was used for multiple shapes: {shapes}"


@pytest.mark.slow
def test_reference_code_shape_carries_the_expected_id(balanced_300):
    """If the [[72,12,6]] shape is ever drawn, it must carry bb_v1_sym_3_3."""
    reference_a = [(3, 0), (0, 1), (0, 2)]
    reference_b = [(0, 3), (1, 0), (2, 0)]
    match = None
    for name, a_exps, b_exps in TEMPLATES:
        if a_exps == reference_a and b_exps == reference_b:
            match = name
    assert match == "sym_3_3"

    for p in balanced_300:
        if p["a_exps"] == reference_a and p["b_exps"] == reference_b:
            assert p["construction_program_id"] == "bb_v1_sym_3_3"


def test_n_codes_must_be_positive():
    with pytest.raises(ValueError):
        sample_bb_params(0, BUDGET, seed=0)


def test_budget_too_small_is_rejected():
    with pytest.raises(ValueError):
        sample_bb_params(10, budget=4, seed=0)  # can't fit even l=m=2


# --- D-023: balanced template allocation -----------------------------------


@pytest.mark.slow
def test_balanced_is_the_default():
    assert sample_bb_params(30, BUDGET, seed=0) == sample_bb_params(
        30, BUDGET, seed=0, balanced=True
    )


@pytest.mark.slow
def test_balanced_every_template_under_2x_mean_and_viable_ones_at_least_10(balanced_300):
    """Every template is viable at budget=150 (each has >= 10 distinct
    admissible (l, m) pairs, D-024), so every one must reach 10."""
    assert len(balanced_300) == 300
    counts = balanced_300.counts
    assert set(counts) == {f"bb_v1_{name}" for name, _, _ in TEMPLATES}
    mean = len(balanced_300) / len(counts)
    assert max(counts.values()) <= 2 * mean, counts
    assert min(counts.values()) >= 10, counts


@pytest.mark.slow
def test_balanced_counts_attribute_matches_the_list(balanced_300):
    tally: dict[str, int] = {}
    for p in balanced_300:
        tally[p["construction_program_id"]] = tally.get(p["construction_program_id"], 0) + 1
    assert {k: v for k, v in balanced_300.counts.items() if v} == tally
    assert sum(balanced_300.quota.values()) == 300


@pytest.mark.slow
def test_balanced_shortfall_is_redistributed_and_visible(balanced_300):
    """Templates with fewer distinct admissible pairs than their quota are
    reported as exhausted; the list is still full length, not short."""
    assert balanced_300.exhausted
    for pid in balanced_300.exhausted:
        assert balanced_300.counts[pid] < balanced_300.quota[pid]
    for pid, n in balanced_300.counts.items():
        if pid not in balanced_300.exhausted:
            assert n >= balanced_300.quota[pid]


@pytest.mark.slow
def test_balanced_codes_are_distinct(balanced_300):
    keys = [(p["construction_program_id"], p["l"], p["m"]) for p in balanced_300]
    assert len(keys) == len(set(keys))


@pytest.mark.slow
def test_rejections_are_reported_by_cause(balanced_300):
    rej = balanced_300.rejections
    assert set(rej) == {"k<1", f"d_upper<{MIN_D_UPPER}"}
    assert rej[f"d_upper<{MIN_D_UPPER}"] > 0  # the rule does reject real candidates at 150
    assert balanced_300.attempts == len(balanced_300) + sum(rej.values())


def test_balanced_raises_rather_than_returning_short():
    """budget=8 admits only l=m=2: at most one distinct code per template."""
    with pytest.raises(RuntimeError):
        sample_bb_params(len(TEMPLATES) + 1, budget=8, seed=0, balanced=True)
