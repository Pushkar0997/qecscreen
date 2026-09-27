"""Notebook rules (spec/architecture.md §2, D-028, D-030).

Logic never lives in a notebook: notebooks are not tested, cannot be reviewed
in a diff, and run only on Kaggle or Colab, where nobody reads them closely. The
enforceable form of that rule is structural. No code cell defines a function, a
class or a lambda, so anything that needs one has to go into ``src/qecscreen``,
where it is tested.

``notebooks/runs/`` holds executed notebooks kept as dated evidence. They are
frozen records, so the no-definition rule does not apply to them: editing one
would falsify it. The credential scan applies to every notebook, runs included.
"""

import ast
import json
import pathlib
import re
import subprocess
import sys
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
EVIDENCE = NOTEBOOKS / "runs"
TEMPLATE = NOTEBOOKS / "template_run.ipynb"

ALL = sorted(p for p in NOTEBOOKS.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts)
RULED = [p for p in ALL if EVIDENCE not in p.parents]

FORBIDDEN = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)

# IPython line magics and shell escapes, including `x = !cmd`, are not Python.
# They are blanked to `pass` (keeping indentation) so the rest of the cell can
# be parsed. A cell magic (`%%bash`, ...) makes the cell some other language
# and is refused, since nothing in it could be checked.
_MAGIC = re.compile(r"^(\s*)(?:[A-Za-z_]\w*\s*=\s*)?[!%]")

# GitHub token shapes: classic (ghp_, gho_, ghu_, ghs_, ghr_) and fine-grained.
_TOKEN = re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}")


def _rel(path):
    return path.relative_to(ROOT).as_posix()


def _cells(path):
    return json.loads(path.read_text(encoding="utf-8"))["cells"]


def _source(cell):
    src = cell["source"]
    return "".join(src) if isinstance(src, list) else src


def definitions(source):
    """``(line, kind)`` of every function, class or lambda defined in ``source``.

    Raises ``SyntaxError`` if the cell is not Python once magics are blanked.
    """
    if source.lstrip().startswith("%%"):
        raise SyntaxError("cell magic: the cell is not Python and cannot be checked")
    lines = [
        (m.group(1) + "pass") if (m := _MAGIC.match(line)) else line
        for line in source.splitlines()
    ]
    tree = ast.parse("\n".join(lines))
    return [(n.lineno, type(n).__name__) for n in ast.walk(tree) if isinstance(n, FORBIDDEN)]


def test_there_are_notebooks_to_check():
    assert TEMPLATE in RULED
    assert len(RULED) >= 2


@pytest.mark.parametrize("path", RULED, ids=_rel)
def test_no_code_cell_defines_a_function_or_class(path):
    offences = []
    for i, cell in enumerate(_cells(path)):
        if cell["cell_type"] != "code":
            continue
        try:
            found = definitions(_source(cell))
        except SyntaxError as exc:
            offences.append(f"cell {i}: not parseable as Python ({exc.msg})")
            continue
        offences += [f"cell {i}, line {line}: {kind}" for line, kind in found]
    assert not offences, (
        f"{_rel(path)} defines logic in a notebook: {offences}. Move it into "
        "src/qecscreen and call it (spec/architecture.md §2)."
    )


@pytest.mark.parametrize("path", ALL, ids=_rel)
def test_no_notebook_contains_a_github_token(path):
    """Source and outputs both: an output is kept in Kaggle's version history too."""
    text = path.read_text(encoding="utf-8")
    assert not _TOKEN.search(text), f"{_rel(path)} contains a GitHub token (D-028)"


def test_template_has_exactly_six_code_cells_and_no_outputs():
    cells = _cells(TEMPLATE)
    assert [c["cell_type"] for c in cells] == ["code"] * 6
    assert all(c["outputs"] == [] and c["execution_count"] is None for c in cells)


def test_template_install_cell_pins_a_sha_and_reads_the_token_from_secrets():
    install, provenance = (_source(c) for c in _cells(TEMPLATE)[:2])
    assert 'get_secret("GITHUB_TOKEN")' in install        # Kaggle
    assert 'userdata.get("GITHUB_TOKEN")' in install      # Colab
    assert "[0-9a-f]{40}" in install                      # a full SHA, never a ref
    assert '.replace(token, "***")' in install            # pip's output is masked
    assert "assert token" not in install                  # the secret is optional (D-030)
    assert "record()" in provenance
    assert 'PROVENANCE["commit_sha"] == QECSCREEN_SHA' in provenance


# --- executing the install cell (D-030) ---------------------------------------
#
# Cell 1 runs here against fake Kaggle/Colab secret stores, with pip replaced by
# a recorder, so no network and no install. The token is a fake that pip's fake
# output echoes back, to check the masking.

_SHA = "0123456789abcdef0123456789abcdef01234567"
_FAKE_TOKEN = "fake-secret-value-for-tests"
_PUBLIC_URL = f"git+https://github.com/Pushkar0997/qecscreen@{_SHA}"
_TOKEN_URL = f"git+https://{_FAKE_TOKEN}@github.com/Pushkar0997/qecscreen@{_SHA}"
_INSTALLING = ["template_run.ipynb", "calibrate.ipynb"]


class _SecretNotFound(Exception):
    pass


def _getter(secret):
    """Both platforms raise, rather than return None, for a secret not attached."""

    def get(name):
        if secret is None or name != "GITHUB_TOKEN":
            raise _SecretNotFound(name)
        return secret

    return get


def _kaggle(secret):
    get = _getter(secret)

    class UserSecretsClient:
        def get_secret(self, name):
            return get(name)

    return types.SimpleNamespace(UserSecretsClient=UserSecretsClient)


def _colab(secret):
    return types.SimpleNamespace(userdata=types.SimpleNamespace(get=_getter(secret)))


def _run_install_cell(notebook, monkeypatch, kaggle=None, colab=None):
    """Execute cell 1 of ``notebook``; return the pip argv it ran.

    ``kaggle``/``colab`` are fake modules, or None for "not on this platform".
    """
    source = _source(_cells(NOTEBOOKS / notebook)[0])
    assert 'QECSCREEN_SHA = ""' in source
    source = source.replace('QECSCREEN_SHA = ""', f'QECSCREEN_SHA = "{_SHA}"')
    monkeypatch.setitem(sys.modules, "kaggle_secrets", kaggle)
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return types.SimpleNamespace(returncode=0, stdout=f"Collecting {argv[-1]}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    exec(compile(source, notebook, "exec"), {"__name__": "__main__"})
    assert len(calls) == 1
    assert calls[0][:4] == [sys.executable, "-m", "pip", "install"]
    return calls[0]


@pytest.mark.parametrize("notebook", _INSTALLING)
@pytest.mark.parametrize(
    "platform",
    [
        pytest.param({}, id="neither"),
        pytest.param({"kaggle": _kaggle(None)}, id="kaggle-no-secret"),
        pytest.param({"colab": _colab(None)}, id="colab-no-secret"),
    ],
)
def test_install_cell_without_a_secret_uses_the_public_url(notebook, platform, monkeypatch, capsys):
    argv = _run_install_cell(notebook, monkeypatch, **platform)
    assert argv[-1] == _PUBLIC_URL
    assert "from the public URL, no token" in capsys.readouterr().out


@pytest.mark.parametrize("notebook", _INSTALLING)
@pytest.mark.parametrize(
    "platform",
    [
        pytest.param({"kaggle": _kaggle(_FAKE_TOKEN)}, id="kaggle"),
        pytest.param({"colab": _colab(_FAKE_TOKEN)}, id="colab"),
    ],
)
def test_install_cell_with_a_secret_uses_it_and_masks_it(notebook, platform, monkeypatch, capsys):
    argv = _run_install_cell(notebook, monkeypatch, **platform)
    assert argv[-1] == _TOKEN_URL
    out = capsys.readouterr().out
    assert _FAKE_TOKEN not in out                          # pip echoed it; the cell masked it
    assert "git+https://***@github.com" in out


# --- the checker itself ------------------------------------------------------


@pytest.mark.parametrize(
    "source,kinds",
    [
        ("def f():\n    pass", ["FunctionDef"]),
        ("async def f():\n    pass", ["AsyncFunctionDef"]),
        ("class C:\n    pass", ["ClassDef"]),
        ("key = lambda row: row[0]", ["Lambda"]),
        ("if True:\n    def f():\n        pass", ["FunctionDef"]),
        ("!pip install x\nimport os", []),
        ("files = !ls\n%time x = 1\nif True:\n    !echo hi", []),
        ("x = [i * i for i in range(3)]", []),
    ],
)
def test_definitions_finds_exactly_the_definitions(source, kinds):
    assert [k for _, k in definitions(source)] == kinds


def test_definitions_refuses_cell_magics_and_invalid_python():
    with pytest.raises(SyntaxError):
        definitions("%%bash\necho hi")
    with pytest.raises(SyntaxError):
        definitions("def (:")


def test_token_pattern_matches_both_token_shapes():
    assert _TOKEN.search("ghp_" + "a1" * 18)
    assert _TOKEN.search("github_pat_" + "A_1" * 10)
    assert not _TOKEN.search("the GITHUB_TOKEN secret")
