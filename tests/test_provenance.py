"""provenance.resolved_commit() (D-017), stim_version / cpu_class (D-027), and
the no-credential guarantee for a private-repo install (D-028).

The distribution is faked the way pip lays one out: a ``qecscreen-*.dist-info``
directory with ``METADATA`` and ``direct_url.json``, prepended to ``sys.path``,
so ``importlib.metadata`` discovers it through its normal path. Nothing is
monkeypatched inside ``provenance`` except for the not-installed case.
"""

import json
import re
import sys
from importlib.metadata import PackageNotFoundError

import pytest

from qecscreen import provenance

SHA = "0123456789abcdef0123456789abcdef01234567"
SHA256_OBJECT = "ab" * 32
# Shaped like a real GitHub token so a leak would be recognisable, but not one.
TOKEN = "ghp_" + "FAKEcredentialDoNotLeak0123456789ab"
TOKEN_URL = f"https://{TOKEN}@github.com/Pushkar0997/qecscreen.git"


def _vcs(commit=SHA, url="https://github.com/Pushkar0997/qecscreen.git"):
    return {
        "url": url,
        "vcs_info": {"vcs": "git", "requested_revision": commit, "commit_id": commit},
    }


@pytest.fixture
def fake_dist(tmp_path, monkeypatch):
    """Install a fake ``qecscreen`` distribution; returns a writer for direct_url.json."""
    info = tmp_path / "qecscreen-0.0.1.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: qecscreen\nVersion: 0.0.1\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    def write(direct_url):
        path = info / "direct_url.json"
        if direct_url is None:
            path.unlink(missing_ok=True)
        elif isinstance(direct_url, str):
            path.write_text(direct_url, encoding="utf-8")
        else:
            path.write_text(json.dumps(direct_url), encoding="utf-8")

    return write


# --- resolved_commit(): the VCS branch -------------------------------------


def test_vcs_install_returns_the_commit_id(fake_dist):
    fake_dist(_vcs())
    assert provenance.resolved_commit() == SHA


def test_vcs_install_returns_the_resolved_commit_not_the_requested_ref(fake_dist):
    """D-017: what pip checked out, not what the notebook asked for."""
    fake_dist({
        "url": "https://github.com/Pushkar0997/qecscreen.git",
        "vcs_info": {"vcs": "git", "requested_revision": "main", "commit_id": SHA},
    })
    assert provenance.resolved_commit() == SHA


def test_sha256_object_ids_are_accepted(fake_dist):
    fake_dist(_vcs(commit=SHA256_OBJECT))
    assert provenance.resolved_commit() == SHA256_OBJECT


# --- resolved_commit(): the None branch -------------------------------------


def test_editable_install_returns_none(fake_dist):
    fake_dist({"url": "file:///home/me/qecscreen", "dir_info": {"editable": True}})
    assert provenance.resolved_commit() is None


def test_local_directory_install_returns_none(fake_dist):
    fake_dist({"url": "file:///home/me/qecscreen", "dir_info": {}})
    assert provenance.resolved_commit() is None


def test_archive_install_returns_none(fake_dist):
    fake_dist({"url": "https://example.org/qecscreen.tar.gz", "archive_info": {}})
    assert provenance.resolved_commit() is None


def test_index_install_without_direct_url_returns_none(fake_dist):
    fake_dist(None)
    assert provenance.resolved_commit() is None


def test_not_installed_returns_none(monkeypatch):
    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(provenance, "distribution", missing)
    assert provenance.resolved_commit() is None


# --- resolved_commit(): refusing what it cannot vouch for -------------------


@pytest.mark.parametrize(
    "direct_url",
    [
        "{not json",
        "[]",
        {"url": "x", "vcs_info": "git"},
        {"url": "x", "vcs_info": {"vcs": "git"}},
        _vcs(commit="0123456"),                 # abbreviated
        _vcs(commit=SHA.upper()),               # not how git or pip write it
        _vcs(commit=SHA + "\n"),
        _vcs(commit=None),
    ],
)
def test_malformed_direct_url_raises(fake_dist, direct_url):
    fake_dist(direct_url)
    with pytest.raises(ValueError):
        provenance.resolved_commit()


# --- D-028: no credential ever comes back out -------------------------------


def test_commit_from_a_token_bearing_install_url_carries_no_token(fake_dist):
    """PEP 610 says installers redact credentials; do not rely on it."""
    fake_dist(_vcs(url=TOKEN_URL))
    commit = provenance.resolved_commit()
    assert commit == SHA
    assert TOKEN not in commit


@pytest.mark.parametrize("bad", [TOKEN, TOKEN_URL, f"{SHA}@{TOKEN}"])
def test_a_credential_in_commit_id_raises_without_echoing_it(fake_dist, bad):
    fake_dist(_vcs(url=TOKEN_URL) | {"vcs_info": {"vcs": "git", "commit_id": bad}})
    with pytest.raises(ValueError) as exc:
        provenance.resolved_commit()
    assert TOKEN not in str(exc.value)


def test_every_provenance_value_is_free_of_the_credential(fake_dist, monkeypatch):
    """What a notebook writes into an artifact is ``record()``, whole."""
    fake_dist(_vcs(url=TOKEN_URL))
    # The secret is also in the environment, where a careless provenance field
    # (a dump of os.environ, a pip config) would pick it up.
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    monkeypatch.setenv("PIP_INDEX_URL", f"https://{TOKEN}@example.org/simple")

    values = provenance.record()
    assert values["commit_sha"] == SHA
    assert set(values) == {
        "commit_sha", "stim_version", "cpu_class", "decoder_version", "python_version",
    }
    serialised = json.dumps(values)
    assert TOKEN not in serialised
    assert "github.com" not in serialised
    assert all(v is None or re.fullmatch(r"[\w.+/-]+", v) for v in values.values()), values


# --- D-027: stim_version and cpu_class ---------------------------------------


def test_stim_version_is_the_installed_stim():
    import stim

    assert provenance.stim_version() == stim.__version__


def test_cpu_class_names_the_backend_stim_loaded():
    cls = provenance.cpu_class()
    machine, backend = cls.split("/")
    assert re.fullmatch(r"[a-z0-9_]+", machine)
    assert backend in {"avx2", "sse2", "polyfill"}
    loaded = [m for m in ("stim._stim_avx2", "stim._stim_sse2", "stim._stim_polyfill")
              if m in sys.modules]
    assert loaded == [f"stim._stim_{backend}"]


def test_cpu_class_normalises_machine_names(monkeypatch):
    monkeypatch.setattr(provenance.platform, "machine", lambda: "AMD64")
    assert provenance.cpu_class().startswith("x86_64/")


@pytest.mark.parametrize(
    "modules,expected",
    [
        ({"stim._stim_polyfill": 1}, "polyfill"),
        ({"stim._stim_sse2": 1, "stim": 1}, "sse2"),
        ({"stim._stim_avx2": 1}, "avx2"),
    ],
)
def test_stim_backend_detection(modules, expected):
    assert provenance._stim_backend(modules) == expected


@pytest.mark.parametrize(
    "modules", [{}, {"stim": 1}, {"stim._stim_sse2": 1, "stim._stim_polyfill": 1}]
)
def test_stim_backend_detection_refuses_ambiguity(modules):
    with pytest.raises(RuntimeError):
        provenance._stim_backend(modules)
