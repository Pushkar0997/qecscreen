"""GF(2) linear algebra tests (spec/evals.md INV-8-T, N-01, N-06)."""

import numpy as np
import pytest

from qecscreen.linalg import (
    check_css_commutation,
    gf2_nullspace,
    gf2_nullspace_dim,
    gf2_rank,
    logical_qubit_count,
)


def test_n06_gf2_rank_differs_from_real_rank():
    """The whole reason this module exists.

    Over the reals these three rows are independent (rank 3). Over GF(2) the
    third is the XOR of the first two, so the rank is 2. numpy.linalg.matrix_rank
    would return 3 and give a wrong k for a code.
    """
    m = np.array(
        [
            [1, 1, 0],
            [0, 1, 1],
            [1, 0, 1],
        ],
        dtype=np.uint8,
    )
    assert np.linalg.matrix_rank(m.astype(float)) == 3
    assert gf2_rank(m) == 2


def test_gf2_rank_basic():
    assert gf2_rank(np.eye(4, dtype=np.uint8)) == 4
    assert gf2_rank(np.zeros((3, 5), dtype=np.uint8)) == 0
    assert gf2_nullspace_dim(np.eye(4, dtype=np.uint8)) == 0


def test_gf2_nullspace_vectors_are_annihilated():
    """Every returned row must actually be in the nullspace, over GF(2)."""
    rng = np.random.default_rng(0)
    for _ in range(200):
        rows = int(rng.integers(1, 8))
        cols = int(rng.integers(1, 8))
        m = rng.integers(0, 2, size=(rows, cols), dtype=np.uint8)

        basis = gf2_nullspace(m)
        assert basis.dtype == np.uint8
        assert basis.shape == (gf2_nullspace_dim(m), cols)
        if basis.size:
            product = (m.astype(np.int64) @ basis.astype(np.int64).T) % 2
            assert not product.any()
            # A basis, not just a spanning set: the rows are independent.
            assert gf2_rank(basis) == basis.shape[0]


def test_gf2_nullspace_edge_cases():
    full_rank = gf2_nullspace(np.eye(4, dtype=np.uint8))
    assert full_rank.shape == (0, 4)

    zero = gf2_nullspace(np.zeros((3, 5), dtype=np.uint8))
    assert zero.shape == (5, 5)
    assert gf2_rank(zero) == 5


def test_gf2_nullspace_matches_a_worked_example():
    """The nullspace of the [7,4,3] Hamming matrix is the Hamming code itself."""
    h = np.array(
        [
            [0, 0, 0, 1, 1, 1, 1],
            [0, 1, 1, 0, 0, 1, 1],
            [1, 0, 1, 0, 1, 0, 1],
        ],
        dtype=np.uint8,
    )
    basis = gf2_nullspace(h)
    assert basis.shape == (4, 7)
    assert not ((h.astype(np.int64) @ basis.astype(np.int64).T) % 2).any()


def test_gf2_rejects_non_binary():
    with pytest.raises(ValueError):
        gf2_rank(np.array([[2, 0], [0, 1]], dtype=np.uint8))


def test_steane_code_has_k_one():
    """The [[7,1,3]] Steane code: H_X = H_Z = the [7,4,3] Hamming matrix."""
    h = np.array(
        [
            [0, 0, 0, 1, 1, 1, 1],
            [0, 1, 1, 0, 0, 1, 1],
            [1, 0, 1, 0, 1, 0, 1],
        ],
        dtype=np.uint8,
    )
    check_css_commutation(h, h)
    assert gf2_rank(h) == 3
    assert logical_qubit_count(h, h) == 1


def test_n01_non_commuting_pair_is_rejected():
    """N-01: raise, never warn. A non-commuting pair is not a code."""
    h_x = np.array([[1, 1, 0, 0]], dtype=np.uint8)
    h_z = np.array([[1, 0, 0, 0]], dtype=np.uint8)
    with pytest.raises(ValueError):
        check_css_commutation(h_x, h_z)


def test_mismatched_widths_are_rejected():
    with pytest.raises(ValueError):
        check_css_commutation(
            np.array([[1, 1]], dtype=np.uint8), np.array([[1, 1, 0]], dtype=np.uint8)
        )
