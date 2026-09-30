"""Тесты forecast_demand на реальных данных из задания.

Проверяют 3 SKU × 2 горизонта (30 и 90 дней):
- корректность структуры ответа;
- разумность значений;
- обработку скачка (SCRB-020 — история 4 недели);
- обработку пропуска (WRAP-030 — 12 недель);
- округление до упаковки;
- наличие stockout_date при риске дефицита;
- confidence в ожидаемом диапазоне.
"""

from __future__ import annotations

import pytest

from src.part2.forecast import forecast_demand

# ─── Общие проверки структуры ────────────────────────────────────────

class TestForecastStructure:
    """Проверки структуры ответа — для всех SKU и горизонтов."""

    @pytest.mark.parametrize("sku,horizon", [
        ("OIL-001", 30), ("OIL-001", 90),
        ("SCRB-020", 30), ("SCRB-020", 90),
        ("WRAP-030", 30), ("WRAP-030", 90),
    ])
    def test_all_keys_present(self, part2_history, part2_catalog, sku, horizon):
        result = forecast_demand(
            part2_history, sku, horizon,
            {"catalog": part2_catalog},
        )
        expected_keys = {
            "avg_daily_consumption", "forecast_demand",
            "current_stock", "incoming_qty",
            "safety_stock", "reorder_point",
            "recommended_qty", "estimated_cost",
            "stockout_date", "confidence", "explanation",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.parametrize("sku,horizon", [
        ("OIL-001", 30), ("SCRB-020", 90), ("WRAP-030", 30),
    ])
    def test_numeric_types(self, part2_history, part2_catalog, sku, horizon):
        result = forecast_demand(
            part2_history, sku, horizon,
            {"catalog": part2_catalog},
        )
        for field in ["avg_daily_consumption", "forecast_demand",
                      "safety_stock", "reorder_point", "estimated_cost"]:
            assert isinstance(result[field], float), f"{field}: {type(result[field])}"
        assert isinstance(result["confidence"], float)
        assert isinstance(result["recommended_qty"], float)
        assert isinstance(result["explanation"], str)
        assert len(result["explanation"]) > 50


# ─── OIL-001: стабильный рост ────────────────────────────────────────

class TestOil001:

    def test_30_days(self, part2_history, part2_catalog):
        result = forecast_demand(
            part2_history, "OIL-001", 30,
            {"catalog": part2_catalog},
        )
        assert result["avg_daily_consumption"] == pytest.approx(1.735, abs=0.01)
        assert result["forecast_demand"] == pytest.approx(52.06, abs=0.1)
        assert result["current_stock"] == 50.4
        assert result["incoming_qty"] == 20.0
        assert result["recommended_qty"] == 10.0
        assert result["estimated_cost"] == pytest.approx(12590.50, abs=0.1)
        assert result["stockout_date"] is None  # запас > 30 дней
        assert 0.7 < result["confidence"] < 1.0

    def test_90_days(self, part2_history, part2_catalog):
        result = forecast_demand(
            part2_history, "OIL-001", 90,
            {"catalog": part2_catalog},
        )
        assert result["forecast_demand"] == pytest.approx(156.18, abs=0.1)
        assert result["recommended_qty"] == 115.0
        assert result["stockout_date"] == "2026-10-25"

    def test_90_days_more_than_30(self, part2_history, part2_catalog):
        """На 90 дней закупка больше, чем на 30."""
        r30 = forecast_demand(part2_history, "OIL-001", 30, {"catalog": part2_catalog})
        r90 = forecast_demand(part2_history, "OIL-001", 90, {"catalog": part2_catalog})
        assert r90["recommended_qty"] > r30["recommended_qty"]
        assert r90["forecast_demand"] > r30["forecast_demand"]


# ─── SCRB-020: скачок + риск дефицита ────────────────────────────────

class TestScrb020:

    def test_shift_detected_in_history(self, part2_history, part2_catalog):
        """История должна быть 4 недели (после скачка)."""
        result = forecast_demand(
            part2_history, "SCRB-020", 30,
            {"catalog": part2_catalog},
        )
        assert "4 недель" in result["explanation"]
        assert "скачок" in result["explanation"]

    def test_30_days(self, part2_history, part2_catalog):
        result = forecast_demand(
            part2_history, "SCRB-020", 30,
            {"catalog": part2_catalog},
        )
        assert result["avg_daily_consumption"] == pytest.approx(1.027, abs=0.01)
        assert result["forecast_demand"] == pytest.approx(30.82, abs=0.1)
        assert result["recommended_qty"] == 36.0
        assert result["stockout_date"] == "2026-09-24"
        assert 0.6 < result["confidence"] < 0.9

    def test_90_days(self, part2_history, part2_catalog):
        result = forecast_demand(
            part2_history, "SCRB-020", 90,
            {"catalog": part2_catalog},
        )
        assert result["forecast_demand"] == pytest.approx(92.46, abs=0.1)
        assert result["recommended_qty"] == 98.0
        assert result["stockout_date"] == "2026-09-24"  # та же дата

    def test_confidence_penalty(self, part2_history, part2_catalog):
        """Confidence у SCRB-020 ниже, чем у OIL-001 (штраф за скачок)."""
        oil = forecast_demand(part2_history, "OIL-001", 30, {"catalog": part2_catalog})
        scrb = forecast_demand(part2_history, "SCRB-020", 30, {"catalog": part2_catalog})
        assert scrb["confidence"] < oil["confidence"]


# ─── WRAP-030: пропуск + избыток запаса ─────────────────────────────

class TestWrap030:

    def test_missing_filled_in_history(self, part2_history, part2_catalog):
        """История 12 недель — пропуск интерполирован."""
        result = forecast_demand(
            part2_history, "WRAP-030", 30,
            {"catalog": part2_catalog},
        )
        assert "12 недель" in result["explanation"]
        assert "скачок" not in result["explanation"]

    def test_30_days_no_purchase(self, part2_history, part2_catalog):
        """Запас + incoming > потребности → закупка не нужна."""
        result = forecast_demand(
            part2_history, "WRAP-030", 30,
            {"catalog": part2_catalog},
        )
        assert result["recommended_qty"] == 0.0
        assert result["estimated_cost"] == 0.0

    def test_90_days_needs_purchase(self, part2_history, part2_catalog):
        """На 90 дней запас кончится → закупка есть."""
        result = forecast_demand(
            part2_history, "WRAP-030", 90,
            {"catalog": part2_catalog},
        )
        assert result["recommended_qty"] > 0
        assert result["stockout_date"] is not None

    def test_high_confidence(self, part2_history, part2_catalog):
        """Стабильные данные без скачка → высокая уверенность."""
        result = forecast_demand(
            part2_history, "WRAP-030", 30,
            {"catalog": part2_catalog},
        )
        assert result["confidence"] > 0.9


# ─── Кросс-проверки ─────────────────────────────────────────────────

class TestCrossChecks:

    def test_explanation_contains_sku(self, part2_history, part2_catalog):
        """Explanation упоминает SKU."""
        for sku in ["OIL-001", "SCRB-020", "WRAP-030"]:
            result = forecast_demand(
                part2_history, sku, 30,
                {"catalog": part2_catalog},
            )
            assert sku in result["explanation"]

    def test_explanation_contains_confidence(self, part2_history, part2_catalog):
        """Explanation упоминает уверенность."""
        result = forecast_demand(
            part2_history, "OIL-001", 30,
            {"catalog": part2_catalog},
        )
        assert "Уверенность" in result["explanation"]

    def test_all_horizons_consistent(self, part2_history, part2_catalog):
        """avg_daily не зависит от горизонта."""
        for sku in ["OIL-001", "SCRB-020", "WRAP-030"]:
            r30 = forecast_demand(part2_history, sku, 30, {"catalog": part2_catalog})
            r90 = forecast_demand(part2_history, sku, 90, {"catalog": part2_catalog})
            assert r30["avg_daily_consumption"] == r90["avg_daily_consumption"]