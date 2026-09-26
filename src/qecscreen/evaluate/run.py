"""M0-EVAL-01: seeded sample-and-decode with BP+OSD, stopping at MIN_FAILURES or MAX_SHOTS.

``sample_and_decode(circuit, seed=...)`` is the loop every label comes from
(D-026, CONTRACT "SAMPLING"). One ``stim`` detector sampler, seeded
explicitly, per code; batches of exactly ``SHOT_BATCH`` shots; the stopping
rule is checked between batches. There is no wall-clock input anywhere: stim's
seeded output depends on how shots are split into calls, so batch sizes must
be fixed for a seed to mean anything. Parallelism is across codes, one code
per process, and belongs to the caller. sinter is not used: its samplers are
unseeded and its batches are sized from timing.

``CompiledBpOsd`` is ldpc's ``BpOsdDecoder`` over the DEM's check matrix and
priors, configured with CONTRACT's ``DECODER_PARAMS`` and nothing else, whose
corrections are mapped to observable flips through the DEM's observable
matrix.

The DEM-to-matrix conversion is CONTRACT's ``dem_undecomposed_merge_by_symptom_v1``:
the DEM is built undecomposed (BP+OSD decodes hyperedges directly;
decomposition exists for matching decoders) and flattened. Mechanisms with
identical (detectors, observables) symptoms are merged into one column, their
probabilities combined as independent flips; mechanisms with the same
detectors but different observables stay separate columns. Columns are in
order of first appearance.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import stim
from ldpc import BpOsdDecoder

from qecscreen.protocol import DECODER_PARAMS, MAX_SHOTS, MIN_FAILURES, SHOT_BATCH

__all__ = [
    "DEM_TO_MATRIX",
    "DemMatrices",
    "detector_error_model",
    "dem_matrices",
    "CompiledBpOsd",
    "count_failures",
    "RunResult",
    "sample_and_decode",
]

# The one DEM-to-matrix conversion this module implements (CONTRACT, D-026).
# dem_matrices() refuses to run if DECODER_PARAMS names another.
DEM_TO_MATRIX = "dem_undecomposed_merge_by_symptom_v1"

# DECODER_PARAMS minus the two identity keys and the DEM conversion's name;
# everything else goes to ldpc as is.
_BPOSD_KWARGS = {
    k: v for k, v in DECODER_PARAMS.items() if k not in ("library", "decoder", "dem_to_matrix")
}


def detector_error_model(circuit: stim.Circuit) -> stim.DetectorErrorModel:
    """The DEM every label is decoded against: undecomposed, no gauge detectors."""
    return circuit.detector_error_model(decompose_errors=False)


@dataclass(frozen=True)
class DemMatrices:
    """``check_matrix`` (detectors x mechanisms), ``observables_matrix``
    (observables x mechanisms), both ``uint8`` CSC, and per-mechanism ``priors``."""

    check_matrix: sp.csc_matrix
    observables_matrix: sp.csc_matrix
    priors: np.ndarray


def dem_matrices(dem: stim.DetectorErrorModel) -> DemMatrices:
    """CONTRACT's ``dem_undecomposed_merge_by_symptom_v1``, exactly."""
    if DECODER_PARAMS["dem_to_matrix"] != DEM_TO_MATRIX:
        raise ValueError(
            f"DECODER_PARAMS names dem_to_matrix={DECODER_PARAMS['dem_to_matrix']!r}, "
            f"but this module implements {DEM_TO_MATRIX!r}"
        )
    columns: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {}
    priors: list[float] = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        dets: set[int] = set()
        obs: set[int] = set()
        for t in inst.targets_copy():
            if t.is_relative_detector_id():
                dets ^= {t.val}
            elif t.is_logical_observable_id():
                obs ^= {t.val}
            elif t.is_separator():  # pragma: no cover - the DEM is undecomposed
                raise ValueError("decomposed DEM; build it with detector_error_model()")
        key = (tuple(sorted(dets)), tuple(sorted(obs)))
        p = inst.args_copy()[0]
        if key in columns:
            j = columns[key]
            priors[j] = priors[j] * (1 - p) + p * (1 - priors[j])
        else:
            columns[key] = len(priors)
            priors.append(p)

    def _csc(rows_per_col: list[tuple[int, ...]], n_rows: int) -> sp.csc_matrix:
        indptr = np.cumsum([0] + [len(r) for r in rows_per_col])
        indices = np.array([i for r in rows_per_col for i in r], dtype=np.int64)
        data = np.ones(indices.size, dtype=np.uint8)
        return sp.csc_matrix((data, indices, indptr), shape=(n_rows, len(rows_per_col)))

    keys = list(columns)  # insertion order == column order
    return DemMatrices(
        check_matrix=_csc([d for d, _ in keys], dem.num_detectors),
        observables_matrix=_csc([o for _, o in keys], dem.num_observables),
        priors=np.array(priors, dtype=np.float64),
    )


class CompiledBpOsd:
    """BP+OSD preconfigured for one DEM.

    Telemetry: ``shots_decoded`` and ``osd_invocations`` (shots on which BP did
    not converge, so OSD ran). Counted per instance.
    """

    def __init__(self, dem: stim.DetectorErrorModel) -> None:
        mats = dem_matrices(dem)
        self.num_detectors = dem.num_detectors
        self.num_observables = dem.num_observables
        self.observables_matrix = mats.observables_matrix
        self.shots_decoded = 0
        self.osd_invocations = 0
        n_cols = mats.priors.size
        if n_cols == 0:
            # A noiseless DEM (p = 0): nothing can fire, nothing to correct.
            self.decoder = None
            return
        # OSD needs osd_order columns beyond an information set. ldpc does not
        # check this and segfaults, which kills the process.
        # n_cols - n_rows <= n_cols - rank, so this is conservative.
        if n_cols - self.num_detectors < _BPOSD_KWARGS["osd_order"]:
            raise ValueError(
                f"osd_order={_BPOSD_KWARGS['osd_order']} needs more than "
                f"{n_cols - self.num_detectors} free columns in a "
                f"{self.num_detectors}x{n_cols} check matrix"
            )
        self.decoder = BpOsdDecoder(
            mats.check_matrix, error_channel=mats.priors.tolist(), **_BPOSD_KWARGS
        )

    def decode_shots_bit_packed(self, *, bit_packed_detection_event_data: np.ndarray) -> np.ndarray:
        dets = np.unpackbits(
            bit_packed_detection_event_data, axis=1, count=self.num_detectors, bitorder="little"
        )
        pred = np.zeros((dets.shape[0], self.num_observables), dtype=np.uint8)
        for i, syndrome in enumerate(dets):
            self.shots_decoded += 1
            if self.decoder is None:
                if syndrome.any():  # pragma: no cover - impossible for a noiseless DEM
                    raise RuntimeError("detection event in a DEM with no error mechanisms")
                continue
            correction = self.decoder.decode(syndrome)
            if not self.decoder.converge:
                self.osd_invocations += 1
            pred[i] = (self.observables_matrix @ correction) % 2
        return np.packbits(pred, axis=1, bitorder="little")


def count_failures(predicted: np.ndarray, actual: np.ndarray, num_observables: int) -> int:
    """INV-4's failure event: shots where **any** observable prediction is wrong.

    Both arrays are bit packed little-endian, ``(shots, ceil(num_observables/8))``,
    the format stim samples in. Padding bits past ``num_observables`` are ignored.
    """
    wrong = np.unpackbits(
        np.bitwise_xor(predicted, actual), axis=1, count=num_observables, bitorder="little"
    )
    return int(np.count_nonzero(wrong.any(axis=1)))


@dataclass(frozen=True)
class RunResult:
    """Counts from one ``(code, p)`` run, plus what is needed to reproduce it.

    ``stopped_by`` is ``"min_failures"`` or ``"max_shots"``. ``samples_sha256``
    digests every sampled detection-event and observable byte in order, so two
    runs saw identical shots exactly when their digests match.
    ``decode_seconds`` is telemetry, never an input to anything.
    """

    seed: int
    batch_size: int
    shots: int
    failures: int
    stopped_by: str
    osd_invocations: int
    samples_sha256: str
    decode_seconds: float


def sample_and_decode(
    circuit: stim.Circuit,
    *,
    seed: int,
    batch_size: int = SHOT_BATCH,
    max_shots: int = MAX_SHOTS,
) -> RunResult:
    """Sample ``circuit`` with a stim sampler seeded by ``seed`` and decode with BP+OSD.

    Batches of exactly ``batch_size`` shots, until at least ``MIN_FAILURES``
    failures (INV-3) or ``max_shots`` shots, checked between batches. Same
    circuit, seed, batch size, stim version and machine SIMD width give the
    same shots and failures (stim's seeding contract).

    ``batch_size`` and ``max_shots`` default to CONTRACT's ``SHOT_BATCH`` and
    ``MAX_SHOTS``; smaller values exist for tests. ``max_shots`` may not exceed
    ``MAX_SHOTS`` and must be a whole number of batches, so every batch in a
    run has the same size.
    """
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError(f"seed must be an int in range(2**64); got {seed!r}")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError(f"batch_size must be a positive int; got {batch_size!r}")
    if not 0 < max_shots <= MAX_SHOTS:
        raise ValueError(f"max_shots must be in (0, MAX_SHOTS={MAX_SHOTS}]; got {max_shots!r}")
    if max_shots % batch_size:
        raise ValueError(
            f"max_shots={max_shots} is not a whole number of batch_size={batch_size} batches"
        )

    decoder = CompiledBpOsd(detector_error_model(circuit))
    sampler = circuit.compile_detector_sampler(seed=seed)
    digest = hashlib.sha256()
    shots = failures = 0
    decode_seconds = 0.0
    while failures < MIN_FAILURES and shots < max_shots:
        dets, obs = sampler.sample(batch_size, separate_observables=True, bit_packed=True)
        digest.update(dets.tobytes())
        digest.update(obs.tobytes())
        start = time.perf_counter()
        pred = decoder.decode_shots_bit_packed(bit_packed_detection_event_data=dets)
        decode_seconds += time.perf_counter() - start
        failures += count_failures(pred, obs, circuit.num_observables)
        shots += batch_size

    return RunResult(
        seed=seed,
        batch_size=batch_size,
        shots=shots,
        failures=failures,
        stopped_by="min_failures" if failures >= MIN_FAILURES else "max_shots",
        osd_invocations=decoder.osd_invocations,
        samples_sha256=digest.hexdigest(),
        decode_seconds=decode_seconds,
    )
