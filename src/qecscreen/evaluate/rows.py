"""Guards for whatever writes dataset rows (M0-EVAL-04, M0-RUN-01).

The row writer itself does not exist yet. What does exist is output that must
never become a row: the decoder calibration (``qecscreen.evaluate.calibrate``)
measures under settings that are not the pinned protocol, at values of ``p``
and shot counts chosen for calibration, so a calibration number in the
dataset would be a label from a different protocol under the pinned
protocol's hash (INV-6).

Every calibration file and record carries ``"calibration": true``.
``reject_calibration`` refuses anything that does, and the row writer calls
it on every input before writing anything.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

__all__ = ["CALIBRATION_MARKER", "CalibrationOutputError", "reject_calibration"]

# The key every calibration file and record sets to true.
CALIBRATION_MARKER = "calibration"


class CalibrationOutputError(ValueError):
    """Calibration output was offered where a dataset row was expected."""


def _refuse(what: str) -> None:
    raise CalibrationOutputError(
        f"{what} is decoder-calibration output ('{CALIBRATION_MARKER}': true), not a "
        "dataset row; calibration is never written to the dataset"
    )


def _check_json_file(path: Path) -> None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return  # not JSON: not calibration output, which is always JSON
    if isinstance(obj, Mapping) and obj.get(CALIBRATION_MARKER):
        _refuse(str(path))


def reject_calibration(source: Any) -> None:
    """Raise ``CalibrationOutputError`` if ``source`` is or contains calibration output.

    ``source`` may be a mapping (one record), a pandas-like frame (anything
    with ``columns``; the marker column's presence is enough), a path to a
    file or a directory (every ``*.json`` under it is checked), or an
    iterable of any of these. Returns ``None`` otherwise.
    """
    if isinstance(source, Mapping):
        if source.get(CALIBRATION_MARKER):
            _refuse("a record")
        return
    if hasattr(source, "columns"):
        if CALIBRATION_MARKER in list(source.columns):
            _refuse("a frame")
        return
    if isinstance(source, (str, os.PathLike)):
        path = Path(source)
        if path.is_dir():
            for f in sorted(path.rglob("*.json")):
                _check_json_file(f)
        elif path.is_file() and path.suffix == ".json":
            _check_json_file(path)
        return
    if isinstance(source, Iterable) and not isinstance(source, (bytes, bytearray)):
        for item in source:
            reject_calibration(item)
