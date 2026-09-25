"""M0-EVAL-01, decoder half: BP+OSD as a sinter decoder, built from the DEM.

``BpOsdSinterDecoder`` is a ``sinter.Decoder``. For a detector error model it
compiles a ``CompiledBpOsd``: ldpc's ``BpOsdDecoder`` over the DEM's check
matrix and priors, configured with CONTRACT's ``DECODER_PARAMS`` and nothing
else, whose corrections are mapped to observable flips through the DEM's
observable matrix.

**Not here yet: the sampling loop and its stopping rule.** sinter seeds its
stim samplers from OS entropy and sizes its batches from wall-clock timing, so
a sinter-driven run cannot take the explicit ``seed`` CONTRACT's pinned
conventions require of every sampler. That is an owner decision; see
AGENT_LOG (mm).

The DEM is built undecomposed: BP+OSD decodes hyperedges directly, and
decomposition exists for matching decoders. Mechanisms with identical
(detectors, observables) symptoms are merged into one column, their
probabilities combined as independent flips. Mechanisms with the same
detectors but different observables stay separate columns.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import sinter
import stim
from ldpc import BpOsdDecoder

from qecscreen.protocol import DECODER_PARAMS

__all__ = [
    "DECODER_KEY",
    "DemMatrices",
    "detector_error_model",
    "dem_matrices",
    "BpOsdSinterDecoder",
    "CompiledBpOsd",
    "count_failures",
]

# The name this decoder is registered under in sinter's custom_decoders.
DECODER_KEY = "qecscreen_bposd"

# DECODER_PARAMS minus the two identity keys; everything else goes to ldpc as is.
_BPOSD_KWARGS = {k: v for k, v in DECODER_PARAMS.items() if k not in ("library", "decoder")}


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


class CompiledBpOsd(sinter.CompiledDecoder):
    """BP+OSD preconfigured for one DEM.

    Telemetry: ``shots_decoded`` and ``osd_invocations`` (shots on which BP did
    not converge, so OSD ran). Counted per instance, in whichever process
    decodes.
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
        # check this and segfaults, which in a sinter worker kills the process.
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


class BpOsdSinterDecoder(sinter.Decoder):
    """CONTRACT's decoder, in the form sinter's ``custom_decoders`` takes. Stateless."""

    def compile_decoder_for_dem(self, *, dem: stim.DetectorErrorModel) -> CompiledBpOsd:
        return CompiledBpOsd(dem)


def count_failures(predicted: np.ndarray, actual: np.ndarray, num_observables: int) -> int:
    """INV-4's failure event: shots where **any** observable prediction is wrong.

    Both arrays are bit packed little-endian, ``(shots, ceil(num_observables/8))``,
    the format sinter and stim use. Padding bits past ``num_observables`` are ignored.
    """
    wrong = np.unpackbits(
        np.bitwise_xor(predicted, actual), axis=1, count=num_observables, bitorder="little"
    )
    return int(np.count_nonzero(wrong.any(axis=1)))
