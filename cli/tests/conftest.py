"""Test fixtures and sample data."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def load_html_fixture(name: str) -> str:
    """Load an HTML fixture file."""
    path = FIXTURES_DIR / name
    return path.read_text(encoding="utf-8")
