"""Shared test setup.

lightgbm is imported before any test module can import pandas or pyarrow: on
Windows, pyarrow 18's bundled msvcp140.dll otherwise makes lightgbm's first
fit die with an access violation (see ``qecscreen/models/baseline.py``).
"""

import lightgbm  # noqa: F401
