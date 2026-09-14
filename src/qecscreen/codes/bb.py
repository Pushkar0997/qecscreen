"""Bivariate bicycle (BB) code generator (Bravyi et al. 2024).

Construction: let ``x`` and ``y`` be the ``l*m x l*m`` GF(2) matrices
representing the commuting cyclic shifts of ``Z_l`` and ``Z_m`` respectively,
acting on the index pair ``(a, b) in Z_l x Z_m``. A polynomial such as
``A = x^3 + y + y^2`` is a GF(2) sum of monomials ``x^i y^j``; each monomial
maps to the permutation matrix shifting ``a -> a+i (mod l)`` and
``b -> b+j (mod m)`` simultaneously. Given the two check polynomials A and B:

    H_X = [A | B]
    H_Z = [B^T | A^T]

``x`` and ``y`` commute (they act on independent coordinates), so any A and B
built from them commute too, which is exactly what makes ``H_X @ H_Z.T == 0``
(mod 2) hold structurally — this is not verified here, only produced;
``qecscreen.linalg.check_css_commutation`` is what verifies it (INV-8).

d_upper (the code's estimated distance) is out of scope for this module — see
M0-CODES-04. This module never computes a distance.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

__all__ = ["generate"]


def _monomial_matrix(l: int, m: int, i: int, j: int) -> np.ndarray:
    """The ``lm x lm`` permutation matrix for the monomial ``x^i y^j``.

    Index ``(a, b) in Z_l x Z_m`` is flattened row-major as ``a * m + b``.
    The monomial maps ``(a, b) -> (a + i mod l, b + j mod m)``.
    """
    lm = l * m
    mat = np.zeros((lm, lm), dtype=np.uint8)
    for a in range(l):
        row_shifted = (a + i) % l
        for b in range(m):
            row = a * m + b
            col = row_shifted * m + (b + j) % m
            mat[row, col] = 1
    return mat


def _poly_matrix(l: int, m: int, exps: Sequence[tuple[int, int]]) -> np.ndarray:
    """GF(2) sum (XOR) of the monomial matrices for a polynomial's exponent pairs."""
    lm = l * m
    acc = np.zeros((lm, lm), dtype=np.uint8)
    for i, j in exps:
        acc ^= _monomial_matrix(l, m, i, j)
    return acc


def generate(
    l: int,
    m: int,
    a_exps: Sequence[tuple[int, int]],
    b_exps: Sequence[tuple[int, int]],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a BB code's parity check matrices.

    Parameters
    ----------
    l, m:
        The two cyclic group orders. The code has ``n = 2*l*m`` physical
        qubits and ``l*m`` checks of each type.
    a_exps, b_exps:
        The monomial exponent pairs ``(i, j)`` of the check polynomials
        ``A(x, y)`` and ``B(x, y)``, e.g. ``A = x^3 + y + y^2`` is
        ``[(3, 0), (0, 1), (0, 2)]``.
    seed:
        Accepted for interface consistency with the randomised samplers this
        module will grow (M0-CODES-05) and to allow a future
        ``construction_program_id``/``code_id`` derivation. The construction
        here is fully determined by ``l``, ``m``, ``a_exps`` and ``b_exps``
        and consumes no randomness, so ``seed`` does not affect the result —
        which is exactly what "same arguments and same seed produce
        byte-identical output" requires.

    Returns
    -------
    (H_X, H_Z):
        Two ``(l*m, 2*l*m)`` ``uint8`` arrays with entries in ``{0, 1}``.
    """
    if l <= 0 or m <= 0:
        raise ValueError(f"l and m must be positive integers; got l={l}, m={m}")
    if not a_exps or not b_exps:
        raise ValueError("a_exps and b_exps must each be non-empty")
    if not isinstance(seed, int):
        raise ValueError(f"seed must be an int; got {type(seed)}")

    a = _poly_matrix(l, m, a_exps)
    b = _poly_matrix(l, m, b_exps)

    h_x = np.hstack([a, b]).astype(np.uint8)
    h_z = np.hstack([b.T, a.T]).astype(np.uint8)
    return h_x, h_z
