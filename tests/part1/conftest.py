"""Фикстуры для тестов Части 1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def records_m1_m8(project_root: Path) -> list[dict]:
    """M1–M8 из dataset_part1.json."""
    path = project_root / "src" / "part1" / "dataset_part1.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)