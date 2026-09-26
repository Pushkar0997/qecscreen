"""M0-EVAL-02: turn raw counts into a label, censoring per INV-3.

A label is the measurement half of a dataset row: counts, the INV-4 rate and
its Wilson interval. Every rate here comes from ``qecscreen.protocol``; this
module only decides which of them a row carries.

INV-3: fewer than ``MIN_FAILURES`` observed failures is not a point estimate.
Such a row is ``censored``, ``true_ler`` is null, and ``true_ler_ub`` (the
Wilson upper bound, in per-round per-qubit units) is what it contributes.

The Wilson interval is taken on the per-shot failure fraction ``P_L`` and
mapped through ``logical_error_rate``, which is monotone increasing in
``P_L``, so the mapped bounds are an interval for ``true_ler`` at the same
confidence. Both bounds are stored on every row, censored or not.
"""

from __future__ import annotations

from dataclasses import dataclass

from qecscreen.protocol import (
    MAX_SHOTS,
    is_censored,
    logical_error_rate,
    wilson_interval,
)

__all__ = ["Label", "make_label"]


@dataclass(frozen=True)
class Label:
    """Measurement columns of one ``(code, protocol)`` row (spec/architecture.md §3)."""

    p: float
    rounds: int
    k: int
    shots: int
    failures: int
    censored: bool
    true_ler: float | None
    true_ler_ub: float
    true_ler_ci_low: float
    true_ler_ci_high: float
    decode_seconds: float


def make_label(
    *, p: float, rounds: int, k: int, shots: int, failures: int, decode_seconds: float
) -> Label:
    """Label for ``failures`` in ``shots`` of an ``r = rounds``, ``k``-qubit memory run.

    Raises ``ValueError`` on counts that cannot come from a valid run, and
    (via ``logical_error_rate``, N-05) when every shot failed.
    """
    if not 0 < shots <= MAX_SHOTS:
        raise ValueError(f"shots must be in (0, MAX_SHOTS={MAX_SHOTS}]; got {shots!r}")
    if not 0 <= failures <= shots:
        raise ValueError(f"failures must be in [0, shots]; got {failures!r}/{shots!r}")
    if decode_seconds < 0:
        raise ValueError(f"decode_seconds must be >= 0; got {decode_seconds!r}")

    lo, hi = wilson_interval(failures, shots)  # clamped to [0, 1] in protocol (D-026)
    ci_low = logical_error_rate(lo, rounds, k)
    ci_high = logical_error_rate(hi, rounds, k)

    censored = is_censored(failures)
    true_ler = None if censored else logical_error_rate(failures / shots, rounds, k)

    return Label(
        p=round(p, 6),
        rounds=rounds,
        k=k,
        shots=shots,
        failures=failures,
        censored=censored,
        true_ler=true_ler,
        true_ler_ub=ci_high,
        true_ler_ci_low=ci_low,
        true_ler_ci_high=ci_high,
        decode_seconds=float(decode_seconds),
    )
