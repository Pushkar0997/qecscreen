"""M0-CODES-05: sample_bb_params tests.

INV-2's grouping key is construction_program_id, so the specific thing this
file guards is that two codes from the same polynomial template always
share an id and two codes from different templates never do - getting that
wrong is the exact failure mode that makes a split-based score meaningless
(spec/decisions.md D-022 has the diversity measurement this file assumes).
"""

import numpy as np
import pytest

from qecscreen.codes.bb import generate
from qecscreen.codes.sample import TEMPLATES, sample_bb_params
from qecscreen.codes.validate import InvalidCodeError, validate

BUDGET = 150


def test_determinism_same_args_identical_list():
    params_1 = sample_bb_params(50, BUDGET, seed=3)
    params_2 = sample_bb_params(50, BUDGET, seed=3)
    assert params_1 == params_2


def test_every_sample_validates_and_respects_budget():
    params = sample_bb_params(100, BUDGET, seed=1)
    assert len(params) == 100
    for p in params:
        n = 2 * p["l"] * p["m"]
        assert n <= BUDGET
        h_x, h_z = generate(p["l"], p["m"], p["a_exps"], p["b_exps"], seed=0)
        validate(h_x, h_z)  # raises InvalidCodeError if this code shouldn't have been emitted


def test_at_least_eight_distinct_templates_in_a_large_sample():
    """n_codes=400 at this budget/seed was measured (D-022) to surface all
    10 templates, comfortably above the required 8; not just barely enough."""
    params = sample_bb_params(400, BUDGET, seed=0)
    pids = {p["construction_program_id"] for p in params}
    assert len(pids) >= 8


def test_same_template_shares_id_different_templates_never_do():
    params = sample_bb_params(300, BUDGET, seed=0)
    by_shape: dict[tuple[tuple[int, int], ...], set[str]] = {}
    id_to_shapes: dict[str, set[tuple[tuple[int, int], ...]]] = {}
    for p in params:
        shape = (tuple(p["a_exps"]), tuple(p["b_exps"]))
        by_shape.setdefault(shape, set()).add(p["construction_program_id"])
        id_to_shapes.setdefault(p["construction_program_id"], set()).add(shape)

    # Every occurrence of the same (a_exps, b_exps) shape carries exactly one id.
    for shape, ids in by_shape.items():
        assert len(ids) == 1, f"shape {shape} produced multiple ids: {ids}"

    # No id is ever shared by two different shapes.
    for pid, shapes in id_to_shapes.items():
        assert len(shapes) == 1, f"id {pid} was used for multiple shapes: {shapes}"


def test_reference_code_shape_carries_the_expected_id():
    """If the [[72,12,6]] shape is ever drawn, it must carry bb_v1_sym_3_3."""
    reference_a = [(3, 0), (0, 1), (0, 2)]
    reference_b = [(0, 3), (1, 0), (2, 0)]
    match = None
    for name, a_exps, b_exps in TEMPLATES:
        if a_exps == reference_a and b_exps == reference_b:
            match = name
    assert match == "sym_3_3"

    params = sample_bb_params(400, BUDGET, seed=0)
    for p in params:
        if p["a_exps"] == reference_a and p["b_exps"] == reference_b:
            assert p["construction_program_id"] == "bb_v1_sym_3_3"


def test_n_codes_must_be_positive():
    with pytest.raises(ValueError):
        sample_bb_params(0, BUDGET, seed=0)


def test_budget_too_small_is_rejected():
    with pytest.raises(ValueError):
        sample_bb_params(10, budget=4, seed=0)  # can't fit even l=m=2


# --- D-023: balanced template allocation -----------------------------------


@pytest.fixture(scope="module")
def balanced_300():
    return sample_bb_params(300, BUDGET, seed=0, balanced=True)


def test_balanced_is_the_default(balanced_300):
    assert sample_bb_params(300, BUDGET, seed=0) == balanced_300


def test_balanced_every_template_under_2x_mean_and_viable_ones_at_least_10(balanced_300):
    """All 10 templates are viable at budget=150 (each has >= 17 distinct
    valid (l, m) pairs, D-023), so every one must reach 10."""
    assert len(balanced_300) == 300
    counts = balanced_300.counts
    assert set(counts) == {f"bb_v1_{name}" for name, _, _ in TEMPLATES}
    mean = len(balanced_300) / len(counts)
    assert max(counts.values()) <= 2 * mean, counts
    assert min(counts.values()) >= 10, counts


def test_balanced_counts_attribute_matches_the_list(balanced_300):
    tally: dict[str, int] = {}
    for p in balanced_300:
        tally[p["construction_program_id"]] = tally.get(p["construction_program_id"], 0) + 1
    assert {k: v for k, v in balanced_300.counts.items() if v} == tally
    assert sum(balanced_300.quota.values()) == 300


def test_balanced_shortfall_is_redistributed_and_visible(balanced_300):
    """Templates with fewer distinct valid pairs than their quota of 30 are
    reported as exhausted; the list is still full length, not short."""
    assert balanced_300.exhausted  # five templates have only 17-20 valid pairs at 150
    for pid in balanced_300.exhausted:
        assert balanced_300.counts[pid] < balanced_300.quota[pid]
    for pid, n in balanced_300.counts.items():
        if pid not in balanced_300.exhausted:
            assert n >= balanced_300.quota[pid]


def test_balanced_codes_are_distinct(balanced_300):
    keys = [(p["construction_program_id"], p["l"], p["m"]) for p in balanced_300]
    assert len(keys) == len(set(keys))


def test_balanced_determinism():
    assert sample_bb_params(120, BUDGET, seed=7, balanced=True) == sample_bb_params(
        120, BUDGET, seed=7, balanced=True
    )
    assert sample_bb_params(120, BUDGET, seed=7) != sample_bb_params(120, BUDGET, seed=8)


def test_balanced_every_sample_validates_and_respects_budget(balanced_300):
    for p in balanced_300:
        assert 2 * p["l"] * p["m"] <= BUDGET
        h_x, h_z = generate(p["l"], p["m"], p["a_exps"], p["b_exps"], seed=0)
        validate(h_x, h_z)


def test_balanced_raises_rather_than_returning_short():
    """budget=8 admits only l=m=2: at most one distinct code per template."""
    with pytest.raises(RuntimeError):
        sample_bb_params(len(TEMPLATES) + 1, budget=8, seed=0, balanced=True)


def test_unbalanced_unchanged_from_m0_codes_05():
    """balanced=False must reproduce the exact 300-code draw logged for
    M0-CODES-05 (AGENT_LOG 2026-09-14 (hh)), the draw that motivated D-023."""
    params = sample_bb_params(300, BUDGET, seed=0, balanced=False)
    assert params.counts == {
        "bb_v1_pair_2_2": 70,
        "bb_v1_quad_4_4": 69,
        "bb_v1_quad_4_2": 63,
        "bb_v1_quad_2_4": 61,
        "bb_v1_mod_2_3": 21,
        "bb_v1_sym_3_3": 8,
        "bb_v1_rare_2_3": 6,
        "bb_v1_mixed_3_5": 1,
        "bb_v1_rare_3_4": 1,
        "bb_v1_mixed_5_3": 0,
    }
    assert (params.attempts, params.rejections) == (639, 339)
    assert params.quota is None and params.exhausted == ()
