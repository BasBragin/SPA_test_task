"""Тесты граничных случаев forecast_demand.

Покрывают:
- некорректный horizon_days (0, отрицательный, слишком большой);
- неизвестный SKU (нет в истории, нет в каталоге);
- отсутствие catalog в params;
- SKU с пустой историей или всеми None;
- проверку, что explanation не пустой.
"""

from __future__ import annotations

import copy

import pytest

from src.part2.forecast import forecast_demand

# ─── Валидация horizon_days ─────────────────────────────────────────

class TestHorizonValidation:

    @pytest.mark.parametrize("horizon", [0, -1, -30, 366, 1000])
    def test_invalid_horizon_raises(self, part2_history, part2_catalog, horizon):
        """Некорректный горизонт → ValueError."""
        with pytest.raises(ValueError):
            forecast_demand(
                part2_history, "OIL-001", horizon,
                {"catalog": part2_catalog},
            )

    @pytest.mark.parametrize("horizon", [1, 7, 30, 90, 180, 365])
    def test_valid_horizon_works(self, part2_history, part2_catalog, horizon):
        """Корректный горизонт — работает без ошибок."""
        result = forecast_demand(
            part2_history, "OIL-001", horizon,
            {"catalog": part2_catalog},
        )
        assert result["forecast_demand"] > 0


# ─── Валидация SKU ───────────────────────────────────────────────────

class TestSkuValidation:

    def test_unknown_sku_in_history(self, part2_history, part2_catalog):
        """SKU нет в истории → ValueError."""
        with pytest.raises(ValueError, match="отсутствует в history"):
            forecast_demand(
                part2_history, "UNKNOWN-999", 30,
                {"catalog": part2_catalog},
            )

    def test_unknown_sku_in_catalog(self, part2_history, part2_catalog):
        """SKU есть в истории, но нет в каталоге → ValueError."""
        history = copy.deepcopy(part2_history)
        history["weekly_consumption"]["NEW-SKU"] = [1.0] * 12
        history["current_stock"]["NEW-SKU"] = 10.0
        history["incoming_qty"]["NEW-SKU"] = 0.0

        with pytest.raises(ValueError, match="отсутствует в catalog"):
            forecast_demand(
                history, "NEW-SKU", 30,
                {"catalog": part2_catalog},
            )


# ─── Валидация params ────────────────────────────────────────────────

class TestParamsValidation:

    def test_missing_catalog_key(self, part2_history):
        """params без catalog → ValueError."""
        with pytest.raises(ValueError, match="отсутствует в catalog"):
            forecast_demand(part2_history, "OIL-001", 30, {})

    def test_empty_catalog(self, part2_history):
        """Пустой catalog → ValueError."""
        with pytest.raises(ValueError, match="отсутствует в catalog"):
            forecast_demand(part2_history, "OIL-001", 30, {"catalog": {}})


# ─── История с проблемами ────────────────────────────────────────────

class TestHistoryEdgeCases:

    def test_empty_history_list(self, part2_history, part2_catalog):
        """Пустой список в weekly_consumption → ValueError."""
        history = copy.deepcopy(part2_history)
        history["weekly_consumption"]["OIL-001"] = []

        with pytest.raises(ValueError, match="нет данных"):
            forecast_demand(history, "OIL-001", 30, {"catalog": part2_catalog})

    def test_all_none_history(self, part2_history, part2_catalog):
        """Все None в истории → ValueError."""
        history = copy.deepcopy(part2_history)
        history["weekly_consumption"]["OIL-001"] = [None] * 12

        with pytest.raises(ValueError, match="нет данных"):
            forecast_demand(history, "OIL-001", 30, {"catalog": part2_catalog})

    def test_zero_current_stock(self, part2_history, part2_catalog):
        """Нулевой остаток — считается корректно."""
        history = copy.deepcopy(part2_history)
        history["current_stock"]["OIL-001"] = 0.0
        history["incoming_qty"]["OIL-001"] = 0.0

        result = forecast_demand(history, "OIL-001", 30, {"catalog": part2_catalog})
        assert result["current_stock"] == 0.0
        assert result["recommended_qty"] > 0
        assert result["stockout_date"] is not None  # скоро закончится

    def test_zero_incoming(self, part2_history, part2_catalog):
        """Нулевой incoming — не влияет на ошибки."""
        history = copy.deepcopy(part2_history)
        history["incoming_qty"]["OIL-001"] = 0.0

        result = forecast_demand(history, "OIL-001", 30, {"catalog": part2_catalog})
        assert result["incoming_qty"] == 0.0


# ─── Explanation ─────────────────────────────────────────────────────

class TestExplanation:

    def test_explanation_not_empty(self, part2_history, part2_catalog):
        """Explanation содержит текст."""
        for sku in ["OIL-001", "SCRB-020", "WRAP-030"]:
            result = forecast_demand(
                part2_history, sku, 30,
                {"catalog": part2_catalog},
            )
            assert len(result["explanation"]) > 100

    def test_explanation_mentions_horizon(self, part2_history, part2_catalog):
        """Explanation упоминает горизонт."""
        result = forecast_demand(
            part2_history, "OIL-001", 30,
            {"catalog": part2_catalog},
        )
        assert "30" in result["explanation"]

    def test_explanation_mentions_shift(self, part2_history, part2_catalog):
        """Для SCRB-020 explanation упоминает скачок."""
        result = forecast_demand(
            part2_history, "SCRB-020", 30,
            {"catalog": part2_catalog},
        )
        assert "скачок" in result["explanation"]

    def test_explanation_no_shift_mention_for_oil(self, part2_history, part2_catalog):
        """Для OIL-001 explanation НЕ упоминает скачок."""
        result = forecast_demand(
            part2_history, "OIL-001", 30,
            {"catalog": part2_catalog},
        )
        assert "скачок" not in result["explanation"]


# ─── Кастомный alpha ─────────────────────────────────────────────────

class TestCustomAlpha:

    def test_alpha_overrides_default(self, part2_history, part2_catalog):
        """Кастомный alpha меняет результат."""
        r_default = forecast_demand(
            part2_history, "OIL-001", 30,
            {"catalog": part2_catalog},
        )
        r_alpha_1 = forecast_demand(
            part2_history, "OIL-001", 30,
            {"catalog": part2_catalog, "alpha": 1.0},  # = последнее значение
        )
        # α=1 → avg_daily = последнее недельное значение / 7
        # = 13.4 / 7 ≈ 1.914
        assert r_alpha_1["avg_daily_consumption"] == pytest.approx(1.914, abs=0.01)
        # Отличается от дефолтного
        assert r_alpha_1["avg_daily_consumption"] != r_default["avg_daily_consumption"]