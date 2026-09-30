"""Тесты для форматтеров Части 3.

Покрывают все функции format_* из src/part3/formatter.py.
Не требуют LLM.
"""

from __future__ import annotations

from src.part3 import formatter

# ─── Минимальные данные для тестов ──────────────────────────────────

CATALOG_ITEM = {
    "sku": "OIL-001",
    "name": "Массажное масло базовое (миндаль)",
    "unit": "л",
    "pack_size": 5,
    "min_order_qty": 10,
    "safety_stock_days": 14,
    "lead_time_days": 7,
    "price": 1259.05,
}

RESULT_FORECAST = {
    "avg_daily_consumption": 1.7353,
    "forecast_demand": 52.0584,
    "current_stock": 50.4,
    "incoming_qty": 20.0,
    "safety_stock": 24.2939,
    "reorder_point": 36.4409,
    "recommended_qty": 10.0,
    "estimated_cost": 12590.5,
    "stockout_date": None,
    "confidence": 0.8432,
    "explanation": "Прогноз для OIL-001...\nИстория: 12 недель.",
}


# ─── format_forecast_purchase ───────────────────────────────────────

class TestFormatForecast:

    def test_contains_sku_and_name(self):
        text = formatter.format_forecast_purchase(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30,
        )
        assert "OIL-001" in text
        assert "Массажное масло" in text

    def test_contains_period(self):
        text = formatter.format_forecast_purchase(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30,
        )
        assert "30 дней" in text

    def test_contains_recommended_and_cost(self):
        text = formatter.format_forecast_purchase(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30,
        )
        assert "10.00" in text
        assert "12 590.50" in text

    def test_no_stockout_date(self):
        text = formatter.format_forecast_purchase(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30,
        )
        assert "Ожидаемое истощение" not in text

    def test_with_stockout_date(self):
        result = {**RESULT_FORECAST, "stockout_date": "2026-10-25"}
        text = formatter.format_forecast_purchase(
            "OIL-001", CATALOG_ITEM, result, 30,
        )
        assert "2026-10-25" in text

    def test_contains_explanation(self):
        text = formatter.format_forecast_purchase(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30,
        )
        assert "Обоснование" in text
        assert "История: 12 недель" in text


# ─── format_what_if ─────────────────────────────────────────────────

class TestFormatWhatIf:

    def test_contains_what_if_header(self):
        text = formatter.format_what_if(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30, 1.2, 0.45,
        )
        assert "WHAT-IF" in text

    def test_contains_multiplier(self):
        text = formatter.format_what_if(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30, 1.2, 0.45,
        )
        assert "×1.20" in text
        assert "+20%" in text

    def test_contains_warning(self):
        text = formatter.format_what_if(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30, 1.2, 0.45,
        )
        assert "ПРЕДПОЛОЖЕНИЕ" in text
        assert "перепроверьте" in text

    def test_shows_adjusted_confidence(self):
        text = formatter.format_what_if(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30, 1.2, 0.45,
        )
        assert "0.45" in text
        assert "понижена" in text

    def test_negative_change(self):
        text = formatter.format_what_if(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST, 30, 0.8, 0.45,
        )
        assert "-20%" in text


# ─── format_reorder_list ────────────────────────────────────────────

class TestFormatReorderList:

    def test_empty(self):
        text = formatter.format_reorder_list([])
        assert "не требуются" in text or "Срочных заказов нет" in text

    def test_one_item(self):
        items = [{
            "sku": "SCRB-020",
            "name": "Скраб для тела кофейный",
            "unit": "кг",
            "recommended_qty": 36.0,
            "cost": 64422.0,
            "stockout_date": "2026-09-24",
        }]
        text = formatter.format_reorder_list(items)
        assert "SCRB-020" in text
        assert "36.00" in text
        assert "64 422.00" in text
        assert "2026-09-24" in text

    def test_total_cost(self):
        items = [
            {"sku": "A", "name": "Товар A", "unit": "шт",
             "recommended_qty": 10.0, "cost": 1000.0, "stockout_date": None},
            {"sku": "B", "name": "Товар B", "unit": "шт",
             "recommended_qty": 5.0, "cost": 500.0, "stockout_date": None},
        ]
        text = formatter.format_reorder_list(items)
        assert "1 500.00" in text


# ─── format_budget ──────────────────────────────────────────────────

class TestFormatBudget:

    def test_empty(self):
        text = formatter.format_budget([], 30)
        assert "не требуются" in text

    def test_with_items(self):
        items = [
            {"sku": "OIL-001", "name": "Масло", "unit": "л",
             "recommended_qty": 10.0, "cost": 12590.5},
        ]
        text = formatter.format_budget(items, 30)
        assert "OIL-001" in text
        assert "30 дней" in text
        assert "12 590.50" in text

    def test_with_limit_within(self):
        items = [
            {"sku": "A", "name": "A", "unit": "шт",
             "recommended_qty": 1.0, "cost": 100.0},
        ]
        text = formatter.format_budget(items, 30, budget_limit=200000.0)
        assert "Лимит" in text
        assert "Остаток" in text

    def test_with_limit_exceeded(self):
        items = [
            {"sku": "A", "name": "A", "unit": "шт",
             "recommended_qty": 1.0, "cost": 250000.0},
        ]
        text = formatter.format_budget(items, 30, budget_limit=200000.0)
        assert "Превышение" in text


# ─── format_deficit_risk ────────────────────────────────────────────

class TestFormatDeficitRisk:

    def test_empty(self):
        text = formatter.format_deficit_risk([])
        assert "не обнаружено" in text

    def test_with_location(self):
        items = [{
            "sku": "SCRB-020", "name": "Скраб", "unit": "кг",
            "stockout_date": "2026-09-24", "days_left": 9,
            "recommended_qty": 16.0,
        }]
        text = formatter.format_deficit_risk(items, location="Сочи")
        assert "Сочи" in text
        assert "SCRB-020" in text
        assert "16.00" in text

    def test_without_location(self):
        items = [{
            "sku": "SCRB-020", "name": "Скраб", "unit": "кг",
            "stockout_date": "2026-09-24", "days_left": 9,
            "recommended_qty": 16.0,
        }]
        text = formatter.format_deficit_risk(items)
        assert "Риск дефицита" in text


# ─── format_expiry_risk ─────────────────────────────────────────────

class TestFormatExpiryRisk:

    def test_empty(self):
        text = formatter.format_expiry_risk([])
        assert "нет" in text.lower() or "Рекомендую" in text


# ─── format_price_dynamics ──────────────────────────────────────────

class TestFormatPriceDynamics:

    def test_no_catalog_item(self):
        text = formatter.format_price_dynamics(None, None, None, None)
        assert "нет" in text.lower() or "Рекомендую" in text

    def test_no_history(self):
        text = formatter.format_price_dynamics(
            "OIL-001", CATALOG_ITEM, None, None,
        )
        assert "OIL-001" in text
        assert "Истории цен нет" in text

    def test_with_history(self):
        text = formatter.format_price_dynamics(
            "OIL-001", CATALOG_ITEM, 1000.0, 1200.0,
        )
        assert "1 000.00" in text
        assert "1 200.00" in text
        assert "+200.00" in text
        assert "+20.0%" in text


# ─── format_stock_check ─────────────────────────────────────────────

class TestFormatStockCheck:

    def test_basic(self):
        text = formatter.format_stock_check(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST,
        )
        assert "OIL-001" in text
        assert "50.40" in text
        assert "20.00" in text
        assert "70.40" in text  # 50.40 + 20.00

    def test_contains_days_left(self):
        text = formatter.format_stock_check(
            "OIL-001", CATALOG_ITEM, RESULT_FORECAST,
        )
        # 70.4 / 1.7353 ≈ 41 дней
        assert "Хватит" in text
        assert "дней" in text


# ─── format_explain ─────────────────────────────────────────────────

class TestFormatExplain:

    def test_empty(self):
        text = formatter.format_explain([])
        assert "нет" in text.lower()

    def test_with_trends(self):
        trends = [
            {"sku": "SCRB-020", "name": "Скраб",
             "first_week": 3.1, "last_week": 7.6, "change_pct": 145.2},
            {"sku": "OIL-001", "name": "Масло",
             "first_week": 8.4, "last_week": 13.4, "change_pct": 59.5},
        ]
        text = formatter.format_explain(trends)
        assert "SCRB-020" in text
        assert "+145.2%" in text
        assert "Возможные причины" in text


# ─── format_unknown ─────────────────────────────────────────────────

class TestFormatUnknown:

    def test_contains_what_i_can(self):
        text = formatter.format_unknown()
        assert "вне моей компетенции" in text
        assert "Прогноз закупки" in text


# ─── format_clarify ─────────────────────────────────────────────────

class TestFormatClarify:

    def test_basic(self):
        text = formatter.format_clarify("какой товар вас интересует?")
        assert "Уточните" in text
        assert "какой товар" in text

    def test_with_options(self):
        text = formatter.format_clarify(
            "выберите период", options=["30", "90", "180"],
        )
        assert "30" in text
        assert "90" in text