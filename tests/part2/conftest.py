"""Фикстуры для тестов Части 2."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def part2_history(project_root: Path) -> dict:
    """Данные Части 2 из dataset_part2.json."""
    path = project_root / "src" / "part2" / "dataset_part2.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def part2_catalog(project_root: Path) -> dict[str, dict]:
    """Каталог товаров для Части 2."""
    path = project_root / "catalog.json"
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["sku"]: item for item in items}