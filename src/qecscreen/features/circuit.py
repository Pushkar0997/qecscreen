"""Circuit features from the syndrome-extraction schedule (M0-FEAT-03, owner decision 2026-10-01).

Read off the ``bb_monomial_matching_xz_phased_v2`` schedule that builds the
code's memory circuit (``circuits.schedule.bb_schedule``), not re-derived from
``n`` and the check weight:

- ``cx_per_round``: CNOTs in one round, every pair in every X and Z layer.
- ``cx_total``: ``cx_per_round * d_upper``, over the ``r = d_upper`` rounds (D-006).
- ``circuit_ticks``: ``d_upper * (schedule.depth + 2)``, the ticks of the
  ``r`` noisy rounds. Per round, CONTRACT's tick layout has the CNOT layers
  plus an open tick and a swap tick: ``2(|A|+|B|) + 2``. The built stim
  circuit has one TICK more, after the noiseless initial data reset.

The colouring number in M0-FEAT-03's first wording is not a feature: in this
schedule each phase's layers are one perfect matching per monomial, so the
number of colours is ``|A|+|B|``, the check weight (``check_weight_max``),
and the per-round depth is twice it (``spec/tasks.md``).

BB-only, like the schedule.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from qecscreen.circuits.schedule import bb_schedule

__all__ = ["OPEN_AND_SWAP_TICKS", "circuit_features"]

OPEN_AND_SWAP_TICKS = 2  # per round: CONTRACT, tick layout per round (D-025)


def circuit_features(params: Mapping[str, Any], d_upper: int) -> dict[str, Any]:
    """``cx_per_round``, ``cx_total``, ``circuit_ticks`` for a BB code's ``params`` at ``r = d_upper``."""
    sched = bb_schedule(
        int(params["l"]), int(params["m"]),
        [tuple(e) for e in params["a_exps"]], [tuple(e) for e in params["b_exps"]],
    )
    cx_per_round = sum(len(layer) for layer in (*sched.x_layers, *sched.z_layers))
    return {
        "cx_per_round": int(cx_per_round),
        "cx_total": int(cx_per_round * d_upper),
        "circuit_ticks": int(d_upper * (sched.depth + OPEN_AND_SWAP_TICKS)),
    }
