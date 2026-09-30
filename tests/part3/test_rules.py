"""Тесты для fallback-разбора (rules.py) — без LLM.

Покрывают:
- detect_intents / pick_intent;
- extract_sku (явный код + синонимы);
- extract_location;
- extract_period_days (числа + словами);
- extract_budget_limit;
- extract_scenario_multiplier (what-if);
- parse_question (полный разбор).
"""

from __future__ import annotations

import pytest

from src.part3.rules import (
    detect_intents,
    extract_budget_limit,
    extract_location,
    extract_period_days,
    extract_scenario_multiplier,
    extract_sku,
    parse_question,
    pick_intent,
)

# ─── detect_intents / pick_intent ────────────────────────────────────

class TestDetectIntents:

    def test_forecast_purchase(self):
        scores = detect_intents("Сколько масла закупить на квартал?")
        assert "forecast_purchase" in scores

    def test_stock_check(self):
        scores = detect_intents("Сколько масла осталось на складе?")
        assert "stock_check" in scores

    def test_deficit_risk(self):
        scores = detect_intents("Что закончится в ближайшие дни?")
        assert "deficit_risk" in scores

    def test_explain(self):
        scores = detect_intents("Почему план закупок вырос?")
        assert "explain" in scores

    def test_empty(self):
        scores = detect_intents("")
        assert scores == {}

    def test_pick_intent_top(self):
        scores = {"forecast_purchase": 2, "budget": 1}
        intent, conf = pick_intent(scores)
        assert intent == "forecast_purchase"
        assert 0.5 < conf <= 1.0

    def test_pick_intent_empty(self):
        intent, conf = pick_intent({})
        assert intent == "unknown"
        assert conf == 0.0


# ─── extract_sku ─────────────────────────────────────────────────────

class TestExtractSku:

    @pytest.mark.parametrize("text,expected", [
        ("OIL-001", "OIL-001"),
        ("oil 001", "OIL-001"),
        ("OIL 001", "OIL-001"),
        ("масло", "OIL-001"),
        ("масла", "OIL-001"),
        ("ароматическое масло", "OIL-002"),
        ("лаванда", "OIL-002"),
        ("скраба", "SCRB-020"),
        ("маски", "WRAP-030"),
        ("тапочки", "CONS-051"),
        ("шапочки", "CONS-052"),
    ])
    def test_sku_variants(self, text, expected):
        assert extract_sku(text) == expected

    def test_unknown_sku(self):
        assert extract_sku("что-то непонятное") is None

    def test_empty(self):
        assert extract_sku("") is None


# ─── extract_location ────────────────────────────────────────────────

class TestExtractLocation:

    @pytest.mark.parametrize("text,expected", [
        ("в Сочи", "Сочи"),
        ("Красная Поляна", "Красная Поляна"),
        ("на поляне", "Красная Поляна"),
        ("MS-01", "MS-01"),
        ("ms 02", "MS-02"),
    ])
    def test_locations(self, text, expected):
        assert extract_location(text) == expected

    def test_no_location(self):
        assert extract_location("сколько масла") is None


# ─── extract_period_days ────────────────────────────────────────────

class TestExtractPeriod:

    @pytest.mark.parametrize("text,expected", [
        ("на 30 дней", 30),
        ("на 14 дней", 14),
        ("на неделю", 7),
        ("на месяц", 30),
        ("на квартал", 90),
        ("на полгода", 180),
        ("на год", 365),
        ("на 2 недели", 14),
        ("на 3 месяца", 90),
        ("в ближайшие 14 дней", 14),
        ("за месяц", 30),
        ("за квартал", 90),
    ])
    def test_periods(self, text, expected):
        result = extract_period_days(text)
        assert result == expected, f"'{text}': {result} != {expected}"

    def test_numbers_as_words(self):
        assert extract_period_days("на три месяца") == 90
        assert extract_period_days("на две недели") == 14
        assert extract_period_days("на пять дней") == 5

    def test_no_period(self):
        assert extract_period_days("сколько масла") is None


# ─── extract_budget_limit ───────────────────────────────────────────

class TestExtractBudget:

    @pytest.mark.parametrize("text,expected", [
        ("лимит 200 тысяч", 200000.0),
        ("лимит 200 тыс", 200000.0),
        ("лимит 200000", 200000.0),
        ("лимит 200 000 руб", 200000.0),
    ])
    def test_budgets(self, text, expected):
        assert extract_budget_limit(text) == expected

    def test_no_budget(self):
        assert extract_budget_limit("сколько масла") is None


# ─── extract_scenario_multiplier ────────────────────────────────────

class TestExtractScenarioMultiplier:

    @pytest.mark.parametrize("text,expected", [
        # Рост
        ("если загрузка вырастет на 20%", 1.2),
        ("если спрос вырастет на 50%", 1.5),
        ("увеличится на 10%", 1.1),
        ("+20%", 1.2),
        ("рост 25%", 1.25),

        # Падение
        ("если спрос упадёт на 10%", 0.9),
        ("снизится на 20%", 0.8),
        ("уменьшится на 25%", 0.75),
        ("−10%", 0.9),
        ("-15%", 0.85),

        # Нет сценария
        ("сколько масла закупить", None),
        ("обычный вопрос без процентов", None),
        ("", None),
    ])
    def test_scenario_multiplier(self, text, expected):
        result = extract_scenario_multiplier(text)
        if expected is None:
            assert result is None, f"'{text}': {result} != None"
        else:
            assert result == pytest.approx(expected, abs=0.001), (
                f"'{text}': {result} != {expected}"
            )

    def test_too_large_growth_ignored(self):
        """Рост > 500% — вероятно, ошибка парсинга."""
        assert extract_scenario_multiplier("вырастет на 1000%") is None

    def test_too_large_fall_ignored(self):
        """Падение > 100% — не имеет смысла."""
        assert extract_scenario_multiplier("упадёт на 150%") is None


# ─── parse_question — полный разбор ─────────────────────────────────

class TestParseQuestion:

    def test_full_question(self):
        result = parse_question("Сколько масла закупить на квартал?")
        assert result["intent"] == "forecast_purchase"
        assert result["sku"] == "OIL-001"
        assert result["period_days"] == 90

    def test_deficit_risk(self):
        result = parse_question("Что закончится в Сочи?")
        assert result["intent"] == "deficit_risk"
        assert result["location"] == "Сочи"

    def test_stock_check(self):
        result = parse_question("Сколько масла осталось?")
        assert result["intent"] == "stock_check"
        assert result["sku"] == "OIL-001"

    def test_unknown(self):
        result = parse_question("Какая погода в Сочи?")
        assert result["intent"] == "unknown"

    def test_returns_all_keys(self):
        result = parse_question("Сколько масла закупить?")
        expected = {
            "intent", "intent_confidence", "sku", "location",
            "period_days", "budget_limit", "scenario_multiplier",
        }
        assert set(result.keys()) == expected

    def test_parse_includes_scenario(self):
        """parse_question извлекает scenario_multiplier."""
        result = parse_question(
            "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?"
        )
        assert result["scenario_multiplier"] == pytest.approx(1.2)

    def test_parse_no_scenario(self):
        """Без what-if scenario_multiplier = None."""
        result = parse_question("Сколько масла закупить на квартал?")
        assert result["scenario_multiplier"] is None