"""Run-time provenance: which code, which stim, which CPU class produced a row.

``resolved_commit()`` is D-017: the ``commit_sha`` column is read back from the
package that is actually installed and importable, never copied from a
notebook's pinned install SHA, which records intent rather than fact.

``stim_version()`` and ``cpu_class()`` are D-027: per-row provenance columns,
deliberately not ``protocol_hash`` inputs. Seeded shots are bit-identical only
on a matching stim version and CPU class; the distribution is the same on all.

Nothing here returns a URL or reads an environment variable. The install URL
of a private repository can carry a token (D-028), so the only value taken from
``direct_url.json`` is the commit id, and it is checked to be a bare hex digest
before it is returned.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from importlib.metadata import PackageNotFoundError, distribution, version

__all__ = ["resolved_commit", "stim_version", "cpu_class", "record"]

DISTRIBUTION = "qecscreen"

# git object ids: SHA-1 (40 hex) or SHA-256 (64 hex). Lowercase, as git and pip
# write them.
_COMMIT_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

# The compiled extensions stim chooses between at import, by CPU features
# (stim/__init__.py). Which one loaded is what decides the sampled bits.
_STIM_BACKENDS = {
    "stim._stim_avx2": "avx2",
    "stim._stim_sse2": "sse2",
    "stim._stim_polyfill": "polyfill",
}

_MACHINE_ALIASES = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}


def resolved_commit() -> str | None:
    """The exact VCS commit of the installed ``qecscreen``, or ``None``.

    Read from the ``direct_url.json`` (PEP 610) that pip writes into the
    installed distribution's metadata:

    - a VCS install (``pip install git+...@<sha>``) returns ``vcs_info.commit_id``,
      the commit pip actually checked out, whatever ref was requested;
    - an editable or local-directory install (``dir_info``), an archive
      install, an index install (no ``direct_url.json``), or no installed
      distribution at all (running from ``src/`` on ``sys.path``) returns
      ``None``: there is no commit to read, and guessing one is what D-017
      forbids.

    ``None`` is not a valid ``commit_sha``. Whatever writes a row must refuse
    it; this function only reports.

    Raises ``ValueError`` if ``direct_url.json`` is present but malformed, or its
    commit id is not a bare hex object id. That check is also what keeps a URL
    or a credential from ever being returned in its place.
    """
    try:
        dist = distribution(DISTRIBUTION)
    except PackageNotFoundError:
        return None

    text = dist.read_text("direct_url.json")
    if text is None:
        return None
    try:
        info = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{DISTRIBUTION}'s direct_url.json is not valid JSON") from exc
    if not isinstance(info, dict):
        raise ValueError(f"{DISTRIBUTION}'s direct_url.json is not a JSON object")

    vcs_info = info.get("vcs_info")
    if vcs_info is None:
        return None
    commit = vcs_info.get("commit_id") if isinstance(vcs_info, dict) else None
    if not isinstance(commit, str) or not _COMMIT_RE.fullmatch(commit):
        # Deliberately does not echo the value: it came from a file that also
        # holds the install URL, and that URL may carry a token.
        raise ValueError(
            f"{DISTRIBUTION}'s direct_url.json has a vcs_info.commit_id that is not a "
            "40- or 64-character lowercase hex object id (D-017)"
        )
    return commit


def stim_version() -> str:
    """The installed stim's version, for the ``stim_version`` column (D-027)."""
    return version("stim")


def _stim_backend(modules) -> str:
    """Which of stim's compiled backends is loaded in ``modules``."""
    loaded = [name for module, name in _STIM_BACKENDS.items() if module in modules]
    if len(loaded) != 1:
        raise RuntimeError(
            f"expected exactly one stim backend among {sorted(_STIM_BACKENDS)} to be "
            f"loaded, found {loaded}. stim may have changed how it selects its "
            "backend; cpu_class must be redefined before any row is written (D-027)."
        )
    return loaded[0]


def cpu_class() -> str:
    """``<machine>/<stim SIMD backend>``, e.g. ``x86_64/sse2`` (D-027).

    The backend is the compiled extension stim chose at import from the CPU's
    features. Two machines with the same class and stim version draw the same
    bits from the same seed; a raw CPU flag list would split machines that do.
    """
    import stim  # noqa: F401  (imported for its side effect: loading a backend)

    machine = platform.machine().lower()
    return f"{_MACHINE_ALIASES.get(machine, machine)}/{_stim_backend(sys.modules)}"


def record() -> dict[str, str | None]:
    """Every provenance value a run writes into an artifact.

    Keys: ``commit_sha``, ``stim_version``, ``cpu_class``, ``decoder_version``
    (the value that enters ``protocol_hash``) and ``python_version``. No URL,
    no path, no environment variable: nothing here can carry a credential.
    """
    from qecscreen.protocol import installed_decoder_version

    return {
        "commit_sha": resolved_commit(),
        "stim_version": stim_version(),
        "cpu_class": cpu_class(),
        "decoder_version": installed_decoder_version(),
        "python_version": platform.python_version(),
    }
