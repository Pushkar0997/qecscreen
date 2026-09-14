"""Randomised upper-bound distance search (d_upper), M0-CODES-04.

CONTRACT.md's distance-provenance rule is the hard constraint this module
exists to respect: a randomised search can only ever produce an UPPER bound
on distance, because it is not exhaustive. This module returns ``d_upper``
only and never computes, returns, or names the exact-distance column — that requires an
exhaustive or provably exact method, which this is not.

METHOD — random information-set search
For each attempt, draw a uniformly random column permutation and use it to
select a fresh set of pivot columns when reducing a basis for the logical
operator space (``ker(H_X)`` for Z-type, ``ker(H_Z)`` for X-type) to row
echelon form. Every resulting row is still a valid element of that space —
row-reducing a basis never leaves its row space — but each random pivot
choice re-expresses the same space through a different "information set",
and the weight of the rows that come out varies with it. Some permutations
land close enough to a genuinely low-weight codeword's own support that a
row comes out at or near that weight. Repeating with many random
permutations and keeping the minimum weight seen across every row, every
attempt (after discarding rows that reduce to zero against the stabiliser
generators — i.e. rows that are themselves pure stabiliser elements, not
logical operators) is a standard random information-set search for a
low-weight codeword, applied here to the logical-operator coset rather than
the whole code.

An earlier version of this module used a weaker method — draw one random
dense combination of the nullspace basis, then greedily flip in single
stabiliser generators while that reduces weight — and it failed to reach the
published distance for the [[144,12,12]] gross code even at 5,000 attempts
(best found: 14, not 12). The random-information-set method above reaches
both reference codes' published distances in single-digit attempts (see
``tests/test_distance.py`` and D-021, ``spec/decisions.md``, which records
the measurement behind ``DEFAULT_ATTEMPTS``). That failure is the reason
this docstring names the method: a search that is too weak fails upward,
silently, and a wrong docstring claiming "decoder-assisted random search"
without saying which random search is exactly the kind of thing that looks
fine until someone checks it against a reference value.

Every GF(2) operation here is either delegated to ``qecscreen.linalg`` (for
computing the nullspace bases) or performed inline as GF(2) row reduction in
the same style as ``qecscreen.linalg.gf2_rref`` — this module performs no
floating-point linear algebra and adds no new dependency.
"""

from __future__ import annotations

import numpy as np

from qecscreen.linalg import gf2_nullspace, gf2_rref

__all__ = ["estimate_d_upper", "METHOD_NAME", "DEFAULT_ATTEMPTS"]

METHOD_NAME = "random_information_set_v1"

# Measured, not guessed (D-021, spec/decisions.md): across 30 seeds each, the
# [[72,12,6]] code hits d_upper=6 reliably from attempts=1; the [[144,12,12]]
# gross code — the binding constraint — is unreliable at attempts=3 (25/30
# correct) and reliable at attempts=4 (30/30 correct). DEFAULT_ATTEMPTS is
# set at 16x that measured threshold. At this default, a single call takes
# ~0.10s for the gross code and ~0.05s for the [[72,12,6]] code (20-seed
# average, dev box).
DEFAULT_ATTEMPTS = 64


def _reduce_against_rref(v: np.ndarray, rref: np.ndarray, pivots: list[int]) -> np.ndarray:
    """Reduce ``v`` modulo the rowspace of a matrix already in RREF.

    Zeroes each pivot column of ``v`` in turn using the RREF's rows. What is
    left is the all-zero vector iff ``v`` was already in that rowspace (i.e.
    a pure stabiliser element, not a logical operator).
    """
    v = v.copy()
    for row, col in enumerate(pivots):
        if v[col]:
            v ^= rref[row]
    return v


def _random_information_set_rows(rng: np.random.Generator, basis: np.ndarray) -> np.ndarray:
    """One random-information-set row reduction of ``basis``.

    Returns a ``(dim, n)`` array whose rows all lie in the row space of
    ``basis`` (so each is a valid element of the space ``basis`` spans), but
    expressed through a fresh, randomly chosen set of pivot columns. This is
    the single random draw the search repeats every attempt.
    """
    dim, n = basis.shape
    mat = basis.copy()
    perm = rng.permutation(n)
    r = 0
    for c in perm:
        if r >= dim:
            break
        nz = np.nonzero(mat[r:, c])[0]
        if nz.size == 0:
            continue
        i = r + int(nz[0])
        if i != r:
            mat[[r, i]] = mat[[i, r]]
        targets = np.nonzero(mat[:, c])[0]
        targets = targets[targets != r]
        if targets.size:
            mat[targets] ^= mat[r]
        r += 1
    return mat


def _search_one_type(
    rng: np.random.Generator,
    logical_basis: np.ndarray,
    stab_rref: np.ndarray,
    stab_pivots: list[int],
    n_attempts: int,
) -> int | None:
    """Minimum nontrivial row weight found over ``n_attempts`` random information sets."""
    if n_attempts <= 0:
        return None
    best: int | None = None
    for _ in range(n_attempts):
        mat = _random_information_set_rows(rng, logical_basis)
        weights = mat.sum(axis=1)
        order = np.argsort(weights)  # cheapest candidates first; skip once no row can beat `best`
        for i in order:
            w = int(weights[i])
            if best is not None and w >= best:
                break
            if _reduce_against_rref(mat[i], stab_rref, stab_pivots).any():
                best = w
    return best


def estimate_d_upper(
    h_x: np.ndarray, h_z: np.ndarray, seed: int, attempts: int = DEFAULT_ATTEMPTS
) -> tuple[int, str]:
    """Randomised upper bound on code distance. Returns ``(d_upper, method_name)``.

    Never returns, computes, or names the exact-distance column — see CONTRACT.md's
    distance-provenance rule. ``method_name`` identifies the algorithm
    (``qecscreen.codes.distance.METHOD_NAME``) and is meant to be recorded
    per row, since a different method could later give a different (still
    valid) bound.

    Determinism is a correctness requirement, not a nicety (D-006,
    ``rounds_rule = "r = d_upper"``): the same ``(h_x, h_z, seed, attempts)``
    always returns the same result. Every random draw comes from a single
    ``numpy.random.Generator`` seeded from ``seed`` — no global RNG, no
    time-based entropy, no set/dict iteration order affecting the outcome.
    """
    if attempts < 1:
        raise ValueError(f"attempts must be >= 1; got {attempts}")

    rng = np.random.default_rng(seed)

    null_x = gf2_nullspace(h_x)  # Z-logical candidates (mod rowspace(H_Z))
    null_z = gf2_nullspace(h_z)  # X-logical candidates (mod rowspace(H_X))
    rref_z, pivots_z = gf2_rref(h_z)
    rref_x, pivots_x = gf2_rref(h_x)

    # Attempts are split deterministically between the two logical-operator
    # types (never randomly), so the type sequence depends only on `attempts`.
    z_attempts = attempts // 2
    x_attempts = attempts - z_attempts

    best_z = _search_one_type(rng, null_x, rref_z, pivots_z, z_attempts)
    best_x = _search_one_type(rng, null_z, rref_x, pivots_x, x_attempts)

    candidates = [w for w in (best_z, best_x) if w is not None]
    return min(candidates), METHOD_NAME
