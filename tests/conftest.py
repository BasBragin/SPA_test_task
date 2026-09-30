"""Общие фикстуры для всех тестов."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Загружаем .env — чтобы GIGACHAT_CREDENTIALS был доступен
# в тестах Части 3 (LLM-тесты).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Корень проекта (где catalog.json)."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def catalog(project_root: Path) -> dict[str, dict]:
    """Справочник товаров — общий для всех частей."""
    with open(project_root / "catalog.json", encoding="utf-8") as f:
        items = json.load(f)
    return {item["sku"]: item for item in items}