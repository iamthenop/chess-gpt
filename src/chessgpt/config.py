"""
Project configuration defaults.

This module is a lightweight home for shared defaults used by scripts
and library code. It is intentionally small until real duplication appears.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_DB_PATH = Path("data/db/chessgpt.sqlite3")
