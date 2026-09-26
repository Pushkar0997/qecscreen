"""Syndrome-extraction schedule ``bb_monomial_matching_xz_phased_v2`` (D-025 and its amendment).

For a BB code ``H_X = [A | B]`` and ``H_Z = [B^T | A^T]``, where ``A`` and
``B`` are sums of monomial permutation matrices. Each monomial is therefore a
perfect matching between the ``lm`` checks of one type and one data block, and
one CNOT layer per monomial touches every qubit at most once. That gives
``|A| + |B|`` layers per check type, which equals the check weight: the Konig
minimum (the maximum degree of the Tanner graph). The schedule is deterministic,
with no colouring strategy to pin.

X checks and Z checks are extracted in separate phases, X first, and never
interleaved. Within one check type all CNOTs point the same way and commute,
so the order inside a phase cannot change what is measured. An interleaved
order can.

Recorded monomial order (part of the scheduling method):
    X phase: A's monomials (data 0..lm-1), then B's (data lm..2lm-1)
    Z phase: B^T's monomials (data 0..lm-1), then A^T's (data lm..2lm-1)
each in the stored ``a_exps`` / ``b_exps`` order.

BB-only. Families without group-algebra structure need a general, verified
bipartite edge colouring under a new method string (revisit at M1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from qecscreen.codes.bb import _monomial_matrix, generate
from qecscreen.protocol import SCHEDULING

__all__ = ["Schedule", "bb_schedule"]

# One layer: (check index within its type, data qubit), one pair per check.
Layer = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Schedule:
    """CNOT layers for one round. ``x_layers`` run before ``z_layers``."""

    x_layers: tuple[Layer, ...]
    z_layers: tuple[Layer, ...]
    method: str = SCHEDULING

    @property
    def depth(self) -> int:
        """CNOT layers per round."""
        return len(self.x_layers) + len(self.z_layers)


def _matching(perm: np.ndarray, offset: int) -> Layer:
    """Layer for one permutation matrix: row ``c`` pairs with its single 1."""
    return tuple((c, offset + int(np.flatnonzero(perm[c])[0])) for c in range(perm.shape[0]))


def bb_schedule(
    l: int,
    m: int,
    a_exps: Sequence[tuple[int, int]],
    b_exps: Sequence[tuple[int, int]],
) -> Schedule:
    """The ``bb_monomial_matching_xz_phased_v2`` schedule for a BB code.

    Raises if the layers do not reproduce ``generate``'s ``H_X`` and ``H_Z``
    edge for edge, e.g. when a polynomial repeats a monomial and two terms
    cancel over GF(2). A schedule that measures something other than the
    checks would still produce a circuit, and a plausible LER.
    """
    lm = l * m
    a = [_monomial_matrix(l, m, i, j) for i, j in a_exps]
    b = [_monomial_matrix(l, m, i, j) for i, j in b_exps]

    x_layers = tuple(_matching(p, 0) for p in a) + tuple(_matching(p, lm) for p in b)
    z_layers = tuple(_matching(p.T, 0) for p in b) + tuple(_matching(p.T, lm) for p in a)

    h_x, h_z = generate(l, m, a_exps, b_exps, seed=0)
    for name, layers, h in (("X", x_layers, h_x), ("Z", z_layers, h_z)):
        rebuilt = np.zeros_like(h)
        for layer in layers:
            for c, q in layer:
                rebuilt[c, q] += 1
        if not np.array_equal(rebuilt, h):
            raise ValueError(
                f"{name}-phase layers do not reproduce H_{name} edge for edge; a "
                "polynomial likely repeats a monomial. This schedule cannot "
                "extract that code's checks (D-025)."
            )
    return Schedule(x_layers=x_layers, z_layers=z_layers)
