"""BB generator reference test (spec/evals.md G-07..G-10, M0-CODES-02).

G-07 through G-10 are the single most important tests in the project: if the
generator does not reproduce the published Bravyi et al. 2024 [[72,12,6]]
bivariate bicycle code exactly, every label downstream measures something
other than what it claims. There is no tolerance to loosen here — these are
exact structural properties (n, k, check weight), not simulation output.

Distance (G-09, d_upper=6) is deliberately not asserted here. d_upper is a
decoder-assisted search result (M0-CODES-04) and CONTRACT.md keeps d_exact
and d_upper as distinct columns; nothing in this module computes either.
"""

import numpy as np

from qecscreen.codes.bb import generate
from qecscreen.linalg import check_css_commutation, gf2_rank, logical_qubit_count

# l=6, m=6, A = x^3 + y + y^2, B = y^3 + x + x^2 (Bravyi et al. 2024, Table 3).
# Each polynomial is a list of (x_exponent, y_exponent) monomial pairs.
L = 6
M = 6
A_EXPS = [(3, 0), (0, 1), (0, 2)]
B_EXPS = [(0, 3), (1, 0), (2, 0)]
SEED = 0


def test_g07_g08_reference_code_n_and_k():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    n = h_x.shape[1]
    assert n == 72  # G-07
    k = logical_qubit_count(h_x, h_z)  # also asserts CSS commutation (INV-8)
    assert k == 12  # G-08


def test_g10_all_check_weights_are_six():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    x_weights = h_x.sum(axis=1)
    z_weights = h_z.sum(axis=1)
    assert set(np.unique(x_weights).tolist()) == {6}
    assert set(np.unique(z_weights).tolist()) == {6}


def test_reference_code_css_commutation():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    check_css_commutation(h_x, h_z)  # raises on failure; a clean call is the assertion


def test_reference_code_shape():
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    lm = L * M
    assert h_x.shape == (lm, 2 * lm)
    assert h_z.shape == (lm, 2 * lm)


def test_reference_code_dtype_is_gf2_compatible():
    """qecscreen.linalg rejects bool and float; H_X/H_Z must be integer {0, 1}."""
    h_x, h_z = generate(L, M, A_EXPS, B_EXPS, SEED)
    assert np.issubdtype(h_x.dtype, np.integer)
    assert np.issubdtype(h_z.dtype, np.integer)
    assert set(np.unique(h_x).tolist()) <= {0, 1}
    assert set(np.unique(h_z).tolist()) <= {0, 1}
    # Never use numpy.linalg.matrix_rank on a check matrix (INV-8) - gf2_rank
    # must run cleanly on exactly what generate() returns, not a recast copy.
    assert gf2_rank(h_x) >= 0
    assert gf2_rank(h_z) >= 0


def test_determinism_same_args_same_seed_byte_identical():
    h_x_1, h_z_1 = generate(L, M, A_EXPS, B_EXPS, SEED)
    h_x_2, h_z_2 = generate(L, M, A_EXPS, B_EXPS, SEED)
    assert h_x_1.tobytes() == h_x_2.tobytes()
    assert h_z_1.tobytes() == h_z_2.tobytes()
    assert h_x_1.dtype == h_x_2.dtype
    assert h_z_1.dtype == h_z_2.dtype
