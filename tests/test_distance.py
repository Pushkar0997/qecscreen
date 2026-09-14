"""M0-CODES-04: estimate_d_upper reference and determinism tests.

d_upper is an UPPER bound from a randomised search: it can come out too
large but never too small. The two reference codes are the only guard
against a search that is too weak - a weak search fails upward, silently,
and looks entirely plausible. If either fails here, the search needs more
attempts or a better reduction; the fix is never to relax the assertion,
adjust the expected value, or mark it xfail (spec/decisions.md D-021).

d_exact is never asserted, returned, or populated anywhere in this module -
see CONTRACT.md's distance-provenance rule and qecscreen.codes.distance's
own module docstring.
"""

import pathlib
import re

from qecscreen.codes.bb import generate
from qecscreen.codes.distance import DEFAULT_ATTEMPTS, METHOD_NAME, estimate_d_upper

L = 6
M = 6
A_EXPS = [(3, 0), (0, 1), (0, 2)]
B_EXPS = [(0, 3), (1, 0), (2, 0)]
SEED = 0

GROSS_L = 12
GROSS_M = 6

H_X_72, H_Z_72 = generate(L, M, A_EXPS, B_EXPS, SEED)
H_X_GROSS, H_Z_GROSS = generate(GROSS_L, GROSS_M, A_EXPS, B_EXPS, SEED)


def test_reference_code_hits_published_distance():
    d_upper, method_name = estimate_d_upper(H_X_72, H_Z_72, seed=0, attempts=DEFAULT_ATTEMPTS)
    assert d_upper == 6
    assert method_name == METHOD_NAME


def test_gross_code_hits_published_distance():
    """The binding case: at DEFAULT_ATTEMPTS=64, 16x the measured reliability
    threshold of 4 (D-021), this must come out exactly 12, not higher."""
    d_upper, method_name = estimate_d_upper(
        H_X_GROSS, H_Z_GROSS, seed=0, attempts=DEFAULT_ATTEMPTS
    )
    assert d_upper == 12
    assert method_name == METHOD_NAME


def test_determinism_same_args_same_seed_identical_result():
    result_1 = estimate_d_upper(H_X_GROSS, H_Z_GROSS, seed=7, attempts=32)
    result_2 = estimate_d_upper(H_X_GROSS, H_Z_GROSS, seed=7, attempts=32)
    assert result_1 == result_2


def test_different_seeds_never_go_below_true_distance():
    """A weak search (few attempts) can overshoot upward but must never
    undershoot. Deliberately using a low attempt count (1) here, rather than
    DEFAULT_ATTEMPTS, so the seed-to-seed variation this test is about is
    actually visible instead of always landing on the exact answer."""
    for seed in range(10):
        d_72, _ = estimate_d_upper(H_X_72, H_Z_72, seed=seed, attempts=1)
        assert d_72 >= 6
        d_gross, _ = estimate_d_upper(H_X_GROSS, H_Z_GROSS, seed=seed, attempts=1)
        assert d_gross >= 12


def test_module_never_names_d_exact():
    """Source-grep guard, same style as tests/test_hygiene.py's INV-4 check."""
    src = pathlib.Path(__file__).resolve().parents[1] / "src" / "qecscreen" / "codes" / "distance.py"
    assert not re.search(r"d_exact", src.read_text(encoding="utf-8"))
