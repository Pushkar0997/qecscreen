"""A code's stored identity: ``params_json``, ``code_id``, ``family``, and ``regenerate`` (INV-7).

``params_json`` is the canonical JSON of a BB code's parameters: keys ``l``,
``m``, ``a_exps``, ``b_exps``, sorted, no whitespace, exponents as lists of
ints. ``code_id`` is CONTRACT's ``{program_id}-{sha256(params_json)[:12]}``.
This is the canonicalisation the decoder calibration pinned (D-029), so a
code in both the calibration and the dataset has one ``code_id``, and so one
``sampling_seed`` at a given protocol (D-027).

``regenerate(row)`` rebuilds ``H_X`` and ``H_Z`` from what a row stores:
``construction_program_id``, ``params_json`` and ``seed``. It checks the
row's ``code_id`` against the formula first, so a row whose parameters were
edited after its id was derived is refused, not silently regenerated as a
different code.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from qecscreen.codes.bb import generate

__all__ = ["params_json", "code_id", "family", "regenerate"]

# construction_program_id prefix -> family (spec/architecture.md §3). Only BB
# exists at M0; M1 adds the others.
_FAMILIES = {"bb_v1": "BB"}


def params_json(l: int, m: int, a_exps: Sequence[Sequence[int]], b_exps: Sequence[Sequence[int]]) -> str:
    """Canonical JSON of a BB code's parameters (sorted keys, no whitespace)."""
    params = {
        "a_exps": [list(map(int, e)) for e in a_exps],
        "b_exps": [list(map(int, e)) for e in b_exps],
        "l": int(l),
        "m": int(m),
    }
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def code_id(construction_program_id: str, params: str) -> str:
    """``{program_id}-{sha256(params_json)[:12]}`` (CONTRACT, IDs)."""
    digest = hashlib.sha256(params.encode("utf-8")).hexdigest()[:12]
    return f"{construction_program_id}-{digest}"


def family(construction_program_id: str) -> str:
    """``BB`` for ``bb_v1_<template>``; ``KeyError`` for a program of no known family (N-09)."""
    for prefix, name in _FAMILIES.items():
        if construction_program_id == prefix or construction_program_id.startswith(prefix + "_"):
            return name
    raise KeyError(
        f"no family for construction_program_id {construction_program_id!r}; "
        f"known prefixes: {sorted(_FAMILIES)}"
    )


def regenerate(row: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """``(H_X, H_Z)`` from a row's ``construction_program_id``, ``params_json`` and ``seed`` (INV-7)."""
    program = row["construction_program_id"]
    stored = row["params_json"]
    if code_id(program, stored) != row["code_id"]:
        raise ValueError(
            f"code_id {row['code_id']!r} does not match its construction_program_id and "
            "params_json under CONTRACT's formula; refusing to regenerate"
        )
    if family(program) != "BB":  # pragma: no cover - only BB exists at M0
        raise KeyError(f"no generator for family {family(program)!r}")
    params = json.loads(stored)
    if params_json(**params) != stored:
        raise ValueError("params_json is not in canonical form")
    return generate(
        params["l"], params["m"],
        [tuple(e) for e in params["a_exps"]], [tuple(e) for e in params["b_exps"]],
        seed=int(row["seed"]),
    )
