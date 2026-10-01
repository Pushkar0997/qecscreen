"""Structural features of a code from its check matrices (M0-FEAT-01).

Everything here is a function of ``H_X``, ``H_Z`` and the code's ``d_upper``,
itself a function of the code (``estimate_d_upper``, seeded). No measurement
enters: see ``qecscreen.features.table`` for how a code reaches this module.

Names follow INV-5: ``d_upper`` is the randomised upper bound, and Φ = kd²/n
computed from it is ``phi_from_d_upper``, the same formula as the measurement
row's column (``evaluate.rows.build_row``).

``check_weight_*`` is over every check, X and Z together (as evals G-10's "all
check weights"). Tanner-graph features (``qecscreen.features.tanner``) are
per check type: each ``<name>`` is stored as ``<name>_x`` (graph of ``H_X``)
and ``<name>_z`` (graph of ``H_Z``), in ``GRAPH_FEATURES`` order, x then z.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from qecscreen.codes.validate import validate
from qecscreen.features.tanner import graph_features

__all__ = ["GRAPH_FEATURES", "structural_features"]

# Tanner-graph feature names, each stored per check type with suffix _x / _z.
GRAPH_FEATURES = ("qubit_degree_min", "qubit_degree_max", "qubit_degree_mean")


def structural_features(h_x: np.ndarray, h_z: np.ndarray, d_upper: int) -> dict[str, Any]:
    """``n``, ``k``, ``d_upper``, ``phi_from_d_upper``, check weights, ``n_ancilla``, ``n_total``, graph features."""
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
        **_per_type(graph_features(h_x), graph_features(h_z)),
    }


def _per_type(x: dict[str, Any], z: dict[str, Any]) -> dict[str, Any]:
    if tuple(x) != GRAPH_FEATURES or tuple(z) != GRAPH_FEATURES:
        raise AssertionError(f"graph features {tuple(x)} are not GRAPH_FEATURES {GRAPH_FEATURES}")
    return {f"{name}_{t}": values[name] for name in GRAPH_FEATURES for t, values in (("x", x), ("z", z))}
