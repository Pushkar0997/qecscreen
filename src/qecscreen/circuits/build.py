"""Z-basis memory circuit for a BB code under ``uniform_depolarizing_v1`` (D-025).

Layout, every choice pinned in CONTRACT.md and D-025 (ancilla timing as
amended 2026-09-25):

    tick 0          R on all data qubits, noiseless (initial preparation)
    each of r rounds
      open tick     RX X-ancillas + Z_ERROR(p); in rounds after the first,
                    M(p) on the previous round's Z-ancillas in the same tick
      X phase       one CX tick per monomial, X-ancilla -> data, DEPOLARIZE2(p)
                    on each pair, DEPOLARIZE1(p) on every other qubit
      swap tick     MX(p) X-ancillas; R Z-ancillas + X_ERROR(p)
      Z phase       likewise, data -> Z-ancilla
    last tick       M(p) on the last round's Z-ancillas; M on all data qubits,
                    noiseless (final readout)

Every tick puts DEPOLARIZE1(p) on each qubit it does not act on. Each ancilla
is reset in the tick straight before its phase and measured in the tick
straight after it, so no ancilla idles while it holds syndrome information;
its idle ticks all fall between its measurement and its next reset, where
they cannot affect any outcome. The Z measurement of round t shares a tick
with the X reset of round t+1 (and the last one with the data readout), so a
round is still 2(|A|+|B|) + 2 ticks, as before the amendment.

There are no single-qubit gates, so CONTRACT's single-qubit-gate line covers
idles only. The boundaries are noiseless so that all noise lives inside the
``r`` rounds INV-4 divides by: boundary noise happens once per experiment,
and after dividing by ``r = d_upper`` it would bias the per-round rate by
distance, which is the ranking this project measures.

Qubit indexing (CONTRACT): data ``0..n-1``, X-ancillas ``n..n+m_x-1``,
Z-ancillas ``n+m_x..n+m_x+m_z-1``.

Detector coordinates are ``(check index, round, basis)`` with basis 0 for Z
checks and 1 for X checks; the final data-derived Z-check detectors carry
round ``r``. Observables are the ``k`` Z logicals from ``z_logical_basis``.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import stim

from qecscreen.circuits.schedule import bb_schedule
from qecscreen.codes.bb import generate
from qecscreen.codes.validate import validate
from qecscreen.linalg import gf2_nullspace, gf2_rank

__all__ = ["build_memory_circuit", "z_logical_basis"]


def z_logical_basis(h_x: np.ndarray, h_z: np.ndarray) -> np.ndarray:
    """``k`` independent Z logical operators, one per row, deterministically.

    Walks the rows of ``gf2_nullspace(H_X)`` in order (every Z operator that
    commutes with the X checks) and keeps each one that raises the GF(2) rank
    of ``H_Z`` stacked with the rows kept so far. No RNG: the same code always
    yields the same observables.
    """
    _, k = validate(h_x, h_z)
    kept: list[np.ndarray] = []
    rank = gf2_rank(h_z)
    for v in gf2_nullspace(h_x):
        new_rank = gf2_rank(np.vstack([h_z, *kept, v]))
        if new_rank > rank:
            kept.append(v)
            rank = new_rank
            if len(kept) == k:
                break
    if len(kept) != k:  # pragma: no cover - impossible for a validated code
        raise RuntimeError(f"found {len(kept)} Z logicals, expected k={k}")
    return np.array(kept, dtype=np.uint8)


def build_memory_circuit(code: Mapping[str, Any], p: float, rounds: int) -> stim.Circuit:
    """Z-memory circuit with ``rounds`` noisy rounds for a BB code.

    ``code`` is a BB parameter mapping with ``l``, ``m``, ``a_exps`` and
    ``b_exps`` (as ``sample_bb_params`` emits). ``rounds`` is the total number
    of noisy rounds, the first included (D-006: ``r = d_upper``).
    """
    if not isinstance(rounds, (int, np.integer)) or rounds < 1:
        raise ValueError(f"rounds must be an int >= 1; got {rounds!r}")
    if not 0.0 <= p < 1.0:
        raise ValueError(f"p must be in [0, 1); got {p!r}")

    l, m = int(code["l"]), int(code["m"])
    a_exps = [tuple(e) for e in code["a_exps"]]
    b_exps = [tuple(e) for e in code["b_exps"]]
    h_x, h_z = generate(l, m, a_exps, b_exps, seed=0)
    validate(h_x, h_z)  # INV-8: before any circuit is built
    sched = bb_schedule(l, m, a_exps, b_exps)
    logicals = z_logical_basis(h_x, h_z)

    n = h_x.shape[1]
    m_x, m_z = h_x.shape[0], h_z.shape[0]
    data = list(range(n))
    x_anc = [n + c for c in range(m_x)]
    z_anc = [n + m_x + c for c in range(m_z)]
    everyone = set(range(n + m_x + m_z))

    c = stim.Circuit()
    n_meas = 0  # absolute measurement index, for rec[] lookbacks

    def rec(i: int) -> stim.GateTarget:
        return stim.target_rec(i - n_meas)

    c.append("R", data)
    c.append("TICK")

    prev_x: list[int] | None = None
    prev_z: list[int] | None = None

    def measure_z(t: int) -> None:
        """M(p) on the Z-ancillas and round ``t``'s Z-check detectors."""
        nonlocal n_meas, prev_z
        c.append("M", z_anc, p)
        this_z = list(range(n_meas, n_meas + m_z))
        n_meas += m_z
        for check in range(m_z):
            targets = [rec(this_z[check])]
            if prev_z is not None:
                targets.append(rec(prev_z[check]))
            c.append("DETECTOR", targets, (check, t, 0))
        prev_z = this_z

    def cx_phase(layers, ancillas: list[int], anc_first: bool) -> None:
        for layer in layers:
            pairs: list[int] = []
            for check, q in layer:
                pairs += [ancillas[check], q] if anc_first else [q, ancillas[check]]
            c.append("CX", pairs)
            c.append("DEPOLARIZE2", pairs, p)
            c.append("DEPOLARIZE1", sorted(everyone - set(pairs)), p)
            c.append("TICK")

    for t in range(rounds):
        # Open tick: the previous round's Z-ancillas are read out alongside
        # the X-ancilla reset, so no extra tick is spent on them.
        if t > 0:
            measure_z(t - 1)
        c.append("RX", x_anc)
        c.append("Z_ERROR", x_anc, p)
        c.append("DEPOLARIZE1", data + (z_anc if t == 0 else []), p)
        c.append("TICK")

        cx_phase(sched.x_layers, x_anc, True)

        # Swap tick: X-ancillas read out, Z-ancillas reset for their phase.
        c.append("MX", x_anc, p)
        this_x = list(range(n_meas, n_meas + m_x))
        n_meas += m_x
        if prev_x is not None:  # X checks are random in round 0 of Z memory
            for check in range(m_x):
                c.append("DETECTOR", [rec(this_x[check]), rec(prev_x[check])], (check, t, 1))
        prev_x = this_x
        c.append("R", z_anc)
        c.append("X_ERROR", z_anc, p)
        c.append("DEPOLARIZE1", data, p)
        c.append("TICK")

        cx_phase(sched.z_layers, z_anc, False)

    # Last tick: the final Z-ancilla readout shares the tick with the
    # noiseless data readout, so data never idle outside the r rounds.
    measure_z(rounds - 1)
    c.append("DEPOLARIZE1", x_anc, p)
    c.append("M", data)
    data_meas = list(range(n_meas, n_meas + n))
    n_meas += n
    assert prev_z is not None
    for check in range(m_z):
        targets = [rec(data_meas[q]) for q in np.flatnonzero(h_z[check])]
        targets.append(rec(prev_z[check]))
        c.append("DETECTOR", targets, (check, rounds, 0))
    for i, row in enumerate(logicals):
        c.append("OBSERVABLE_INCLUDE", [rec(data_meas[q]) for q in np.flatnonzero(row)], i)
    return c
