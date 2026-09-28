"""Worker hooks for tests/test_pilot.py.

A module of its own because pilot workers are spawned processes: the hook
(``PilotConfig._worker_setup``) is pickled by reference and the worker imports
it by module name (tests/ is on the parent's sys.path, which spawn hands to
the child). Each hook runs first in the worker, before anything is sampled.
"""

from __future__ import annotations

import os
import time

import qecscreen.evaluate.run as run_mod
import qecscreen.provenance as prov


def fake_provenance(job, *, commit: str, cpu: str, stim: str = "1.16.0") -> None:
    """The worker reports this commit, CPU class and stim version (an editable
    install has no commit to read)."""
    prov.resolved_commit = lambda: commit
    prov.cpu_class = lambda: cpu
    prov.stim_version = lambda: stim


def past_deadline(job, **provenance) -> None:
    """Sleep until the session deadline has passed: the worker then runs exactly
    one batch (the first always runs) and stops at the next between-batch check."""
    fake_provenance(job, **provenance)
    time.sleep(max(0.0, job["deadline"] - time.time()) + 0.05)


def slow_batches(job, *, seconds: float, **provenance) -> None:
    """Every decoded batch takes at least ``seconds``, so a test can kill the
    worker between two of its batches."""
    fake_provenance(job, **provenance)
    real = run_mod.CompiledBpOsd.decode_shots_bit_packed

    def slow(self, *, bit_packed_detection_event_data):
        time.sleep(seconds)
        return real(self, bit_packed_detection_event_data=bit_packed_detection_event_data)

    run_mod.CompiledBpOsd.decode_shots_bit_packed = slow


def die_on(job, *, code_id: str, exitcode: int, **provenance) -> None:
    """The worker for ``code_id`` exits at once with ``exitcode``, like a kernel OOM kill."""
    fake_provenance(job, **provenance)
    if job["code"]["code_id"] == code_id:
        os._exit(exitcode)
