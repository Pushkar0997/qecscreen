"""``qecscreen.splits`` (M0-SPLIT-01): one export, and no fallback to a row split (N-04).

The leakage assertion over every split (INV-2-T) is in ``test_inv_2_leakage.py``.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

from qecscreen import splits
from qecscreen.splits import grouped_kfold


def _frame(programs=6, per_program=5):
    return pd.DataFrame({
        "code_id": [f"bb_v1_t{g}-{i:012x}" for g in range(programs) for i in range(per_program)],
        "construction_program_id": [f"bb_v1_t{g}" for g in range(programs) for _ in range(per_program)],
    })


def test_grouped_kfold_is_the_only_export():
    assert splits.__all__ == ["grouped_kfold"]
    public_functions = [
        name for name, obj in vars(splits).items()
        if not name.startswith("_") and inspect.isfunction(obj) and obj.__module__ == splits.__name__
    ]
    assert public_functions == ["grouped_kfold"]


def test_n04_a_frame_without_the_program_column_raises():
    df = _frame().drop(columns="construction_program_id")
    with pytest.raises(KeyError, match="construction_program_id"):
        grouped_kfold(df, 3)


def test_a_null_program_raises():
    df = _frame()
    df.loc[3, "construction_program_id"] = None
    with pytest.raises(ValueError, match="null"):
        grouped_kfold(df, 3)


def test_fewer_programs_than_folds_raises():
    with pytest.raises(ValueError):
        grouped_kfold(_frame(programs=2), 3)


def test_folds_partition_the_rows_and_are_deterministic():
    df = _frame()
    folds = grouped_kfold(df, 3)
    assert len(folds) == 3
    tests = np.concatenate([test for _, test in folds])
    assert sorted(tests.tolist()) == list(range(len(df)))
    for train, test in folds:
        assert sorted(np.concatenate([train, test]).tolist()) == list(range(len(df)))
    again = grouped_kfold(df, 3)
    assert all(np.array_equal(a, c) and np.array_equal(b, d) for (a, b), (c, d) in zip(folds, again))
