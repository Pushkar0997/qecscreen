"""Code validity, verified rather than assumed (CONTRACT.md INV-8).

Lives in its own module rather than ``codes/__init__.py``: it is a
substantial, independently-testable unit of logic that applies to a check
matrix pair from *any* construction program (``bb.py``, and later ``gb.py``,
``hgp.py``), not the package's re-export surface. ``codes/__init__.py`` stays
the placeholder it already is.

Every check here is delegated to ``qecscreen.linalg`` — this module adds no
new GF(2) arithmetic of its own, because INV-8's own text names NumPy's
floating-point rank function as "a real and common bug" and the way to avoid
reintroducing it is to have exactly one place that does GF(2) math.
"""

from __future__ import annotations

import numpy as np

from qecscreen.linalg import logical_qubit_count

__all__ = ["InvalidCodeError", "validate"]


class InvalidCodeError(ValueError):
    """Raised by ``validate()`` when H_X/H_Z do not form a valid CSS code.

    A subclass of ``ValueError`` (so existing ``except ValueError`` handling
    still catches it) but named specifically so a caller can distinguish "this
    is not a valid code" (INV-8) from an unrelated ``ValueError`` raised for a
    bad argument somewhere else in the codebase.
    """


def validate(h_x: np.ndarray, h_z: np.ndarray) -> tuple[int, int]:
    """Verify ``H_X``/``H_Z`` form a valid CSS code; return ``(n, k)``.

    Enforces, in order:

    1. Both matrices are integer arrays with entries in ``{0, 1}`` — bool and
       float are rejected before any GF(2) work (``qecscreen.linalg``'s
       ``_as_gf2`` discipline).
    2. Both have the same column count; that count is ``n``.
    3. ``H_X @ H_Z.T == 0`` over GF(2) (CSS commutation).
    4. ``k = n - gf2_rank(H_X) - gf2_rank(H_Z)``, computed over GF(2), never
       with floating-point rank.
    5. ``k >= 1`` — a code with ``k = 0`` encodes nothing and is not a valid
       candidate.

    Raises ``InvalidCodeError`` on any failure. Never returns a bool, never
    warns, never logs and continues — CONTRACT.md INV-8 is explicit that
    validity is verified, never assumed.
    """
    try:
        k = logical_qubit_count(h_x, h_z)  # checks 1-4: dtype/value, shape, commutation, rank
    except ValueError as exc:
        raise InvalidCodeError(str(exc)) from exc

    n = np.asarray(h_x).shape[1]
    if k < 1:
        raise InvalidCodeError(
            f"k={k}: a code with k < 1 encodes nothing and is not a valid candidate "
            "(CONTRACT.md INV-8)"
        )
    return n, k
