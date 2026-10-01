"""The feature table (M0-FEAT-01..05): computed from the code alone (D-009, INV-1, INV-5).

The full 244-code table is not computed here; ``compute_features`` is run on
three codes. Their ``n``/``k``/``d_upper`` are the values the M0 population
enumeration (``admissible_codes(72)``) gives them.
"""

import math
import time
from collections.abc import Mapping

import numpy as np
import pandas as pd
import pytest

from qecscreen.codes import ids
from qecscreen.features.table import (
    FEATURE_COLUMNS,
    FEATURE_SCHEMA,
    IDENTITY_KEYS,
    code_features,
    compute_features,
)

REFERENCE = ("bb_v1_sym_3_3", 6, 6, [(3, 0), (0, 1), (0, 2)], [(0, 3), (1, 0), (2, 0)])  # [[72,12,6]]
SMALL = ("bb_v1_pair_2_2", 2, 3, [(1, 0), (0, 2)], [(0, 1), (2, 0)])  # [[12,2,<=3]]
LARGE_TRI = ("bb_v1_tri_3_3", 12, 3, [(1, 0), (0, 1), (1, 1)], [(0, 0), (2, 1), (1, 2)])  # [[72,4,<=6]]

# The measurement columns a feature must never read (architecture §3).
MEASUREMENT_ONLY = {
    "shots": 40960, "failures": 3, "true_ler": 0.25, "true_ler_ub": 0.5,
    "true_ler_ci_low": 0.1, "true_ler_ci_high": 0.9, "censored": True,
    "decode_seconds": 1.0, "protocol_hash": "a" * 64, "p": 0.002, "rounds": 6,
}


def _record(program, l, m, a_exps, b_exps, seed=0):
    pj = ids.params_json(l, m, a_exps, b_exps)
    return {"code_id": ids.code_id(program, pj), "construction_program_id": program,
            "params_json": pj, "seed": seed}


class _SpyRecord(Mapping):
    """A record that remembers every key read from it."""

    def __init__(self, data):
        self._data = dict(data)
        self.read = []

    def __getitem__(self, key):
        self.read.append(key)
        return self._data[key]

    def __iter__(self):
        self.read.append("<iter>")
        return iter(self._data)

    def __len__(self):
        return len(self._data)


def test_reference_code_features():
    row = code_features(_record(*REFERENCE))
    assert (row["n"], row["k"], row["d_upper"]) == (72, 12, 6)
    assert math.isclose(row["phi_from_d_upper"], 12 * 6**2 / 72, rel_tol=1e-12)
    assert (row["check_weight_min"], row["check_weight_max"], row["check_weight_mean"]) == (6, 6, 6.0)
    assert (row["n_ancilla"], row["n_total"]) == (72, 144)


def test_compute_features_on_three_codes():
    records = [_record(*c) for c in (REFERENCE, SMALL, LARGE_TRI)]
    table = compute_features(records)
    assert tuple(table.columns) == FEATURE_COLUMNS
    assert table["code_id"].tolist() == [r["code_id"] for r in records]
    assert table[["n", "k", "d_upper"]].values.tolist() == [[72, 12, 6], [12, 2, 3], [72, 4, 6]]
    assert table["check_weight_max"].tolist() == [6, 4, 6]
    ints = ("n", "k", "d_upper", "n_ancilla", "n_total", "check_weight_min", "check_weight_max",
            *(f"qubit_degree_{s}_{t}" for s in ("min", "max") for t in ("x", "z")))
    for name in ints:
        assert table[name].dtype == np.int32, name
    for name in ("phi_from_d_upper", "check_weight_mean", "qubit_degree_mean_x", "qubit_degree_mean_z"):
        assert table[name].dtype == np.float64, name
    assert FEATURE_SCHEMA.field("code_id").type == "string"


def test_compute_features_refuses_a_repeated_code():
    with pytest.raises(ValueError, match="twice"):
        compute_features([_record(*SMALL), _record(*SMALL)])


def test_inv1_feature_columns_are_neither_true_nor_pred():
    table = compute_features([_record(*SMALL)])
    assert not [c for c in table.columns if c.startswith(("true_", "pred_"))]
    assert tuple(table.columns) == FEATURE_COLUMNS


def test_inv5_distance_and_phi_are_named_for_the_upper_bound():
    table = compute_features([_record(*REFERENCE), _record(*SMALL)])
    assert "d_upper" in table.columns and "phi_from_d_upper" in table.columns
    assert "d_exact" not in table.columns
    bare = {"d", "distance", "phi", "Phi"}
    assert not bare & set(table.columns)
    assert [c for c in table.columns if "phi" in c.lower()] == ["phi_from_d_upper"]
    expected = table["k"] * table["d_upper"].astype(np.int64) ** 2 / table["n"]
    assert np.allclose(table["phi_from_d_upper"], expected, rtol=1e-12, atol=0)


def test_features_never_read_a_measurement_column():
    """No feature reads a row's ``true_*``, ``shots`` or ``failures``: only ``IDENTITY_KEYS`` are read."""
    spy = _SpyRecord({**_record(*REFERENCE), **MEASUREMENT_ONLY})
    code_features(spy)
    assert set(spy.read) <= set(IDENTITY_KEYS), spy.read
    assert not [k for k in spy.read if k.startswith("true_") or k in ("shots", "failures")]


def test_features_do_not_change_with_the_measurement_columns():
    base = pd.DataFrame([_record(*c) for c in (REFERENCE, SMALL, LARGE_TRI)])
    measured = base.assign(**{k: [v] * len(base) for k, v in MEASUREMENT_ONLY.items()})
    other = base.assign(shots=[256, 512, 768], failures=[100, 0, 7], true_ler=[None, 1e-3, 0.5],
                        true_ler_ub=[1.0, 0.0, 0.2], true_ler_ci_low=[0.0] * 3, true_ler_ci_high=[1.0] * 3)
    expected = compute_features(base)
    pd.testing.assert_frame_equal(compute_features(measured), expected)
    pd.testing.assert_frame_equal(compute_features(other), expected)


def test_a_record_without_its_seed_is_refused():
    record = _record(*SMALL)
    del record["seed"]
    with pytest.raises(KeyError):
        code_features(record)


@pytest.mark.parametrize("code", [REFERENCE, SMALL], ids=["72_12_6", "12_2_3"])
def test_feat05_every_feature_under_one_second_per_code(code):
    """M0-FEAT-05, N-07: all of a code's features, regeneration and ``d_upper`` included, in under 1 s.

    Times ``code_features`` whole, so each feature added to it falls under the
    bound. [[72,12,6]] is the largest M0 code (n <= 72, D-031).
    """
    record = _record(*code)
    start = time.perf_counter()
    code_features(record)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"{record['code_id']}: features took {elapsed:.3f} s, over the 1 s bound"


# A CSS code whose two Tanner graphs differ: H_X = [1111], H_Z = [1100] (n=4, k=2).
# Every qubit is in the X check, only qubits 0 and 1 in the Z check.
ASYM_HX = np.array([[1, 1, 1, 1]], dtype=np.uint8)
ASYM_HZ = np.array([[1, 1, 0, 0]], dtype=np.uint8)


def test_feat01_qubit_degree_is_per_check_type():
    from qecscreen.features.structural import structural_features

    row = structural_features(ASYM_HX, ASYM_HZ, d_upper=2)
    assert (row["qubit_degree_min_x"], row["qubit_degree_max_x"], row["qubit_degree_mean_x"]) == (1, 1, 1.0)
    assert (row["qubit_degree_min_z"], row["qubit_degree_max_z"], row["qubit_degree_mean_z"]) == (0, 1, 0.5)


def test_feat01_qubit_degree_on_bb_codes():
    """In a BB code a qubit of block A is in |A| checks of one type and |B| of the other."""
    table = compute_features([_record(*REFERENCE), _record(*LARGE_TRI)])
    for t in ("x", "z"):
        assert table[f"qubit_degree_min_{t}"].tolist() == [3, 3]
        assert table[f"qubit_degree_max_{t}"].tolist() == [3, 3]
        assert table[f"qubit_degree_mean_{t}"].tolist() == [3.0, 3.0]
    quad = _record("bb_v1_quad_4_2", 3, 3, [(1, 0), (0, 1), (2, 0), (0, 2)], [(1, 1), (2, 2)])
    row = code_features(quad)
    for t in ("x", "z"):
        assert (row[f"qubit_degree_min_{t}"], row[f"qubit_degree_max_{t}"], row[f"qubit_degree_mean_{t}"]) == (2, 4, 3.0)
