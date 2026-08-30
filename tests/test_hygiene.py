"""Source-grep and import-hygiene tests.

These catch the reasonable-looking mistake at the moment it is written, rather
than three weeks later in a results table. See spec/evals.md section 3.
"""

import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "qecscreen"


def _python_sources():
    return sorted(SRC.rglob("*.py"))


def test_inv8_no_float_matrix_rank():
    """numpy.linalg.matrix_rank works over the reals and is wrong here."""
    offenders = [
        str(f)
        for f in _python_sources()
        if re.search(r"linalg\.matrix_rank", f.read_text())
        and f.name != "linalg.py"  # linalg.py references it only inside a docstring
    ]
    assert not offenders, (
        f"numpy.linalg.matrix_rank found in {offenders}. Use qecscreen.linalg.gf2_rank "
        "— see CONTRACT.md INV-8."
    )


def test_inv2_no_random_train_test_split():
    """Random splits let the model memorise construction templates (INV-2)."""
    offenders = [
        str(f) for f in _python_sources() if "train_test_split" in f.read_text()
    ]
    assert not offenders, (
        f"train_test_split found in {offenders}. Use qecscreen.splits.grouped_kfold "
        "— see CONTRACT.md INV-2."
    )


def test_inv4_ler_formula_lives_only_in_protocol():
    """Only protocol.py may compute a logical error rate (INV-4)."""
    pattern = re.compile(r"\(\s*1(?:\.0)?\s*-\s*[\w.]*p[\w_]*\s*\)\s*\*\*")
    offenders = [
        str(f)
        for f in _python_sources()
        if f.name != "protocol.py" and pattern.search(f.read_text())
    ]
    assert not offenders, (
        f"an LER-shaped computation appears in {offenders}. Call "
        "qecscreen.protocol.logical_error_rate — see CONTRACT.md INV-4."
    )


def test_no_torch_outside_models_gnn():
    """torch is an optional M3 dependency; the data pipeline must not need it."""
    offenders = [
        str(f)
        for f in _python_sources()
        if re.search(r"^\s*import torch|^\s*from torch", f.read_text(), re.M)
        and "models/gnn" not in f.as_posix()
    ]
    assert not offenders, f"torch imported outside models/gnn in {offenders}"


def test_inv9_no_network_at_import():
    """Importing the package must make no network call."""
    import socket
    import importlib

    original = socket.socket

    class Blocked(original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **kw):
            raise AssertionError("qecscreen must not open a socket at import time")

    socket.socket = Blocked  # type: ignore[assignment]
    try:
        import qecscreen

        importlib.reload(qecscreen)
    finally:
        socket.socket = original  # type: ignore[assignment]
