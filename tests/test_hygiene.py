"""Source-grep and import-hygiene tests.

These catch the reasonable-looking mistake at the moment it is written, rather
than three weeks later in a results table. See spec/evals.md section 3.
"""

import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "qecscreen"


def _python_sources():
    return sorted(SRC.rglob("*.py"))


# INV-4: only protocol.py may compute a logical error rate. These patterns cover
# the direct exponentiation and the rearrangements that are the same arithmetic
# written differently.
#
# The previous single pattern required a lowercase `p` in the base variable
# name, so it missed CONTRACT's own notation `(1 - P_L) **`, along with
# np.power, math.pow and the expm1/log1p form. Of six plausible spellings it
# caught one. It passed only because nothing had violated INV-4 yet.
LER_PATTERNS = (
    # (1 - anything) ** ... — any variable name, any case
    re.compile(r"\(\s*1(?:\.0*)?\s*-[^()]+\)\s*\*\*"),
    # ... ** (1 / ...) — the exponent shape, which also catches a base that
    # itself contains parentheses, e.g. (1 - f(x)) ** (1 / (r * k))
    re.compile(r"\)\s*\*\*\s*\(\s*1(?:\.0*)?\s*/"),
    # np.power(1 - x, ...), numpy.power(...), math.pow(...)
    re.compile(r"\b(?:np|numpy|math)\s*\.\s*pow(?:er)?\s*\(\s*1(?:\.0*)?\s*-", re.I),
    # the numerically-stable rearrangement: -expm1(log1p(-x) / n)
    re.compile(r"\bexpm1\s*\("),
    re.compile(r"\blog1p\s*\("),
)


def _ler_offenders(paths):
    """Paths whose source contains an LER-shaped computation."""
    return [
        str(f)
        for f in paths
        if any(p.search(f.read_text(encoding="utf-8")) for p in LER_PATTERNS)
    ]


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
    offenders = _ler_offenders(
        [f for f in _python_sources() if f.name != "protocol.py"]
    )
    assert not offenders, (
        f"an LER-shaped computation appears in {offenders}. Call "
        "qecscreen.protocol.logical_error_rate — see CONTRACT.md INV-4."
    )


# Every spelling below is the INV-4 formula. The guard must catch all of them.
KNOWN_LER_VIOLATIONS = (
    "x = 1 - (1 - P_L) ** (1.0 / (r * k))",  # CONTRACT's own notation
    "x = 1 - (1 - p_fail) ** (1.0 / (r * k))",
    "x = 1 - (1 - frac) ** (1.0 / (rounds * k))",  # no 'p' in the name at all
    "x = 1 - (1 - shot_fraction(z)) ** (1.0 / (r * k))",  # parens in the base
    "x = 1 - np.power(1 - P_L, 1.0 / (r * k))",
    "x = 1 - math.pow(1 - pl, 1.0 / (r * k))",
    "x = -np.expm1(np.log1p(-P_L) / (r * k))",
)


@pytest.mark.parametrize("snippet", KNOWN_LER_VIOLATIONS)
def test_inv4_grep_catches_known_violations(tmp_path, snippet):
    """The guard is itself tested. An untested guard is not a guard.

    Without this, the INV-4 check passes because nothing violates INV-4 yet —
    which says nothing about whether it would catch a violation when one is
    written.
    """
    offender = tmp_path / "offender.py"
    offender.write_text(snippet, encoding="utf-8")
    assert _ler_offenders([offender]) == [str(offender)]


def test_inv4_grep_does_not_flag_benign_source(tmp_path):
    """And it must not fire on ordinary arithmetic, or it will be disabled."""
    benign = tmp_path / "benign.py"
    benign.write_text(
        "ratio = failures / shots\n"
        "total = shots - failures\n"
        "weights = matrix.sum(axis=1)\n"
        "scaled = base ** exponent\n"
        "area = (width - 1) * (height - 1)\n",
        encoding="utf-8",
    )
    assert _ler_offenders([benign]) == []


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
