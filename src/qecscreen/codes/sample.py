"""Sample diverse BB (l, m, A, B) parameter sets, M0-CODES-05.

A **template** here is a polynomial *shape* — a fixed pair of monomial
exponent lists (``a_exps``, ``b_exps``) — independent of ``l`` and ``m``.
Two codes drawn from the same template with different ``l``/``m`` are the
SAME construction program (``AGENTS.md``'s vocabulary: "Construction
program — the parameterised recipe that generates a family of codes, e.g.
the BB polynomial template. The unit of grouping for splits."). Varying
``l``/``m`` within one template is exactly the near-duplicate relationship
INV-2 exists to keep off both sides of a split.

``construction_program_id`` is ``bb_v1_<template_name>`` — one level more
specific than the bare ``bb_v1`` shown as CONTRACT.md's illustrative example
for the *family*, because grouping on the family alone would still let two
different polynomial shapes (structurally unrelated codes) share a group,
which is looser than INV-2 needs. Every code sharing a template shares this
id; no two templates ever produce the same id.

Two templates can also be the same construction program under different
exponent lists (D-024): swapping A and B gives ``[B|A]``/``[A^T|B^T]``, which
is ``[A|B]``/``[B^T|A^T]`` with the two qubit halves exchanged; and
multiplying A by a monomial ``g`` and B by ``h`` gives ``[Ag|Bh]``, which is
``[A|B]`` with each half's qubits permuted. ``template_key`` is invariant
under both, and no two ``TEMPLATES`` may share a key.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from qecscreen.codes.bb import generate
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.codes.validate import InvalidCodeError, validate

__all__ = ["sample_bb_params", "admissible_codes", "BBSample", "TEMPLATES", "MIN_D_UPPER", "template_key"]

# Minimum l/m: keeps the cyclic groups non-degenerate. 1 would collapse a
# dimension entirely (S_1 is the 1x1 identity), which is a valid input to
# generate() but not a useful sample point.
_MIN_DIM = 2

# Admission rule (D-024): a code is emitted only if estimate_d_upper() >= 3.
# A d <= 2 code corrects no errors, so it is trivially rankable and would
# inflate rank correlation for every screening method alike.
MIN_D_UPPER = 3

# Structural shapes, not (l, m) choices. Term counts deliberately vary
# (2..5 monomials per polynomial) so check weight, rank and k vary across
# the sample too, not just n. Named descriptively; the name becomes part of
# construction_program_id and must stay stable once a labelled row uses it
# (a rename then changes every id derived from it, which is exactly the kind
# of silent split corruption INV-2 exists to prevent). D-024's removals and
# additions happened before any labelled row existed.
TEMPLATES: list[tuple[str, list[tuple[int, int]], list[tuple[int, int]]]] = [
    ("sym_3_3", [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),  # the [[72,12,6]] shape
    ("pair_2_2", [(1, 0), (0, 2)], [(0, 1), (2, 0)]),
    ("quad_4_2", [(1, 0), (0, 1), (2, 0), (0, 2)], [(1, 1), (2, 2)]),
    ("rare_3_4", [(1, 2), (0, 3), (3, 0)], [(0, 1), (3, 3), (2, 3), (2, 1)]),
    ("rare_2_3", [(1, 1), (1, 3)], [(0, 1), (3, 2), (2, 1)]),
    ("mixed_3_5", [(4, 0), (0, 1), (1, 3)], [(0, 4), (1, 0), (2, 1), (3, 0), (0, 2)]),
    ("mod_2_3", [(1, 0), (2, 3)], [(2, 3), (3, 2), (2, 1)]),
    # Added by D-024 to replace the three removed templates.
    ("bb288_3_3", [(3, 0), (0, 2), (0, 7)], [(0, 3), (1, 0), (2, 0)]),  # the [[288,12,18]] shape
    ("tri_3_3", [(1, 0), (0, 1), (1, 1)], [(0, 0), (2, 1), (1, 2)]),
    ("diag_3_3", [(1, 0), (0, 1), (2, 2)], [(0, 0), (1, 2), (2, 1)]),
    ("sq_4_2", [(0, 0), (1, 0), (0, 1), (1, 1)], [(2, 0), (0, 3)]),
]
# Removed by D-024: quad_2_4 and mixed_5_3 (A/B swaps of quad_4_2 and
# mixed_3_5, so the same programs under a second id) and quad_4_4 (A == B,
# so Z_i Z_{i+lm} commutes with every X check and d <= 2 whenever k >= 1).
# A template whose A or B is a single monomial is deliberately avoided: a
# lone monomial matrix is itself an invertible permutation, so it forces
# rank(H_X) = rank(H_Z) = l*m regardless of the other polynomial — k = 0 for
# EVERY (l, m), not bad luck but a structural certainty. Three early
# candidates (each with a 2-term side, not even a lone monomial) were also
# found to fail for EVERY (l, m) tested across the full l,m in [2,19] grid
# under budget=150, for reasons tied to the specific polynomials' algebraic
# structure rather than any one simple rule; they were replaced rather than
# kept and hoped past. Every template actually shipped here was verified
# against that same grid to have a nonzero success rate before being kept —
# see D-022, spec/decisions.md. Since D-024 the bar is at least 10 distinct
# (l, m) at budget=150 that pass both validate() and the MIN_D_UPPER rule.


def _translate_to_origin(exps: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    lo = min(exps)
    return tuple(sorted((a - lo[0], b - lo[1]) for a, b in exps))


def template_key(
    a_exps: list[tuple[int, int]], b_exps: list[tuple[int, int]]
) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    """Canonical form of a template under A/B swap and per-polynomial monomial shift.

    Both operations map every code the template generates, at every
    ``(l, m)``, to the same code up to a qubit permutation (module
    docstring), so two templates with equal keys are one construction
    program. Does not cover equivalences that only hold at particular
    ``(l, m)`` (e.g. ``y -> y^5`` when ``gcd(5, m) = 1``).
    """
    a, b = _translate_to_origin(a_exps), _translate_to_origin(b_exps)
    return min((a, b), (b, a))


class BBSample(list):
    """The list of parameter dicts ``sample_bb_params`` returns, plus how it was filled.

    A ``list`` subclass, so it compares, iterates and slices exactly like the
    plain list callers already use; the attributes exist so a shortfall is
    visible rather than silent (D-023):

    - ``counts`` — actual codes per ``construction_program_id`` (every
      template listed, including those with 0).
    - ``quota`` — the even allocation each template was first asked for
      (``None`` when ``balanced=False``, which allocates nothing).
    - ``exhausted`` — ids of templates that ran out of distinct admissible
      ``(l, m)`` pairs before meeting their quota; their shortfall was
      redistributed to the others. Always empty when ``balanced=False``.
    - ``attempts`` — candidate codes checked.
    - ``rejections`` — how many candidates failed, by cause: ``"k<1"``
      (``validate()`` failed) and ``"d_upper<3"`` (the D-024 admission rule).
    """

    counts: dict[str, int]
    quota: dict[str, int] | None
    exhausted: tuple[str, ...]
    attempts: int
    rejections: dict[str, int]


def sample_bb_params(n_codes: int, budget: int, seed: int, balanced: bool = True) -> BBSample:
    """Draw ``n_codes`` diverse, valid BB parameter sets with ``n = 2*l*m <= budget``.

    Each returned dict carries ``l``, ``m``, ``a_exps``, ``b_exps`` and
    ``construction_program_id`` — enough to call
    ``qecscreen.codes.bb.generate`` and reproduce the code exactly (``seed``
    is not needed for that: ``generate`` is deterministic in its other
    arguments alone).

    Every returned code is *admissible*: it has passed
    ``qecscreen.codes.validate.validate`` (so ``k >= 1``) and has
    ``estimate_d_upper(h_x, h_z, seed=0) >= MIN_D_UPPER`` (D-024). The same
    ``(n_codes, budget, seed, balanced)`` always returns an identical list.

    ``balanced=True`` (the default, D-023) splits ``n_codes`` evenly across
    ``TEMPLATES`` and fills each template's quota with *distinct* admissible
    ``(l, m)`` pairs. A template with fewer such pairs than its
    quota at this budget is marked exhausted and its shortfall is
    redistributed evenly to templates that still have pairs left; if every
    template is exhausted first, ``RuntimeError`` — never a shorter list.
    The result's ``counts``/``quota``/``exhausted`` attributes show what
    happened.

    ``balanced=False`` is the original M0-CODES-05 behaviour: template drawn
    uniformly per candidate, reject-and-redraw on failure, duplicates
    possible. Uniform template draws against per-template yields of 9%-100%
    concentrate most codes in a few templates (D-023 has the measurement).
    """
    if n_codes < 1:
        raise ValueError(f"n_codes must be >= 1; got {n_codes}")
    if budget < 2 * _MIN_DIM * _MIN_DIM:
        raise ValueError(
            f"budget={budget} is too small to fit even the minimum l=m={_MIN_DIM} code "
            f"(needs >= {2 * _MIN_DIM * _MIN_DIM})"
        )
    if balanced:
        return _sample_balanced(n_codes, budget, seed)
    return _sample_uniform(n_codes, budget, seed)


def _pid(template_idx: int) -> str:
    return f"bb_v1_{TEMPLATES[template_idx][0]}"


def _params(template_idx: int, l: int, m: int) -> dict[str, Any]:
    _, a_exps, b_exps = TEMPLATES[template_idx]
    return {
        "l": l,
        "m": m,
        "a_exps": a_exps,
        "b_exps": b_exps,
        "construction_program_id": _pid(template_idx),
    }


def _rejection_cause(template_idx: int, l: int, m: int) -> str | None:
    """``None`` if the code is admitted, else the reason it is not."""
    _, a_exps, b_exps = TEMPLATES[template_idx]
    h_x, h_z = generate(l, m, a_exps, b_exps, seed=0)
    try:
        validate(h_x, h_z)
    except InvalidCodeError:
        return "k<1"
    # Fixed seed: admission is a property of the code, not of the draw.
    d_upper, _ = estimate_d_upper(h_x, h_z, seed=0)
    if d_upper < MIN_D_UPPER:
        return f"d_upper<{MIN_D_UPPER}"
    return None


def admissible_codes(budget: int) -> list[dict[str, Any]]:
    """Every admissible code at ``budget``, enumerated, not sampled (D-031).

    Each ``(template, l, m)`` on the balanced sampler's grid (``2*l*m <=
    budget``, ``l, m >= 2``) whose code passes ``validate`` and has
    ``estimate_d_upper(seed=0) >= MIN_D_UPPER``: the admission rule the
    samplers apply (``_rejection_cause``), applied to the whole grid. In
    ``TEMPLATES`` order, then grid order. Each dict is ``sample_bb_params``'s
    plus ``n``, ``k`` and ``d_upper``. At budget 72 this is the M0 population.
    """
    pairs, _ = _lm_grid(budget)
    out: list[dict[str, Any]] = []
    for t, (_, a_exps, b_exps) in enumerate(TEMPLATES):
        for l, m in pairs:
            h_x, h_z = generate(l, m, a_exps, b_exps, seed=0)
            try:
                n, k = validate(h_x, h_z)
            except InvalidCodeError:
                continue
            d_upper, _ = estimate_d_upper(h_x, h_z, seed=0)
            if d_upper >= MIN_D_UPPER:
                out.append({**_params(t, l, m), "n": n, "k": k, "d_upper": d_upper})
    return out


def _new_rejections() -> dict[str, int]:
    return {"k<1": 0, f"d_upper<{MIN_D_UPPER}": 0}


def _finish(
    results: list[dict[str, Any]],
    quota: dict[str, int] | None,
    exhausted: tuple[str, ...],
    attempts: int,
    rejections: dict[str, int],
) -> BBSample:
    out = BBSample(results)
    out.counts = {_pid(t): 0 for t in range(len(TEMPLATES))}
    for p in results:
        out.counts[p["construction_program_id"]] += 1
    out.quota = quota
    out.exhausted = exhausted
    out.attempts = attempts
    out.rejections = rejections
    return out


def _lm_grid(budget: int) -> tuple[list[tuple[int, int]], np.ndarray]:
    """Every ``(l, m)`` with ``2*l*m <= budget``, weighted as ``_sample_uniform`` draws them.

    ``_sample_uniform`` draws ``l`` uniformly from ``[_MIN_DIM, max_l]``, then
    ``m`` uniformly from ``[_MIN_DIM, budget // (2*l)]``; reusing those
    weights keeps the balanced sampler's ``n`` distribution comparable.
    """
    max_l = budget // (2 * _MIN_DIM)
    n_l = max_l - _MIN_DIM + 1
    pairs: list[tuple[int, int]] = []
    weights: list[float] = []
    for l in range(_MIN_DIM, max_l + 1):
        n_m = budget // (2 * l) - _MIN_DIM + 1
        for m in range(_MIN_DIM, _MIN_DIM + n_m):
            pairs.append((l, m))
            weights.append(1.0 / (n_l * n_m))
    w = np.asarray(weights)
    return pairs, w / w.sum()


def _sample_balanced(n_codes: int, budget: int, seed: int) -> BBSample:
    n_t = len(TEMPLATES)
    pairs, weights = _lm_grid(budget)

    # One independent stream per template plus one for allocation and the
    # final shuffle, so a template's draws never depend on how many attempts
    # another template needed.
    children = np.random.SeedSequence(seed).spawn(n_t + 1)
    alloc_rng = np.random.default_rng(children[-1])
    # Each template walks its own weighted without-replacement ordering of
    # the (l, m) grid: pairs are distinct, and attempts are bounded by the
    # grid's size, which is also what makes "exhausted" exact rather than a
    # guess from a timeout.
    walks = [
        np.random.default_rng(c).choice(len(pairs), size=len(pairs), replace=False, p=weights)
        for c in children[:-1]
    ]

    quota = [n_codes // n_t] * n_t
    for t in alloc_rng.permutation(n_t)[: n_codes % n_t]:
        quota[int(t)] += 1
    initial_quota = {_pid(t): quota[t] for t in range(n_t)}

    accepted: list[list[dict[str, Any]]] = [[] for _ in range(n_t)]
    pos = [0] * n_t
    exhausted = [False] * n_t
    attempts = 0
    rejections = _new_rejections()

    # Each pass either fills every open quota or exhausts at least one more
    # template, so this terminates within n_t + 1 passes.
    while True:
        for t in range(n_t):
            while len(accepted[t]) < quota[t] and pos[t] < len(pairs):
                l, m = pairs[int(walks[t][pos[t]])]
                pos[t] += 1
                attempts += 1
                cause = _rejection_cause(t, l, m)
                if cause is None:
                    accepted[t].append(_params(t, l, m))
                else:
                    rejections[cause] += 1
            if len(accepted[t]) < quota[t]:
                exhausted[t] = True

        shortfall = sum(quota[t] - len(accepted[t]) for t in range(n_t))
        if shortfall == 0:
            break
        for t in range(n_t):
            if exhausted[t]:
                quota[t] = len(accepted[t])
        open_ts = [t for t in range(n_t) if not exhausted[t]]
        if not open_ts:
            got = {_pid(t): len(accepted[t]) for t in range(n_t)}
            raise RuntimeError(
                f"could not draw {n_codes} distinct admissible codes at budget={budget}: every "
                f"template ran out of admissible (l, m) pairs; got {sum(got.values())}, counts={got}"
            )
        share, extra = divmod(shortfall, len(open_ts))
        for j, i in enumerate(alloc_rng.permutation(len(open_ts))):
            quota[open_ts[int(i)]] += share + (1 if j < extra else 0)

    flat = [p for group in accepted for p in group]
    # Shuffle so a prefix slice isn't grouped by template.
    results = [flat[int(i)] for i in alloc_rng.permutation(len(flat))]
    exhausted_ids = tuple(_pid(t) for t in range(n_t) if exhausted[t])
    return _finish(results, initial_quota, exhausted_ids, attempts, rejections)


def _sample_uniform(n_codes: int, budget: int, seed: int) -> BBSample:
    # The original M0-CODES-05 sampler, unchanged: one seeded Generator drives
    # template choice, l, m and every redraw, so determinism does not depend
    # on how many candidates were rejected along the way.
    rng = np.random.default_rng(seed)
    max_l = budget // (2 * _MIN_DIM)

    results: list[dict[str, Any]] = []
    attempts = 0
    rejections = _new_rejections()
    max_attempts = max(10_000, n_codes * 200)

    while len(results) < n_codes:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(
                f"could not draw {n_codes} admissible codes within {max_attempts} attempts "
                f"(got {len(results)}, rejected {rejections}); budget={budget} may be too "
                "tight for the current template set"
            )

        template_idx = int(rng.integers(0, len(TEMPLATES)))

        l = int(rng.integers(_MIN_DIM, max_l + 1))
        max_m = budget // (2 * l)
        if max_m < _MIN_DIM:
            continue  # this l leaves no room for a valid m; redraw
        m = int(rng.integers(_MIN_DIM, max_m + 1))

        cause = _rejection_cause(template_idx, l, m)
        if cause is not None:
            rejections[cause] += 1
            continue

        results.append(_params(template_idx, l, m))

    return _finish(results, None, (), attempts, rejections)
