"""Circuit sanity for the Z-memory experiment (M0-CIRC-01..03, D-025, N-08).

A wrong circuit still produces plausible-looking LERs, so these tests check
the circuit itself: that its detectors are deterministic, that they actually
detect, and that the noise in it is exactly CONTRACT's uniform_depolarizing_v1
placement — no more, no less.

Codes: the [[72,12,6]] reference (weight 3+3 per check type) and a small
[[42,6,6]] code from mixed_3_5 (weight 3+5), so a phase depth other than 6 is
exercised. Nothing larger, to keep the default suite fast.
"""

from __future__ import annotations

import numpy as np
import pytest
import stim

from qecscreen.circuits.build import build_memory_circuit, z_logical_basis
from qecscreen.circuits.schedule import bb_schedule
from qecscreen.codes.bb import generate
from qecscreen.linalg import gf2_rank, logical_qubit_count
from qecscreen.protocol import SCHEDULING

REF = {"l": 6, "m": 6, "a_exps": [(3, 0), (0, 1), (0, 2)], "b_exps": [(0, 3), (1, 0), (2, 0)]}
REF_ROUNDS = 6  # r = d_upper = 6 (D-006)
MIXED = {"l": 3, "m": 7, "a_exps": [(4, 0), (0, 1), (1, 3)],
         "b_exps": [(0, 4), (1, 0), (2, 1), (3, 0), (0, 2)]}
MIXED_ROUNDS = 3

P = 0.001
NOISE_NAMES = {
    "DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Y_ERROR", "Z_ERROR",
    "PAULI_CHANNEL_1", "PAULI_CHANNEL_2", "E", "ELSE_CORRELATED_ERROR",
    "HERALDED_ERASE", "HERALDED_PAULI_CHANNEL_1",
}
GATE_NAMES = {"R", "RX", "CX", "M", "MX"}


def _matrices(code):
    return generate(code["l"], code["m"], code["a_exps"], code["b_exps"], seed=0)


def _ticks(circuit: stim.Circuit) -> list[list[stim.CircuitInstruction]]:
    """Split a flattened circuit into its ticks."""
    ticks: list[list[stim.CircuitInstruction]] = [[]]
    for inst in circuit.flattened():
        if inst.name == "TICK":
            ticks.append([])
        elif isinstance(inst, stim.CircuitInstruction):  # flattened: no REPEAT blocks
            ticks[-1].append(inst)
    return [t for t in ticks if t]


def _qubits(inst: stim.CircuitInstruction) -> list[int]:
    return [t.value for t in inst.targets_copy() if t.is_qubit_target]


def _expected_detector_count(m_x: int, m_z: int, rounds: int) -> int:
    # Z memory: round 1 has only Z-check detectors (compared against the
    # deterministic |0...0> preparation; X checks are random there). Rounds
    # 2..r compare every check with its previous round. The noiseless final
    # data measurement reconstructs one more value of every Z check.
    return m_z + (rounds - 1) * (m_x + m_z) + m_z


@pytest.fixture(scope="module")
def ref_clean():
    return build_memory_circuit(REF, p=0.0, rounds=REF_ROUNDS)


@pytest.fixture(scope="module")
def ref_noisy():
    return build_memory_circuit(REF, p=P, rounds=REF_ROUNDS)


# --- Schedule (M0-CIRC-01) ---------------------------------------------------


@pytest.mark.parametrize("code", [REF, MIXED], ids=["ref72", "mixed42"])
def test_schedule_layers_are_matchings_that_rebuild_the_checks(code):
    h_x, h_z = _matrices(code)
    lm = code["l"] * code["m"]
    sched = bb_schedule(code["l"], code["m"], code["a_exps"], code["b_exps"])
    depth = len(code["a_exps"]) + len(code["b_exps"])

    assert sched.method == SCHEDULING == "bb_monomial_matching_xz_phased_v1"
    # Konig minimum: max Tanner-graph degree, which is the check weight here.
    assert len(sched.x_layers) == len(sched.z_layers) == depth
    assert int(h_x.sum(axis=1).max()) == int(h_z.sum(axis=1).max()) == depth

    for layers, h in ((sched.x_layers, h_x), (sched.z_layers, h_z)):
        rebuilt = np.zeros_like(h)
        for layer in layers:
            checks = [c for c, _ in layer]
            data = [q for _, q in layer]
            # A perfect matching: every check once, lm distinct data qubits.
            assert sorted(checks) == list(range(lm))
            assert len(set(data)) == lm
            for c, q in layer:
                rebuilt[c, q] ^= 1
        # Every Tanner edge appears exactly once across the phase.
        assert np.array_equal(rebuilt, h)

    # Recorded monomial order: A then B in the X phase, B^T then A^T in Z.
    na = len(code["a_exps"])
    assert all(q < lm for layer in sched.x_layers[:na] for _, q in layer)
    assert all(q >= lm for layer in sched.x_layers[na:] for _, q in layer)
    nb = len(code["b_exps"])
    assert all(q < lm for layer in sched.z_layers[:nb] for _, q in layer)
    assert all(q >= lm for layer in sched.z_layers[nb:] for _, q in layer)


def test_every_tick_touches_each_qubit_at_most_once(ref_noisy):
    for tick in _ticks(ref_noisy):
        touched = [q for inst in tick if inst.name in GATE_NAMES for q in _qubits(inst)]
        assert len(touched) == len(set(touched))


def test_x_phase_precedes_z_phase_every_round(ref_clean):
    """Never interleaved (D-025): the phases are separate blocks of CX ticks."""
    n, m_x = 72, 36
    kinds = []
    for tick in _ticks(ref_clean):
        cx = [inst for inst in tick if inst.name == "CX"]
        if cx:
            controls = _qubits(cx[0])[0::2]
            kinds.append("X" if all(n <= c < n + m_x for c in controls) else "Z")
    assert kinds == (["X"] * 6 + ["Z"] * 6) * REF_ROUNDS


# --- Determinism and counts (M0-CIRC-03, N-08) -------------------------------


def test_p0_zero_detection_events(ref_clean):
    dets, obs = ref_clean.compile_detector_sampler(seed=0).sample(
        1000, separate_observables=True
    )
    assert dets.shape == (1000, 432)
    assert not dets.any()
    assert not obs.any()


@pytest.mark.parametrize("code,rounds", [(REF, REF_ROUNDS), (MIXED, MIXED_ROUNDS)],
                         ids=["ref72", "mixed42"])
def test_detector_error_model_builds(code, rounds):
    """Stim refuses a DEM when a detector or observable is non-deterministic,
    which is how a wrong schedule or wrong observable shows up."""
    circuit = build_memory_circuit(code, p=P, rounds=rounds)
    dem = circuit.detector_error_model(decompose_errors=False)
    assert dem.num_detectors == circuit.num_detectors
    assert dem.num_errors > 0


@pytest.mark.parametrize("rounds", [1, 2, REF_ROUNDS])
def test_detector_and_observable_counts(rounds):
    h_x, h_z = _matrices(REF)
    circuit = build_memory_circuit(REF, p=0.0, rounds=rounds)
    assert circuit.num_detectors == _expected_detector_count(h_x.shape[0], h_z.shape[0], rounds)
    assert circuit.num_observables == logical_qubit_count(h_x, h_z) == 12
    if rounds == REF_ROUNDS:
        assert circuit.num_detectors == 36 + 5 * 72 + 36 == 432


def test_mixed_code_counts():
    h_x, h_z = _matrices(MIXED)
    circuit = build_memory_circuit(MIXED, p=0.0, rounds=MIXED_ROUNDS)
    assert circuit.num_detectors == _expected_detector_count(21, 21, MIXED_ROUNDS)
    assert circuit.num_observables == logical_qubit_count(h_x, h_z) == 6
    dets = np.asarray(circuit.compile_detector_sampler(seed=1).sample(200))
    assert not dets.any()


def test_z_logical_basis_is_a_deterministic_basis():
    h_x, h_z = _matrices(REF)
    logicals = z_logical_basis(h_x, h_z)
    assert logicals.dtype == np.uint8 and logicals.shape == (12, 72)
    assert not ((h_x.astype(np.int64) @ logicals.T.astype(np.int64)) % 2).any()
    # Independent of each other and of the Z stabilisers.
    assert gf2_rank(np.vstack([h_z, logicals])) == gf2_rank(h_z) + 12
    assert np.array_equal(logicals, z_logical_basis(h_x, h_z))


# --- Sensitivity: the detectors actually detect ------------------------------


def _inject_after_round(circuit: stim.Circuit, round_index: int, gate: str, qubit: int):
    """Insert a deterministic Pauli error right after round ``round_index``'s
    X-ancilla measurement (0-based), before the next round touches the data."""
    out = stim.Circuit()
    seen = 0
    for inst in circuit.flattened():
        out.append(inst)
        if inst.name == "MX":
            if seen == round_index:
                out.append(gate, [qubit], 1.0)
            seen += 1
    assert seen == REF_ROUNDS
    return out


def _fired(circuit: stim.Circuit):
    dets, obs = circuit.compile_detector_sampler(seed=0).sample(1, separate_observables=True)
    coords = circuit.get_detector_coordinates()
    fired = sorted(tuple(int(c) for c in coords[int(i)]) for i in np.flatnonzero(dets[0]))
    return fired, obs[0]


@pytest.mark.parametrize("qubit", [0, 40])
def test_x_error_on_data_fires_its_z_checks(ref_clean, qubit):
    h_x, h_z = _matrices(REF)
    # X error between rounds 2 and 3 (0-based 1 and 2): every Z check on the
    # qubit flips from round 2 on, so only the round-2 comparison fires.
    fired, obs = _fired(_inject_after_round(ref_clean, 1, "X_ERROR", qubit))
    expected = sorted((int(c), 2, 0) for c in np.flatnonzero(h_z[:, qubit]))
    assert len(expected) == 3
    assert fired == expected
    logicals = z_logical_basis(h_x, h_z)
    assert np.array_equal(obs, logicals[:, qubit].astype(bool))


@pytest.mark.parametrize("qubit", [0, 40])
def test_z_error_on_data_fires_its_x_checks(ref_clean, qubit):
    h_x, _ = _matrices(REF)
    fired, obs = _fired(_inject_after_round(ref_clean, 1, "Z_ERROR", qubit))
    expected = sorted((int(c), 2, 1) for c in np.flatnonzero(h_x[:, qubit]))
    assert len(expected) == 3
    assert fired == expected
    assert not obs.any()  # Z memory: a Z error flips no Z observable


# --- Noise is exactly CONTRACT's uniform_depolarizing_v1 (D-025) -------------


def test_noise_channel_counts_match_contract(ref_noisy):
    h_x, h_z = _matrices(REF)
    n, m_x, m_z = 72, h_x.shape[0], h_z.shape[0]
    lm, depth, r = 36, 6, REF_ROUNDS
    total = n + m_x + m_z

    counts: dict[str, int] = {}
    noisy_meas = {"M": 0, "MX": 0}
    clean_meas = {"M": 0, "MX": 0}
    for inst in ref_noisy.flattened():
        assert isinstance(inst, stim.CircuitInstruction)
        name = inst.name
        if name in NOISE_NAMES:
            assert inst.gate_args_copy() == [P], name
            per = 2 if name == "DEPOLARIZE2" else 1
            counts[name] = counts.get(name, 0) + len(_qubits(inst)) // per
        elif name in ("M", "MX"):
            bucket = noisy_meas if inst.gate_args_copy() == [P] else clean_meas
            assert inst.gate_args_copy() in ([P], [])
            bucket[name] += len(_qubits(inst))

    # Per round: idle on data in the reset and measurement ticks; in each of
    # the 2*depth CX ticks, 2*lm qubits act and the rest idle.
    idle_per_round = 2 * n + 2 * depth * (total - 2 * lm)
    assert counts == {
        "DEPOLARIZE1": r * idle_per_round,
        "DEPOLARIZE2": r * 2 * depth * lm,
        "X_ERROR": r * m_z,  # after R on Z ancillas
        "Z_ERROR": r * m_x,  # after RX on X ancillas
    }
    assert counts["DEPOLARIZE1"] == 6 * 1008 and counts["DEPOLARIZE2"] == 6 * 432
    assert noisy_meas == {"M": r * m_z, "MX": r * m_x}
    # Final data measurement is noiseless.
    assert clean_meas == {"M": n, "MX": 0}


def test_noise_placement_per_tick(ref_noisy):
    """Every noise instruction sits where D-025 says, tick by tick."""
    total = 72 + 36 + 36
    ticks = _ticks(ref_noisy)
    # First tick is the noiseless data preparation, last the noiseless readout.
    for boundary in (ticks[0], ticks[-1]):
        assert not any(inst.name in NOISE_NAMES for inst in boundary)
        assert all(not inst.gate_args_copy() for inst in boundary if inst.name in GATE_NAMES)

    for tick in ticks[1:-1]:
        acted = {q for inst in tick if inst.name in GATE_NAMES for q in _qubits(inst)}
        idle = {q for inst in tick if inst.name == "DEPOLARIZE1" for q in _qubits(inst)}
        assert idle == set(range(total)) - acted
        cx = [q for inst in tick if inst.name == "CX" for q in _qubits(inst)]
        dep2 = [q for inst in tick if inst.name == "DEPOLARIZE2" for q in _qubits(inst)]
        assert dep2 == cx
        reset_r = {q for inst in tick if inst.name == "R" for q in _qubits(inst)}
        reset_rx = {q for inst in tick if inst.name == "RX" for q in _qubits(inst)}
        x_err = {q for inst in tick if inst.name == "X_ERROR" for q in _qubits(inst)}
        z_err = {q for inst in tick if inst.name == "Z_ERROR" for q in _qubits(inst)}
        assert x_err == reset_r and z_err == reset_rx
        # Gate noise follows its gate: after R/RX/CX, never before.
        names = [inst.name for inst in tick]
        for gate, noise in (("R", "X_ERROR"), ("RX", "Z_ERROR"), ("CX", "DEPOLARIZE2")):
            if gate in names:
                assert names.index(noise) > names.index(gate)
        # Nothing else, e.g. no Y_ERROR or PAULI_CHANNEL sneaking in.
        assert {inst.name for inst in tick} <= GATE_NAMES | {
            "DEPOLARIZE1", "DEPOLARIZE2", "X_ERROR", "Z_ERROR", "DETECTOR", "SHIFT_COORDS",
        }


def test_rejects_bad_arguments():
    with pytest.raises(ValueError):
        build_memory_circuit(REF, p=0.001, rounds=0)
    with pytest.raises(ValueError):
        build_memory_circuit(REF, p=-0.1, rounds=2)
    with pytest.raises(ValueError):
        build_memory_circuit(REF, p=1.0, rounds=2)
