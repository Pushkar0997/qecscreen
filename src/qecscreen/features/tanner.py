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

Cycles (M0-FEAT-02) are simple cycles, each counted once as a subgraph, not
once per starting vertex or direction. A Tanner graph is bipartite, so every
cycle has even length and alternates check, qubit. ``girth`` is the length of
the shortest cycle; a graph with no cycle has no girth and stores null
(CONTRACT: explicit nulls). No M0 code reaches that: a check of weight
``w >= 4`` on ``lm`` checks and ``2lm`` qubits gives more edges than vertices.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
import numpy as np

__all__ = ["cycle_counts", "graph_features", "tanner_graph"]


def _qubit_degree(h: np.ndarray) -> dict[str, Any]:
    """Qubit degree in the graph: the number of checks of this type a qubit is in."""
    degree = h.sum(axis=0, dtype=np.int64)
    return {
        "qubit_degree_min": int(degree.min()),
        "qubit_degree_max": int(degree.max()),
        "qubit_degree_mean": float(degree.mean()),
    }


def tanner_graph(h: np.ndarray) -> nx.Graph:
    """Qubits are vertices ``0..n-1``, checks ``n..n+m-1``; one edge per 1 in ``h``."""
    m, n = h.shape
    graph = nx.Graph()
    graph.add_nodes_from(range(n + m))
    checks, qubits = np.nonzero(h)
    graph.add_edges_from(zip(qubits.tolist(), (n + checks).tolist()))
    return graph


def cycle_counts(h: np.ndarray) -> tuple[int, int]:
    """``(4-cycles, 6-cycles)`` of the Tanner graph of ``h``, each simple cycle once.

    With ``O = h h^T`` (qubits two checks share) and ``T[a,b,c]`` (qubits three
    checks share): a 4-cycle is two checks and two shared qubits, so there are
    ``sum_{a<b} C(O_ab, 2)``. A 6-cycle is three checks ``a, b, c`` and three
    distinct qubits, one shared by each pair. Of the ``O_ab O_bc O_ca`` choices,
    inclusion-exclusion removes those reusing a qubit, which must lie in all
    three: ``O_ab O_bc O_ca - T (O_ab + O_bc + O_ca) + 2T``. Each 6-cycle is
    one unordered triple of checks and one such choice.
    """
    hi = h.astype(np.int64)
    o = hi @ hi.T
    m = o.shape[0]
    upper = np.triu_indices(m, 1)
    four = int((o[upper] * (o[upper] - 1) // 2).sum())

    t = np.einsum("aq,bq,cq->abc", hi, hi, hi)
    o_ab, o_bc, o_ca = o[:, :, None], o[None, :, :], o.T[:, None, :]
    choices = o_ab * o_bc * o_ca - t * (o_ab + o_bc + o_ca) + 2 * t
    a, b, c = np.ogrid[:m, :m, :m]
    distinct = (a != b) & (b != c) & (a != c)
    ordered = int(choices[distinct].sum())  # each unordered triple 3! times
    if ordered % 6:  # pragma: no cover - an identity, not a data condition
        raise AssertionError(f"ordered 6-cycle count {ordered} is not a multiple of 6")
    return four, ordered // 6


def _cycles(h: np.ndarray) -> dict[str, Any]:
    four, six = cycle_counts(h)
    if four:
        girth: int | None = 4
    elif six:
        girth = 6
    else:
        g = nx.girth(tanner_graph(h))
        girth = None if g == float("inf") else int(g)
    return {"cycle4_count": four, "cycle6_count": six, "girth": girth}


def graph_features(h: np.ndarray) -> dict[str, Any]:
    """Every Tanner-graph feature of ``h``, unsuffixed; the caller adds ``_x`` / ``_z``."""
    return {**_qubit_degree(h), **_cycles(h)}
