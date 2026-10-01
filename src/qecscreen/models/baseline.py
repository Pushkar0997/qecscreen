"""M0-RUN-04: the LightGBM baseline, out-of-fold over construction programs (INV-2, INV-3).

The model predicts ``log10(true_ler)`` from the feature table
(``features.table.FEATURE_COLUMNS`` less ``code_id`` and ``feature_set``; Φ,
``phi_from_d_upper``, is one of the features). Hyperparameters are pinned in
``LGBM_PARAMS`` (owner, 2026-10-01) and never tuned.

**Folds.** Leave one program out: ``splits.grouped_kfold`` with ``n_splits``
equal to the number of construction programs, so each fold's test set is one
program and its training set every other program (INV-2). Each code is
predicted once, by the model of the fold that held its program out, and the
out-of-fold predictions are pooled over all codes.

**Censored rows** (INV-3) are never a regression target: each fold fits on
its non-censored training rows only. Every row, censored or not, is still
predicted, so every code can be ranked.

Predictions are ``pred_*`` and live in their own file,
``data/m0_predictions.parquet`` (D-009): ``code_id``, ``pred_log10_ler``,
``fold``, ``model_version``. ``write_predictions`` does not overwrite it.
"""

from __future__ import annotations

# lightgbm before pandas and pyarrow, deliberately. On Windows, pyarrow 18's
# wheel bundles an older msvcp140.dll; once pyarrow has loaded it,
# lib_lightgbm.dll binds to it and the first fit dies with an access violation
# (seen with lightgbm 4.7.0, pyarrow 18.1.0). Linux (CI, Kaggle) is unaffected.
from lightgbm import LGBMRegressor  # isort: skip

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from qecscreen.features.table import FEATURE_COLUMNS
from qecscreen.splits import grouped_kfold

__all__ = [
    "LGBM_PARAMS",
    "MODEL_FEATURES",
    "MODEL_VERSION",
    "PREDICTION_COLUMNS",
    "PREDICTION_SCHEMA",
    "PREDICTIONS_FILE",
    "TARGET",
    "make_model",
    "out_of_fold_predictions",
    "write_predictions",
]

# owner, 2026-10-01: pinned, no tuning.
LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 10,
    "subsample": 1.0,
    "colsample_bytree": 1.0,
    "random_state": 0,
    "deterministic": True,
    "n_jobs": 1,
    "verbose": -1,
}
MODEL_VERSION = "m0_lightgbm_v1"  # a change to LGBM_PARAMS, the features or the target is a new version
MODEL_FEATURES = tuple(c for c in FEATURE_COLUMNS if c not in ("code_id", "feature_set"))
TARGET = "log10(true_ler)"
PREDICTIONS_FILE = "m0_predictions.parquet"  # D-009's third file, under data/ (architecture §2)

PREDICTION_SCHEMA = pa.schema([
    pa.field("code_id", pa.string(), nullable=False),
    pa.field("pred_log10_ler", pa.float64(), nullable=False),
    pa.field("fold", pa.int32(), nullable=False),
    pa.field("model_version", pa.string(), nullable=False),
])
PREDICTION_COLUMNS = tuple(PREDICTION_SCHEMA.names)


def make_model() -> LGBMRegressor:
    """A fresh regressor at ``LGBM_PARAMS``."""
    return LGBMRegressor(**LGBM_PARAMS)


def _matrix(frame: pd.DataFrame) -> np.ndarray:
    """The feature matrix, float64; a null feature (e.g. ``girth`` of an acyclic graph) is NaN."""
    return frame.loc[:, list(MODEL_FEATURES)].astype("float64").to_numpy()


def out_of_fold_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    """Leave-one-program-out predictions for every row of ``frame``, in ``frame``'s row order.

    ``frame`` holds one row per code with ``code_id``, ``construction_program_id``,
    ``censored``, ``true_ler`` and every column of ``MODEL_FEATURES``. Returns
    ``PREDICTION_COLUMNS``; ``fold`` is the index of the fold whose test set
    held the row. Raises if a fold has no non-censored training row, or a
    non-censored row has no positive finite ``true_ler``.
    """
    censored = frame["censored"].to_numpy(dtype=bool)
    ler = frame["true_ler"].astype("float64").to_numpy()
    if not (np.isfinite(ler[~censored]) & (ler[~censored] > 0)).all():
        raise ValueError("a non-censored row has no positive finite true_ler to take log10 of")
    target = np.full(len(frame), np.nan)
    target[~censored] = np.log10(ler[~censored])
    x = _matrix(frame)
    n_programs = frame["construction_program_id"].nunique()
    pred = np.full(len(frame), np.nan)
    fold = np.full(len(frame), -1, dtype=np.int32)
    for i, (train, test) in enumerate(grouped_kfold(frame, n_splits=n_programs)):
        fit_rows = train[~censored[train]]  # INV-3: censored rows are never a target
        if len(fit_rows) == 0:
            raise ValueError(f"fold {i} has no non-censored training row")
        model = make_model().fit(x[fit_rows], target[fit_rows])
        pred[test] = model.predict(x[test])
        fold[test] = i
    assert (fold >= 0).all() and np.isfinite(pred).all()
    return pd.DataFrame({
        "code_id": frame["code_id"].to_numpy(),
        "pred_log10_ler": pred,
        "fold": fold,
        "model_version": MODEL_VERSION,
    })


def write_predictions(predictions: pd.DataFrame, data_dir: str | os.PathLike[str]) -> Path:
    """Write ``predictions`` to ``<data_dir>/m0_predictions.parquet``; return its path.

    ``data_dir`` must be a directory named ``data`` (architecture §2), and the
    file must not exist yet. The frame must have exactly
    ``PREDICTION_COLUMNS``, one row per ``code_id``.
    """
    data = Path(data_dir)
    if data.name != "data":
        raise ValueError(f"predictions go under data/ (architecture §2), not {data}")
    target = data / PREDICTIONS_FILE
    if target.exists():
        raise FileExistsError(f"{target} exists; write_predictions does not overwrite it")
    if tuple(predictions.columns) != PREDICTION_COLUMNS:
        raise ValueError(f"columns {tuple(predictions.columns)} are not PREDICTION_COLUMNS {PREDICTION_COLUMNS}")
    if predictions.empty or predictions["code_id"].duplicated().any():
        raise ValueError("predictions need one row per code_id, and at least one")
    table = pa.Table.from_pandas(predictions, schema=PREDICTION_SCHEMA, preserve_index=False)
    data.mkdir(exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    pq.write_table(table, tmp)
    os.replace(tmp, target)
    return target
