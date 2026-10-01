"""The feature table: one row per code, keyed on ``code_id`` (D-009, architecture §3).

Features live in their own Parquet, apart from measurements and predictions,
so INV-1 holds by construction. They are computed **from the code alone**: a
record's ``code_id``, ``construction_program_id``, ``params_json`` and
``seed`` (``IDENTITY_KEYS``) go through ``codes.ids.regenerate`` (INV-7),
and ``d_upper`` is ``estimate_d_upper`` at the same seed, the call that
admitted the code and built its measurement row (D-031). No other key of a
record is read, so a measurement column (``true_*``, ``shots``, ``failures``)
cannot reach a feature, whatever the input carries.

``compute_features(population)`` takes an iterable of records or a DataFrame
(from which only ``IDENTITY_KEYS`` are selected). ``write_features(frame,
data_dir)`` writes it to ``<data_dir>/m0_features.parquet`` (owner,
2026-10-01). Every row carries ``feature_set`` = ``FEATURE_SET``, the version
of this column set: a change to any feature's definition is a new
``FEATURE_SET``, so two feature files are never silently mixed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from qecscreen.codes import ids
from qecscreen.codes.distance import estimate_d_upper
from qecscreen.features.circuit import circuit_features
from qecscreen.features.structural import GRAPH_FEATURES, structural_features

__all__ = [
    "FEATURE_COLUMNS", "FEATURE_SCHEMA", "FEATURE_SET", "FEATURES_FILE", "IDENTITY_KEYS",
    "code_features", "compute_features", "write_features",
]

IDENTITY_KEYS = ("code_id", "construction_program_id", "params_json", "seed")
FEATURE_SET = "m0_features_v1"
FEATURES_FILE = "m0_features.parquet"  # owner, 2026-10-01, under data/ (architecture §2)


def _per_type(fields: list[tuple[str, pa.DataType]]) -> list[tuple[str, pa.DataType]]:
    """Each graph feature as ``_x`` then ``_z`` (``structural.GRAPH_FEATURES`` order)."""
    assert tuple(name for name, _ in fields) == GRAPH_FEATURES
    return [(f"{name}_{t}", dtype) for name, dtype in fields for t in ("x", "z")]


FEATURE_SCHEMA = pa.schema([
    ("code_id", pa.string()),
    ("feature_set", pa.string()),
    ("n", pa.int32()),
    ("k", pa.int32()),
    ("d_upper", pa.int32()),
    ("phi_from_d_upper", pa.float64()),
    ("check_weight_min", pa.int32()),
    ("check_weight_max", pa.int32()),
    ("check_weight_mean", pa.float64()),
    ("n_ancilla", pa.int32()),
    ("n_total", pa.int32()),
    *_per_type([
        ("qubit_degree_min", pa.int32()),
        ("qubit_degree_max", pa.int32()),
        ("qubit_degree_mean", pa.float64()),
        ("cycle4_count", pa.int64()),
        ("cycle6_count", pa.int64()),
        ("girth", pa.int32()),  # null for a graph with no cycle
        ("lambda2", pa.float64()),  # 0 for a disconnected graph
        ("n_components", pa.int32()),
    ]),
    ("cx_per_round", pa.int32()),
    ("cx_total", pa.int32()),
    ("circuit_ticks", pa.int32()),
])
FEATURE_COLUMNS = tuple(FEATURE_SCHEMA.names)


def code_features(record: Mapping[str, Any]) -> dict[str, Any]:
    """One feature row for the code ``record`` identifies. Reads only ``IDENTITY_KEYS``."""
    identity = {key: record[key] for key in IDENTITY_KEYS}
    h_x, h_z = ids.regenerate(identity)
    d_upper, _ = estimate_d_upper(h_x, h_z, seed=int(identity["seed"]))
    row = {
        "code_id": identity["code_id"],
        "feature_set": FEATURE_SET,
        **structural_features(h_x, h_z, d_upper),
        **circuit_features(json.loads(identity["params_json"]), d_upper),  # regenerate checked it
    }
    assert tuple(row) == FEATURE_COLUMNS
    return row


def compute_features(population: Iterable[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    """The feature table for ``population``, columns ``FEATURE_COLUMNS``, one row per code."""
    if isinstance(population, pd.DataFrame):
        population = population.loc[:, list(IDENTITY_KEYS)].to_dict("records")
    rows = [code_features(record) for record in population]
    table = pa.Table.from_pylist(rows, schema=FEATURE_SCHEMA)
    frame = table.to_pandas()
    if frame["code_id"].duplicated().any():
        raise ValueError("a code_id appears twice; the feature table has one row per code")
    return frame


def write_features(frame: pd.DataFrame, data_dir: str | os.PathLike[str]) -> Path:
    """Write ``compute_features``'s ``frame`` to ``<data_dir>/m0_features.parquet``; return its path.

    ``data_dir`` must be a directory named ``data`` (architecture §2), and the
    file must not exist yet: as with the measurements, nothing overwrites it.
    The frame must have exactly ``FEATURE_COLUMNS``, one row per ``code_id``,
    and ``feature_set`` equal to ``FEATURE_SET`` on every row.
    """
    data = Path(data_dir)
    if data.name != "data":
        raise ValueError(f"features go under data/ (architecture §2), not {data}")
    target = data / FEATURES_FILE
    if target.exists():
        raise FileExistsError(f"{target} exists; write_features does not overwrite it")
    if tuple(frame.columns) != FEATURE_COLUMNS:
        raise ValueError(f"columns {tuple(frame.columns)} are not FEATURE_COLUMNS {FEATURE_COLUMNS}")
    if frame.empty:
        raise ValueError("no rows: an empty feature table is not written")
    if frame["code_id"].duplicated().any():
        raise ValueError("a code_id appears twice; the feature table has one row per code")
    if set(frame["feature_set"]) != {FEATURE_SET}:
        raise ValueError(f"feature_set {sorted(set(frame['feature_set']))} is not [{FEATURE_SET!r}]")
    table = pa.Table.from_pandas(frame, schema=FEATURE_SCHEMA, preserve_index=False)
    tmp = target.with_name(target.name + ".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, target)
    return target
