"""qecscreen — circuit-level screening for quantum LDPC code search.

Importing this package performs no network access and no filesystem writes
(CONTRACT.md INV-9). Heavy optional dependencies (torch) are never imported
here.
"""

__version__ = "0.0.1"

from . import linalg, protocol  # noqa: F401

__all__ = ["linalg", "protocol", "__version__"]
