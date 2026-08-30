"""Frozen evaluation protocol.

This module is the single source of truth for the constants and formulas in
CONTRACT.md. Nothing else in the codebase may compute a logical error rate
(INV-4) or a confidence interval.

Changing anything here invalidates every label ever generated. Requires
explicit human approval.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict

__all__ = [
    "SCHEMA_VERSION",
    "MIN_FAILURES",
    "MAX_SHOTS",
    "SHOT_BATCH",
    "CONFIDENCE",
    "Z_95",
    "NOISE_MODEL",
    "DECODER_PARAMS",
    "SCHEDULING",
    "Protocol",
    "protocol_hash",
    "logical_error_rate",
    "wilson_interval",
    "is_censored",
    "assert_single_protocol",
]

# --- Frozen constants (CONTRACT.md, "Exact values") -------------------------

SCHEMA_VERSION = 1

MIN_FAILURES = 100  # below this a row is censored (INV-3)
MAX_SHOTS = 200_000  # hard cap per (code, p)
SHOT_BATCH = 10_000  # sample/decode in batches, check the stopping rule between

CONFIDENCE = 0.95
Z_95 = 1.959963984540054

NOISE_MODEL = "uniform_depolarizing_v1"

DECODER_PARAMS = {
    "library": "ldpc",
    "decoder": "BpOsdDecoder",
    "bp_method": "minimum_sum",
    "max_iter": 30,
    "ms_scaling_factor": 0.625,
    "osd_method": "osd_cs",
    "osd_order": 10,
}

SCHEDULING = "tanner_edge_colouring_v1"


@dataclass(frozen=True)
class Protocol:
    """The frozen tuple that makes two measurements comparable (INV-6)."""

    p: float
    rounds: int
    noise_model: str = NOISE_MODEL
    scheduling: str = SCHEDULING
    decoder_version: str = "unset"  # filled from the installed ldpc version
    schema_version: int = SCHEMA_VERSION

    def hash(self) -> str:
        payload = asdict(self)
        payload["decoder_params"] = DECODER_PARAMS
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def protocol_hash(protocol: Protocol) -> str:
    """The value of the ``protocol_hash`` column for ``protocol`` (INV-6).

    Exists so that the function name matches the column name in the stored
    schema and the task that names it (M0-EVAL-03). A thin wrapper over
    ``Protocol.hash()`` — there is still exactly one implementation, because two
    would eventually disagree.
    """
    return protocol.hash()


# --- The one LER formula (INV-4) --------------------------------------------


def logical_error_rate(p_fail: float, rounds: int, k: int) -> float:
    """Logical error rate per round, per logical qubit.

    ``p_fail`` is the fraction of shots in which *any* logical observable was
    incorrect, over ``rounds`` noisy syndrome-extraction rounds, for a code
    encoding ``k`` logical qubits.

        p_LER = 1 - (1 - p_fail) ** (1 / (rounds * k))

    This is the only place in the codebase where an LER is computed. See
    CONTRACT.md INV-4 for why mixing normalisations silently destroys the
    result this project exists to produce.

    ``p_fail == 1.0`` raises rather than returning 1.0 (negative test N-05):
    a code that fails every single shot has an undefined per-round rate, and
    silently returning 1.0 hides a malformed circuit.
    """
    if not 0.0 <= p_fail < 1.0:
        raise ValueError(
            f"p_fail must be in [0, 1); got {p_fail!r}. "
            "A value of exactly 1.0 means every shot failed, which indicates a "
            "malformed circuit rather than a measurable error rate."
        )
    if rounds < 1:
        raise ValueError(f"rounds must be >= 1; got {rounds!r}")
    if k < 1:
        raise ValueError(f"k must be >= 1; got {k!r}")

    if p_fail == 0.0:
        return 0.0
    return 1.0 - (1.0 - p_fail) ** (1.0 / (rounds * k))


def wilson_interval(
    failures: int, shots: int, z: float = Z_95
) -> tuple[float, float]:
    """Two-sided Wilson score interval for a binomial proportion.

    Used instead of the normal approximation because the interesting regime has
    very few failures, where the normal approximation is badly wrong and can
    produce negative lower bounds.
    """
    if shots <= 0:
        raise ValueError(f"shots must be > 0; got {shots!r}")
    if not 0 <= failures <= shots:
        raise ValueError(f"failures must be in [0, shots]; got {failures!r}/{shots!r}")

    p = failures / shots
    denom = 1.0 + z * z / shots
    centre = (p + z * z / (2.0 * shots)) / denom
    half = (
        z * math.sqrt(p * (1.0 - p) / shots + z * z / (4.0 * shots * shots))
    ) / denom
    return centre - half, centre + half


def is_censored(failures: int) -> bool:
    """INV-3: too few observed failures to be a point estimate."""
    return failures < MIN_FAILURES


def assert_single_protocol(protocol_hashes) -> str:
    """INV-6: refuse to compare rows measured under different protocols.

    Accepts any iterable of hashes (e.g. ``df["protocol_hash"]``). Returns the
    single hash if there is exactly one, raises otherwise. Every function that
    ranks, correlates, plots or trains across rows must call this.
    """
    distinct = set(protocol_hashes)
    if len(distinct) == 0:
        raise ValueError("no rows: cannot establish a protocol")
    if len(distinct) > 1:
        raise ValueError(
            f"refusing to combine {len(distinct)} distinct protocols: "
            f"{sorted(distinct)}. LERs measured under different noise models or "
            "decoders are not comparable (CONTRACT.md INV-6)."
        )
    return distinct.pop()
