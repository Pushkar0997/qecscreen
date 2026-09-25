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
from importlib.metadata import PackageNotFoundError, version

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
    "MEMORY_BASIS",
    "ROUNDS_RULE",
    "installed_decoder_version",
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

# D-025: X-check phase then Z-check phase, one CX tick per monomial of A / B.
SCHEDULING = "bb_monomial_matching_xz_phased_v1"

# D-025: the label is a Z-basis memory LER. The basis changes every label, so
# it enters the hash.
MEMORY_BASIS = "Z"

# D-006 chooses the number of rounds per code. INV-6 hashes this *rule*, never
# the concrete r that it produces — see D-014 for why the obvious alternative
# (dropping rounds from the hash) is wrong.
ROUNDS_RULE = "r = d_upper"


def installed_decoder_version() -> str:
    """Version of the installed decoder library, for INV-6.

    Read at call time, not at import time, so a hash always describes the
    library that actually did the decoding rather than whatever happened to be
    present when the module was first imported.
    """
    library = DECODER_PARAMS["library"]
    try:
        return version(library)
    except PackageNotFoundError as exc:  # pragma: no cover - environment error
        raise RuntimeError(
            f"{library} is not installed, so no protocol hash can honestly record "
            "a decoder version (CONTRACT.md INV-6)."
        ) from exc


@dataclass(frozen=True)
class Protocol:
    """The frozen tuple that makes two measurements comparable (INV-6).

    Note what is deliberately *absent*: the concrete number of rounds. ``r``
    varies per code under D-006, so hashing it made ``protocol_hash`` a per-code
    identifier and ``assert_single_protocol`` fired on every legitimate
    cross-code ranking. ``rounds_rule`` records how ``r`` is chosen; the value
    for a given code is a per-row stored column. See D-014.
    """

    p: float
    decoder_version: str
    noise_model: str = NOISE_MODEL
    scheduling: str = SCHEDULING
    rounds_rule: str = ROUNDS_RULE
    memory_basis: str = MEMORY_BASIS
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.decoder_version or self.decoder_version == "unset":
            raise ValueError(
                "decoder_version must be the version actually installed; got "
                f"{self.decoder_version!r}. A hash that silently omits the thing it "
                "claims to carry is worse than no hash (CONTRACT.md INV-6). Use "
                "installed_decoder_version()."
            )

    def hash(self) -> str:
        payload = asdict(self)
        # CONTRACT convention: p is stored to 6 decimal places.  Round before
        # hashing so that insignificant trailing digits in a raw float do not
        # produce a spurious protocol mismatch.
        payload["p"] = round(payload["p"], 6)
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
