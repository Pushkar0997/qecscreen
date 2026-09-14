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
"""

from __future__ import annotations

from typing import Any

import numpy as np

from qecscreen.codes.bb import generate
from qecscreen.codes.validate import InvalidCodeError, validate

__all__ = ["sample_bb_params", "TEMPLATES"]

# Minimum l/m: keeps the cyclic groups non-degenerate. 1 would collapse a
# dimension entirely (S_1 is the 1x1 identity), which is a valid input to
# generate() but not a useful sample point.
_MIN_DIM = 2

# Structural shapes, not (l, m) choices. Term counts deliberately vary
# (1..5 monomials per polynomial) so check weight, rank and k vary across
# the sample too, not just n. Named descriptively; the name becomes part of
# construction_program_id and must stay stable once used (a rename changes
# every id derived from it, which is exactly the kind of silent split
# corruption INV-2 exists to prevent).
TEMPLATES: list[tuple[str, list[tuple[int, int]], list[tuple[int, int]]]] = [
    ("sym_3_3", [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)]),  # the [[72,12,6]] shape
    ("pair_2_2", [(1, 0), (0, 2)], [(0, 1), (2, 0)]),
    ("quad_4_2", [(1, 0), (0, 1), (2, 0), (0, 2)], [(1, 1), (2, 2)]),
    ("quad_2_4", [(1, 1), (2, 2)], [(1, 0), (0, 1), (2, 0), (0, 2)]),
    ("rare_3_4", [(1, 2), (0, 3), (3, 0)], [(0, 1), (3, 3), (2, 3), (2, 1)]),
    ("rare_2_3", [(1, 1), (1, 3)], [(0, 1), (3, 2), (2, 1)]),
    ("mixed_3_5", [(4, 0), (0, 1), (1, 3)], [(0, 4), (1, 0), (2, 1), (3, 0), (0, 2)]),
    ("mixed_5_3", [(0, 4), (1, 0), (2, 1), (3, 0), (0, 2)], [(4, 0), (0, 1), (1, 3)]),
    ("quad_4_4", [(1, 0), (0, 1), (2, 1), (1, 2)], [(0, 1), (1, 0), (1, 2), (2, 1)]),
    ("mod_2_3", [(1, 0), (2, 3)], [(2, 3), (3, 2), (2, 1)]),
]
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
# see D-022, spec/decisions.md.


def sample_bb_params(n_codes: int, budget: int, seed: int) -> list[dict[str, Any]]:
    """Draw ``n_codes`` diverse, valid BB parameter sets with ``n = 2*l*m <= budget``.

    Each returned dict carries ``l``, ``m``, ``a_exps``, ``b_exps`` and
    ``construction_program_id`` — enough to call
    ``qecscreen.codes.bb.generate`` and reproduce the code exactly (``seed``
    is not needed for that: ``generate`` is deterministic in its other
    arguments alone).

    Every returned code has already passed ``qecscreen.codes.validate.validate``
    (so ``k >= 1``); candidates that fail are rejected and redrawn. All
    randomness comes from one ``numpy.random.Generator`` seeded from ``seed``,
    so the same ``(n_codes, budget, seed)`` always returns an identical list —
    determinism does not depend on how many candidates were rejected along
    the way, since rejection just continues drawing from the same stream.
    """
    if n_codes < 1:
        raise ValueError(f"n_codes must be >= 1; got {n_codes}")
    if budget < 2 * _MIN_DIM * _MIN_DIM:
        raise ValueError(
            f"budget={budget} is too small to fit even the minimum l=m={_MIN_DIM} code "
            f"(needs >= {2 * _MIN_DIM * _MIN_DIM})"
        )

    rng = np.random.default_rng(seed)
    max_l = budget // (2 * _MIN_DIM)

    results: list[dict[str, Any]] = []
    attempts = 0
    rejections = 0
    max_attempts = max(10_000, n_codes * 200)

    while len(results) < n_codes:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(
                f"could not draw {n_codes} valid codes within {max_attempts} attempts "
                f"(got {len(results)}, {rejections} rejected); budget={budget} may be too "
                "tight for the current template set"
            )

        template_idx = int(rng.integers(0, len(TEMPLATES)))
        name, a_exps, b_exps = TEMPLATES[template_idx]

        l = int(rng.integers(_MIN_DIM, max_l + 1))
        max_m = budget // (2 * l)
        if max_m < _MIN_DIM:
            continue  # this l leaves no room for a valid m; redraw
        m = int(rng.integers(_MIN_DIM, max_m + 1))

        h_x, h_z = generate(l, m, a_exps, b_exps, seed=0)
        try:
            validate(h_x, h_z)
        except InvalidCodeError:
            rejections += 1
            continue

        results.append(
            {
                "l": l,
                "m": m,
                "a_exps": a_exps,
                "b_exps": b_exps,
                "construction_program_id": f"bb_v1_{name}",
            }
        )

    return results
