"""Fake decoders for tests/test_calibrate.py.

A module of its own, not part of the test file, because calibration cells run
in spawned worker processes: the decoder factory is pickled by reference and
the worker imports it by module name (tests/ is on the parent's sys.path,
which spawn hands to the child).
"""

from __future__ import annotations

import time

from qecscreen.evaluate.calibrate import _make_decoder


class _HangsOnShot:
    """Delegates to a real decoder, but never returns from call ``hang_on``."""

    def __init__(self, inner, hang_on: int) -> None:
        self.inner = inner
        self.hang_on = hang_on
        self.calls = 0

    @property
    def converge(self):
        return self.inner.converge

    def decode(self, syndrome):
        if self.calls == self.hang_on:
            while True:  # a hang inside decode(): only a kill ends it
                time.sleep(3600)
        self.calls += 1
        return self.inner.decode(syndrome)


def hang_factory(name, dem, mats, *, hang_decoder: str, hang_on: int):
    """``decoder_factory`` whose ``hang_decoder`` hangs on its ``hang_on``-th shot (0-based).

    Each decoder decodes each shot exactly once, so the call index is the shot index.
    """
    real = _make_decoder(name, dem, mats)
    return _HangsOnShot(real, hang_on) if name == hang_decoder else real
