"""Structural features of a code from its check matrices (M0-FEAT-01).

Everything here is a function of ``H_X``, ``H_Z`` and the code's ``d_upper``,
itself a function of the code (``estimate_d_upper``, seeded). No measurement
enters: see ``qecscreen.features.table`` for how a code reaches this module.

Names follow INV-5: ``d_upper`` is the randomised upper bound, and Φ = kd²/n
computed from it is ``phi_from_d_upper``, the same formula as the measurement
row's column (``evaluate.rows.build_row``).

``check_weight_*`` is over every check, X and Z together (as evals G-10's "all
check weights"). The qubit-degree statistics of M0-FEAT-01 are not here yet:
which Tanner graph a degree is taken in is not pinned.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from qecscreen.codes.validate import validate

__all__ = ["structural_features"]


def structural_features(h_x: np.ndarray, h_z: np.ndarray, d_upper: int) -> dict[str, Any]:
    """``n``, ``k``, ``d_upper``, ``phi_from_d_upper``, check-weight min/max/mean, ``n_ancilla``, ``n_total``."""
    n, k = validate(h_x, h_z)  # INV-8: k by GF(2) rank
    weights = np.concatenate([h_x.sum(axis=1, dtype=np.int64), h_z.sum(axis=1, dtype=np.int64)])
    n_ancilla = h_x.shape[0] + h_z.shape[0]  # one ancilla per check (CONTRACT, qubit indexing)
    return {
        "n": int(n),
        "k": int(k),
        "d_upper": int(d_upper),
        "phi_from_d_upper": k * d_upper**2 / n,
        "check_weight_min": int(weights.min()),
        "check_weight_max": int(weights.max()),
        "check_weight_mean": float(weights.mean()),
        "n_ancilla": int(n_ancilla),
        "n_total": int(n + n_ancilla),
    }
