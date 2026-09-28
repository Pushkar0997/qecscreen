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

import dataclasses
import hashlib
import os
import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import stim
from ldpc import BpOsdDecoder

from qecscreen import provenance as _provenance
from qecscreen.evaluate.checkpoint import (
    PROVENANCE_FIELDS,
    BatchRecord,
    CodeCheckpoint,
    ProvenanceMismatchError,
    SampleDigestMismatchError,
)
from qecscreen.protocol import DECODER_PARAMS, MAX_SHOTS, MIN_FAILURES, SHOT_BATCH

__all__ = [
    "DEM_TO_MATRIX",
    "DemMatrices",
    "detector_error_model",
    "dem_matrices",
    "CompiledBpOsd",
    "count_failures",
    "RunResult",
    "run_provenance",
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


def run_provenance() -> dict[str, str | None]:
    """This process's ``commit_sha``, ``stim_version`` and ``cpu_class``, read
    from ``qecscreen.provenance`` at call time (D-017, D-027). Written into
    every checkpoint shard (D-032)."""
    return {
        "commit_sha": _provenance.resolved_commit(),
        "stim_version": _provenance.stim_version(),
        "cpu_class": _provenance.cpu_class(),
    }


@dataclass(frozen=True)
class RunResult:
    """Counts from one ``(code, p)`` run, plus what is needed to reproduce it.

    ``stopped_by`` is ``"min_failures"`` or ``"max_shots"``, or ``"deadline"``
    for a checkpointed run that stopped early and has not finished. ``samples_sha256``
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
    checkpoint_dir: str | os.PathLike[str] | None = None,
    deadline: float | None = None,
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

    With ``checkpoint_dir`` (one directory per code and p), every completed
    batch is flushed there before the next is sampled (M0-EVAL-04,
    ``qecscreen.evaluate.checkpoint``). A code that has already finished
    returns its stored result without sampling or decoding. A partial one
    re-creates the seeded sampler, draws and discards its completed batches,
    each checked against its shard's digest, and decodes from the next batch,
    so it ends with exactly the shots and failures of an uninterrupted run.
    Re-drawn shots that differ from the recorded ones (another stim version
    or CPU class, D-027) raise ``SampleDigestMismatchError`` rather than
    splice two streams into one count. Every shard records this process's
    ``run_provenance()``; a resume by a process whose provenance differs from
    the shards', or shards that disagree among themselves, raise
    ``ProvenanceMismatchError`` before anything is drawn (D-032). Both are
    ``CheckpointMismatchError``s.

    ``deadline`` (``time.time()`` seconds; needs ``checkpoint_dir``) is checked
    between batches, never inside one: after a batch is flushed, the run stops
    if the next batch, taking as long as the last one did, would end past the
    deadline. The first batch of a call always runs, so every call makes
    progress. A run stopped this way returns ``stopped_by="deadline"``, writes
    no result, and resumes from its shards on the next call. A session that
    ends this way ends cleanly, and never relies on being killed (M0-RUN-01).
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
    if deadline is not None and checkpoint_dir is None:
        raise ValueError("a deadline needs a checkpoint_dir: a run stopped early must be resumable")

    checkpoint = None
    completed: list[BatchRecord] = []
    if checkpoint_dir is not None:
        here = run_provenance()
        checkpoint = CodeCheckpoint(
            checkpoint_dir, seed=seed, batch_size=batch_size, max_shots=max_shots, provenance=here
        )
        stored = checkpoint.result()
        if stored is not None:
            return RunResult(**stored)
        completed = checkpoint.batches()
        recorded = checkpoint.shard_provenance()
        for field in PROVENANCE_FIELDS:
            if recorded is not None and recorded[field] != here[field]:
                raise ProvenanceMismatchError(
                    f"{checkpoint_dir} was written with {field}={recorded[field]!r}; this process "
                    f"has {here[field]!r}. One row's batches come from one {field} (D-032)", field)

    sampler = circuit.compile_detector_sampler(seed=seed)
    digest = hashlib.sha256()
    shots = failures = osd_invocations = 0
    decode_seconds = 0.0

    def draw() -> tuple[np.ndarray, np.ndarray, str]:
        dets, obs = sampler.sample(batch_size, separate_observables=True, bit_packed=True)
        digest.update(dets.tobytes())
        digest.update(obs.tobytes())
        batch = hashlib.sha256(dets.tobytes())
        batch.update(obs.tobytes())
        return dets, obs, batch.hexdigest()

    for rec in completed:  # resume: the same stream, drawn and discarded
        _, _, batch_digest = draw()
        if batch_digest != rec.batch_samples_sha256 or digest.hexdigest() != rec.samples_sha256:
            raise SampleDigestMismatchError(
                f"batch {rec.batch_index} re-drawn from seed {seed} differs from its shard in "
                f"{checkpoint_dir}; the stim version or CPU class probably differs from the "
                "run that wrote it (D-027), so its shots cannot be continued"
            )
        shots, failures = rec.shots, rec.failures
        osd_invocations += rec.batch_osd_invocations
        decode_seconds += rec.batch_decode_seconds

    decoder = None
    last_batch_wall = None
    while failures < MIN_FAILURES and shots < max_shots:
        if (deadline is not None and last_batch_wall is not None
                and time.time() + last_batch_wall > deadline):
            return RunResult(seed=seed, batch_size=batch_size, shots=shots, failures=failures,
                             stopped_by="deadline", osd_invocations=osd_invocations,
                             samples_sha256=digest.hexdigest(), decode_seconds=decode_seconds)
        batch_start = time.perf_counter()
        if decoder is None:
            decoder = CompiledBpOsd(detector_error_model(circuit))
        dets, obs, batch_digest = draw()
        osd_before = decoder.osd_invocations
        start = time.perf_counter()
        pred = decoder.decode_shots_bit_packed(bit_packed_detection_event_data=dets)
        batch_seconds = time.perf_counter() - start
        batch_failures = count_failures(pred, obs, circuit.num_observables)
        batch_osd = decoder.osd_invocations - osd_before
        shots += batch_size
        failures += batch_failures
        osd_invocations += batch_osd
        decode_seconds += batch_seconds
        if checkpoint is not None:
            checkpoint.write_batch(BatchRecord(
                batch_index=shots // batch_size - 1,
                batch_shots=batch_size,
                batch_failures=batch_failures,
                batch_osd_invocations=batch_osd,
                batch_decode_seconds=batch_seconds,
                batch_samples_sha256=batch_digest,
                shots=shots,
                failures=failures,
                samples_sha256=digest.hexdigest(),
            ))
        last_batch_wall = time.perf_counter() - batch_start

    result = RunResult(
        seed=seed,
        batch_size=batch_size,
        shots=shots,
        failures=failures,
        stopped_by="min_failures" if failures >= MIN_FAILURES else "max_shots",
        osd_invocations=osd_invocations,
        samples_sha256=digest.hexdigest(),
        decode_seconds=decode_seconds,
    )
    if checkpoint is not None:
        checkpoint.write_result(dataclasses.asdict(result))
    return result
