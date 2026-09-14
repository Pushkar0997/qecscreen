"""INV-8: code validity is verified, never assumed (M0-CODES-03).

``qecscreen.codes.validate.validate`` enforces, in order: dtype/value
rejection, matching column counts, CSS commutation, GF(2)-rank-based ``k``,
and ``k >= 1``. It raises ``InvalidCodeError`` on every failure and never
returns a bool.
"""

import numpy as np
import pytest

from qecscreen.codes.bb import generate
from qecscreen.codes.validate import InvalidCodeError, validate

L = 6
M = 6
A_EXPS = [(3, 0), (0, 1), (0, 2)]
B_EXPS = [(0, 3), (1, 0), (2, 0)]
SEED = 0

GROSS_L = 12
GROSS_M = 6


def test_reference_code_validates_with_correct_n_and_k():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    n, k = validate(h_x, h_z)
    assert (n, k) == (72, 12)


def test_gross_code_validates_with_correct_n_and_k():
    h_x, h_z = generate(GROSS_L, GROSS_M, A_EXPS, B_EXPS, SEED)
    n, k = validate(h_x, h_z)
    assert (n, k) == (144, 12)


def test_perturbed_real_check_matrix_is_rejected():
    """A non-commuting pair must raise - built by perturbing a real H_X.

    A hand-built counterexample tests the author's imagination for what a
    "bad" matrix looks like. Flipping one bit of an actual generate() output
    tests the check itself against a realistic failure, not an invented one.
    """
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    h_x_bad = h_x.copy()
    h_x_bad[0, 0] ^= 1
    with pytest.raises(InvalidCodeError):
        validate(h_x_bad, h_z)


def test_float_matrix_is_rejected():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    with pytest.raises(InvalidCodeError):
        validate(h_x.astype(float), h_z)


def test_bool_matrix_is_rejected():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    with pytest.raises(InvalidCodeError):
        validate(h_x.astype(bool), h_z)


def test_mismatched_column_counts_are_rejected():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    with pytest.raises(InvalidCodeError):
        validate(h_x, h_z[:, :-1])


def test_k_zero_is_rejected():
    """A cheap, legitimate k=0 CSS pair: two orthogonal single-row checks.

    n=2, H_X=[[1,0]], H_Z=[[0,1]]: H_X @ H_Z.T = 0 (mod 2), so it commutes,
    but rank(H_X) = rank(H_Z) = 1 and k = 2 - 1 - 1 = 0. A real, if trivial,
    commuting pair - not a fabricated rejection.
    """
    h_x = np.array([[1, 0]], dtype=np.uint8)
    h_z = np.array([[0, 1]], dtype=np.uint8)
    with pytest.raises(InvalidCodeError):
        validate(h_x, h_z)


def test_invalid_code_error_is_a_value_error():
    """A subclass, not an unrelated type - existing except ValueError still works."""
    assert issubclass(InvalidCodeError, ValueError)
