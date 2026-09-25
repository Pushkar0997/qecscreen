"""M0-EVAL-01 (decoder half): BP+OSD built from the detector error model.

The decoder is a ``sinter.Decoder`` whose compiled form wraps ldpc's
``BpOsdDecoder`` with CONTRACT's DECODER_PARAMS exactly. Sampling here is
seeded stim, never sinter: sinter seeds its samplers from OS entropy, which
CONTRACT's explicit-seed convention does not allow (see AGENT_LOG (mm)), so
the stopping-rule loop is not built yet and these tests decode fixed,
seeded shot counts.

Codes: [[72,12,6]] (the reference) where the claim is about it, and a
[[12,2,3]] BB code from ``pair_2_2`` where the claim needs many shots.
BP+OSD at osd_order=10 costs ~1-2 s/shot on [[72,12,6]], ~1 ms on the
small code.
"""

from __future__ import annotations

import pickle

import numpy as np
import pytest
import sinter
import stim

from qecscreen.circuits.build import build_memory_circuit
from qecscreen.evaluate.label import make_label
from qecscreen.evaluate.run import (
    BpOsdSinterDecoder,
    CompiledBpOsd,
    count_failures,
    dem_matrices,
    detector_error_model,
)
from qecscreen.protocol import DECODER_PARAMS

P_PILOT = 0.005  # CONTRACT.md P_PILOT; protocol.py does not export it (see AGENT_LOG (mm))

REF = {"l": 6, "m": 6, "a_exps": [(3, 0), (0, 1), (0, 2)], "b_exps": [(0, 3), (1, 0), (2, 0)]}
REF_ROUNDS = 6
SMALL = {"l": 2, "m": 3, "a_exps": [(1, 0), (0, 2)], "b_exps": [(0, 1), (2, 0)]}  # [[12,2,3]]
SMALL_ROUNDS = 3


def _compile(circuit: stim.Circuit) -> CompiledBpOsd:
    return BpOsdSinterDecoder().compile_decoder_for_dem(dem=detector_error_model(circuit))


def _sample(circuit: stim.Circuit, shots: int, seed: int):
    dets, obs = circuit.compile_detector_sampler(seed=seed).sample(
        shots, separate_observables=True, bit_packed=True
    )
    return dets, obs


def _decoded_failures(circuit: stim.Circuit, shots: int, seed: int) -> tuple[int, int]:
    """(BP+OSD failures, trivial-decoder failures) on the same seeded shots."""
    dets, obs = _sample(circuit, shots, seed)
    pred = _compile(circuit).decode_shots_bit_packed(bit_packed_detection_event_data=dets)
    trivial = np.zeros_like(obs)
    num_obs = circuit.num_observables
    return count_failures(pred, obs, num_obs), count_failures(trivial, obs, num_obs)


# --- the decoder is CONTRACT's decoder --------------------------------------


def test_compiled_decoder_uses_contract_params_exactly():
    compiled = _compile(build_memory_circuit(SMALL, P_PILOT, SMALL_ROUNDS))
    d = compiled.decoder
    assert d.bp_method == DECODER_PARAMS["bp_method"]
    assert d.max_iter == DECODER_PARAMS["max_iter"]
    assert d.ms_scaling_factor == DECODER_PARAMS["ms_scaling_factor"]
    assert d.osd_method.lower() == DECODER_PARAMS["osd_method"]
    assert d.osd_order == DECODER_PARAMS["osd_order"]
    assert type(d).__name__ == DECODER_PARAMS["decoder"]
    assert type(d).__module__.split(".")[0] == DECODER_PARAMS["library"]


def test_decoder_is_a_picklable_sinter_decoder():
    """sinter ships decoders to worker processes by pickling."""
    dec = BpOsdSinterDecoder()
    assert isinstance(dec, sinter.Decoder)
    assert isinstance(pickle.loads(pickle.dumps(dec)), BpOsdSinterDecoder)
    assert isinstance(_compile(build_memory_circuit(SMALL, P_PILOT, SMALL_ROUNDS)), sinter.CompiledDecoder)


def test_dem_matrices_match_the_dem():
    """One column per distinct (detectors, observables) symptom, priors from the DEM."""
    circuit = build_memory_circuit(SMALL, P_PILOT, SMALL_ROUNDS)
    dem = detector_error_model(circuit)
    mats = dem_matrices(dem)
    assert mats.check_matrix.shape == (dem.num_detectors, mats.priors.size)
    assert mats.observables_matrix.shape == (dem.num_observables, mats.priors.size)
    assert mats.check_matrix.dtype == mats.observables_matrix.dtype == np.uint8
    assert np.all((mats.priors > 0) & (mats.priors < 0.5))
    symptoms = {
        (tuple(mats.check_matrix[:, j].indices), tuple(mats.observables_matrix[:, j].indices))
        for j in range(mats.priors.size)
    }
    assert len(symptoms) == mats.priors.size  # merged, no duplicate columns
    # Every error mechanism in the DEM lands in exactly one column.
    n_mech = sum(1 for inst in dem.flattened() if inst.type == "error")
    assert n_mech >= mats.priors.size


def test_dem_is_not_decomposed():
    """BP+OSD decodes hyperedges directly; decomposition is a matching-decoder need."""
    dem = detector_error_model(build_memory_circuit(SMALL, P_PILOT, SMALL_ROUNDS))
    assert not any(
        t.is_separator() for inst in dem.flattened() if inst.type == "error" for t in inst.targets_copy()
    )


def test_osd_order_larger_than_free_columns_raises_instead_of_crashing():
    """ldpc segfaults (kills the process) when osd_order exceeds the free columns."""
    dem = stim.DetectorErrorModel("error(0.1) D0\nerror(0.1) D1\nerror(0.1) D0 D1 L0")
    with pytest.raises(ValueError, match="osd_order"):
        BpOsdSinterDecoder().compile_decoder_for_dem(dem=dem)


# --- INV-4 failure event -----------------------------------------------------


def test_failure_is_any_observable_flipped():
    num_obs = 12
    actual = np.zeros((4, num_obs), dtype=np.uint8)
    pred = actual.copy()
    pred[1, 11] = 1  # one wrong observable out of twelve is a failure
    pred[2, :] = 1  # all twelve wrong is one failure, not twelve
    packed = lambda a: np.packbits(a, axis=1, bitorder="little")
    assert count_failures(packed(pred), packed(actual), num_obs) == 2


def test_failure_count_ignores_bit_packing_padding():
    """12 observables pack into 2 bytes; the 4 padding bits must not count."""
    pred = np.zeros((3, 2), dtype=np.uint8)
    actual = np.zeros((3, 2), dtype=np.uint8)
    actual[:, 1] = 0b1111_0000  # padding bits only (observables 12..15 do not exist)
    assert count_failures(pred, actual, 12) == 0


# --- behaviour ---------------------------------------------------------------


@pytest.mark.parametrize("code, rounds", [(REF, REF_ROUNDS), (SMALL, SMALL_ROUNDS)], ids=["ref72", "small12"])
def test_p0_gives_zero_failures(code, rounds):
    circuit = build_memory_circuit(code, 0.0, rounds)
    decoded, trivial = _decoded_failures(circuit, 2_000, seed=0)
    assert decoded == trivial == 0
    label = make_label(p=0.0, rounds=rounds, k=circuit.num_observables, shots=2_000,
                       failures=decoded, decode_seconds=0.0)
    assert label.censored and label.true_ler is None


def test_zero_syndrome_decodes_to_no_flip_at_p_pilot():
    """The noisy decoder, not just the empty-DEM path, maps silence to no correction."""
    circuit = build_memory_circuit(REF, P_PILOT, REF_ROUNDS)
    compiled = _compile(circuit)
    zeros = np.zeros((3, (circuit.num_detectors + 7) // 8), dtype=np.uint8)
    pred = compiled.decode_shots_bit_packed(bit_packed_detection_event_data=zeros)
    assert pred.shape == (3, (circuit.num_observables + 7) // 8)
    assert not pred.any()
    assert compiled.osd_invocations == 0


def test_telemetry_counts_shots_and_osd_invocations():
    circuit = build_memory_circuit(SMALL, 0.01, SMALL_ROUNDS)
    compiled = _compile(circuit)
    dets, _ = _sample(circuit, 300, seed=1)
    compiled.decode_shots_bit_packed(bit_packed_detection_event_data=dets)
    assert compiled.shots_decoded == 300
    assert 0 < compiled.osd_invocations < 300  # at p=0.01 BP converges on some shots, not all


@pytest.mark.slow
def test_bposd_beats_trivial_decoder_by_a_wide_margin_on_ref72():
    """At p=0.001 most shots flip some observable if left uncorrected; BP+OSD
    corrects almost all of them. ~25 s: every shot runs OSD at order 10."""
    decoded, trivial = _decoded_failures(build_memory_circuit(REF, 0.001, REF_ROUNDS), 20, seed=3)
    assert trivial >= 10, trivial
    assert decoded <= 2, decoded
    assert decoded * 5 <= trivial


def test_bposd_beats_trivial_decoder_on_small_code():
    decoded, trivial = _decoded_failures(build_memory_circuit(SMALL, 0.002, SMALL_ROUNDS), 2_000, seed=4)
    assert trivial >= 300, trivial
    assert decoded * 10 <= trivial, (decoded, trivial)


@pytest.mark.slow
def test_ler_increases_with_p():
    """Non-censored labels, strictly increasing, with disjoint intervals."""
    labels = []
    for i, p in enumerate((0.003, 0.006, 0.012)):
        circuit = build_memory_circuit(SMALL, p, SMALL_ROUNDS)
        shots = 4_000
        decoded, _ = _decoded_failures(circuit, shots, seed=10 + i)
        labels.append(make_label(p=p, rounds=SMALL_ROUNDS, k=circuit.num_observables,
                                 shots=shots, failures=decoded, decode_seconds=0.0))
    assert not any(lab.censored for lab in labels), [lab.failures for lab in labels]
    for lo, hi in zip(labels, labels[1:]):
        assert lo.true_ler < hi.true_ler
        assert lo.true_ler_ci_high < hi.true_ler_ci_low
