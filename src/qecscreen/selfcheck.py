"""Fast sanity check, referenced by spec/smoke.md.

Run with:  python -m qecscreen.selfcheck
Exits non-zero on failure.
"""

from __future__ import annotations

import sys

from qecscreen import __version__
from qecscreen.protocol import (
    Protocol,
    installed_decoder_version,
    logical_error_rate,
    wilson_interval,
)


def main() -> int:
    checks: list[tuple[str, bool]] = []

    checks.append(
        ("LER golden G-01", abs(logical_error_rate(0.5, 12, 12) - 0.004801955655646228) < 1e-15)
    )
    low, high = wilson_interval(100, 10_000)
    checks.append(("Wilson golden G-05", abs(low - 0.008229336148148417) < 1e-15))
    checks.append(("Wilson bounds ordered", low < high))
    proto = Protocol(p=0.005, decoder_version=installed_decoder_version())
    checks.append(("protocol hash stable", proto.hash() == Protocol(
        p=0.005, decoder_version=installed_decoder_version()).hash()))

    print(f"qecscreen {__version__}")
    failed = 0
    for name, ok in checks:
        print(f"  [{'ok' if ok else 'FAIL'}] {name}")
        failed += not ok

    if failed:
        print(f"\n{failed} check(s) failed.")
        return 1
    print("\nAll self-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
