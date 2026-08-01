"""Path bootstrap so reasoning unit tests run before the package is installed.

Task 1 will add ``pyproject.toml`` and a top-level ``tests/conftest.py``; this
file becomes redundant then and should be deleted.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
