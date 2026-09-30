"""Grouped splits (INV-2). The only sanctioned way to split code rows.

Two codes from one construction program (one polynomial template at different
``(l, m)``, D-022) are near-duplicates, so they always land on the same side
of a split. ``grouped_kfold`` groups on ``construction_program_id`` and on
nothing else. A frame without that column is refused, never split by row
(N-04). sklearn's random row splitter is banned in ``src/`` (``test_hygiene.py``).

This module exports ``grouped_kfold`` and no other split function.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold as _GroupKFold

__all__ = ["grouped_kfold"]

_GROUP_COLUMN = "construction_program_id"


def grouped_kfold(df: pd.DataFrame, n_splits: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """``n_splits`` folds of ``df``, each a ``(train, test)`` pair of positional indices.

    Every row of one ``construction_program_id`` is in the same fold, so no
    program is on both sides of any split. Deterministic: the same frame
    gives the same folds. Use ``df.iloc[train]`` / ``df.iloc[test]``.

    Raises ``KeyError`` if ``df`` has no ``construction_program_id`` column,
    and ``ValueError`` if any row's program is null, or if there are fewer
    programs than ``n_splits`` (sklearn's check).
    """
    if _GROUP_COLUMN not in df.columns:
        raise KeyError(
            f"grouped_kfold needs a {_GROUP_COLUMN!r} column to group on (INV-2); "
            f"the frame has {list(df.columns)}. Splitting by row is never a fallback"
        )
    groups = df[_GROUP_COLUMN]
    if groups.isna().any():
        raise ValueError(f"{int(groups.isna().sum())} row(s) have a null {_GROUP_COLUMN}; every row needs its program")
    folds = _GroupKFold(n_splits=n_splits).split(np.zeros(len(df)), groups=groups.to_numpy())
    return [(np.asarray(train), np.asarray(test)) for train, test in folds]
