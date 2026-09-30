"""Фикстуры для тестов Части 3."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def part3_catalog(project_root: Path) -> dict[str, dict]:
    """Справочник товаров для Части 3."""
    path = project_root / "catalog.json"
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["sku"]: item for item in items}


@pytest.fixture(scope="module")
def part3_history(project_root: Path) -> dict:
    """Данные Части 2 — для расчётов."""
    path = project_root / "src" / "part2" / "dataset_part2.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def part3_context(part3_catalog, part3_history) -> dict:
    """Полный контекст для answer_question."""
    return {"catalog": part3_catalog, "history": part3_history}


@pytest.fixture(scope="module")
def questions_15() -> list[str]:
    """15 вопросов из Приложения 1."""
    return [
        "Сколько масла закупить на три месяца и сколько это будет стоить?",
        "Что нужно заказать в ближайшие 14 дней?",
        "Какой бюджет закупок на квартал?",
        "Что закончится до следующей поставки в Сочи?",
        "Какие партии сгорят в этом месяце?",
        "Насколько подорожало ароматическое масло у поставщика?",
        "Сколько альгинатной маски осталось в Красной Поляне?",
        "Посчитай закупку скраба на полгода при лимите 200 тысяч",
        "Почему план закупок вырос по сравнению с прошлым кварталом?",
        "Сколько стоит закупить всё, что в риске дефицита?",
        "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
        "Заказать масло",
        "Сколько это будет стоить?",
        "Когда привезут заказ от поставщика?",
        "Какая погода в Сочи на выходных?",
    ]