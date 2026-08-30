"""Linear algebra over GF(2).

This module exists for one reason: ``numpy.linalg.matrix_rank`` computes rank
over the reals and gives the wrong answer for parity-check matrices. Using it
produces a wrong ``k`` for a code, which is silent, plausible, and corrupts
every downstream label. See CONTRACT.md INV-8.

All matrices are ``numpy.uint8`` with values in {0, 1}.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "gf2_rref",
    "gf2_rank",
    "gf2_nullspace",
    "gf2_nullspace_dim",
    "check_css_commutation",
    "logical_qubit_count",
]


def _as_gf2(m: np.ndarray) -> np.ndarray:
    a = np.asarray(m)

    # Order matters, and getting it wrong is the exact failure INV-8 exists to
    # catch. Casting first and validating afterwards means
    # np.asarray([[0.5, 0.0]], dtype=np.uint8) truncates to [[0, 0]], sails
    # through a {0, 1} check, and returns a confidently wrong rank — which
    # becomes a wrong k, which becomes a wrong label. An out-of-range integer
    # wraps modulo 256 the same way. So the dtype is rejected before any cast.
    if a.dtype == np.bool_:
        raise ValueError(
            "matrix is bool; GF(2) matrices are uint8 with values in {0, 1} "
            "(CONTRACT.md, matrix field convention). Cast explicitly if that is "
            "what you meant."
        )
    if not np.issubdtype(a.dtype, np.integer):
        raise ValueError(
            f"matrix has dtype {a.dtype}; GF(2) matrices are integer-typed, never "
            "float (CONTRACT.md, matrix field convention). A float matrix would be "
            "silently truncated, which is how a wrong rank becomes a wrong k."
        )
    if a.ndim != 2:
        raise ValueError(f"expected a 2-D matrix; got shape {a.shape}")
    if not np.isin(a, (0, 1)).all():
        raise ValueError("matrix must contain only 0 and 1 over GF(2)")
    return a.astype(np.uint8, copy=True)


def gf2_rref(m: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Reduced row echelon form over GF(2). Returns (rref, pivot_columns)."""
    a = _as_gf2(m)
    rows, cols = a.shape
    pivots: list[int] = []
    r = 0
    for c in range(cols):
        if r >= rows:
            break
        pivot = np.nonzero(a[r:, c])[0]
        if pivot.size == 0:
            continue
        i = r + int(pivot[0])
        if i != r:
            a[[r, i]] = a[[i, r]]
        targets = np.nonzero(a[:, c])[0]
        targets = targets[targets != r]
        if targets.size:
            a[targets] ^= a[r]
        pivots.append(c)
        r += 1
    return a, pivots


def gf2_rank(m: np.ndarray) -> int:
    """Rank over GF(2). Never use numpy.linalg.matrix_rank here (INV-8)."""
    return len(gf2_rref(m)[1])


def gf2_nullspace_dim(m: np.ndarray) -> int:
    a = _as_gf2(m)
    return a.shape[1] - gf2_rank(a)


def gf2_nullspace(m: np.ndarray) -> np.ndarray:
    """Basis for the nullspace ``{x : m @ x == 0 (mod 2)}``, one vector per row.

    Returns a ``(n - gf2_rank(m), n)`` uint8 array. Rows rather than columns, so
    that a basis vector is indexed the same way a check-matrix row is — by qubit
    (CONTRACT.md, check matrix orientation).

    ``gf2_nullspace_dim`` answers the cheaper question and is all that ``k``
    needs. This returns the actual vectors, which is what a search for low-weight
    logical operators needs (M0-CODES-04).
    """
    a = _as_gf2(m)
    n = a.shape[1]
    rref, pivots = gf2_rref(a)
    pivot_set = set(pivots)
    free = [c for c in range(n) if c not in pivot_set]

    basis = np.zeros((len(free), n), dtype=np.uint8)
    for i, f in enumerate(free):
        basis[i, f] = 1
        for row, piv in enumerate(pivots):
            basis[i, piv] = rref[row, f]
    return basis


def check_css_commutation(h_x: np.ndarray, h_z: np.ndarray) -> None:
    """INV-8: raise unless H_X H_Z^T = 0 over GF(2).

    Raises rather than warns. A non-commuting pair is not a code, and every
    downstream tool will happily produce a plausible number for it.
    """
    x = _as_gf2(h_x)
    z = _as_gf2(h_z)
    if x.shape[1] != z.shape[1]:
        raise ValueError(
            f"H_X has {x.shape[1]} columns but H_Z has {z.shape[1]}; "
            "both must be indexed by the same n data qubits"
        )
    product = (x.astype(np.int64) @ z.astype(np.int64).T) % 2
    if product.any():
        bad = int(product.sum())
        raise ValueError(
            f"CSS commutation violated: H_X H_Z^T has {bad} non-zero entries. "
            "This is not a valid CSS code (CONTRACT.md INV-8)."
        )


def logical_qubit_count(h_x: np.ndarray, h_z: np.ndarray) -> int:
    """k = n - rank(H_X) - rank(H_Z), computed over GF(2)."""
    check_css_commutation(h_x, h_z)
    n = np.asarray(h_x).shape[1]
    return n - gf2_rank(h_x) - gf2_rank(h_z)
