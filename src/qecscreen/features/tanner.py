"""Tanner-graph features of one check matrix (M0-FEAT-01, owner decision 2026-10-01).

Each check type has its own Tanner graph: the bipartite graph of ``H_X``
(qubits and X checks), and separately of ``H_Z``. Every graph feature is
computed on each and stored twice, as ``<name>_x`` and ``<name>_z``. The
stacked graph of ``[H_X; H_Z]`` is not used: an X check and a Z check overlap
on an even number of qubits (CSS commutation), so its 4-cycles are forced,
and it has some in all 244 M0 codes. They say nothing about a code beyond
that it is CSS.

The functions here take one matrix ``h`` (checks x qubits, CONTRACT
orientation). Every check and every qubit is a vertex.
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["graph_features"]


def _qubit_degree(h: np.ndarray) -> dict[str, Any]:
    """Qubit degree in the graph: the number of checks of this type a qubit is in."""
    degree = h.sum(axis=0, dtype=np.int64)
    return {
        "qubit_degree_min": int(degree.min()),
        "qubit_degree_max": int(degree.max()),
        "qubit_degree_mean": float(degree.mean()),
    }


def graph_features(h: np.ndarray) -> dict[str, Any]:
    """Every Tanner-graph feature of ``h``, unsuffixed; the caller adds ``_x`` / ``_z``."""
    return {**_qubit_degree(h)}
