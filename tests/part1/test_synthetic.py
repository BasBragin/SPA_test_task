"""Блок 2: синтетические тесты — формы тары, падежи, граничные случаи.

Покрывают случаи, которых нет в M1–M8, но которые ожидаются
в реальных данных spa-оператора.

ВАЖНО: часть тестов помечена `xfail` — они показывают, какие формы
слов ещё не поддерживаются regex и требуют доработки. `XFAIL` в выводе
pytest — это НЕ ошибка, а ожидаемое поведение.
"""

from __future__ import annotations

import math

import pytest

from src.part1.part1_normalize import normalize_movement

# ─── 2.1. Формы тары: канистры, бутылки, упаковки, коробки ──────────

class TestContainerForms:
    """Разные формы слов тары + числительные."""

    @pytest.mark.parametrize("text,expected_qty", [
        # Канистры — разные падежи и числа
        ("2 канистры по 5 л",     10.0),
        ("3 канистры по 10 л",    30.0),

        # Бутылки
        ("4 бутылки по 1 л",       4.0),
        ("2 бутыли по 0,5 л",      1.0),

        # Упаковки
        ("4 уп. по 50 пар",      200.0),
        ("2 упаковки по 100 шт", 200.0),
        ("3 пачки по 25 шт",      75.0),

        # Коробки / мешки
        ("2 коробки по 10 кг",    20.0),
        ("1 мешок 25 кг",         25.0),
    ])
    def test_container_forms(self, catalog, text, expected_qty):
        result = normalize_movement(text, catalog)
        assert result["qty"] == expected_qty, (
            f"'{text}': qty = {result['qty']!r}, ожидалось {expected_qty!r}"
        )


# ─── 2.2. Окончания и склонения единиц ──────────────────────────────

class TestUnitInflections:
    """Разные склонения единиц измерения.

    NB: quantity всегда привязано к SKU — иначе unit невозможно 
    определить. В тестах добавляем SKU явно.
    """

    @pytest.mark.parametrize("text,expected_qty,expected_unit", [
        # Короткие формы — с SKU, unit берётся из каталога
        ("Приход OIL-001 450 мл",    0.45,  "л"),
        ("Приход OIL-001 2 л",       2.0,   "л"),
        ("Приход WRAP-030 3,5 кг",   3.5,   "кг"),
        ("Приход CONS-051 48 пар",  48.0,   "пар"),
        ("Приход CONS-052 120 шт", 120.0,   "шт"),

        # Длинные формы (пока НЕ поддерживаются)
        pytest.param(
            "Приход OIL-001 1 литр", 1.0, "л",
            marks=pytest.mark.xfail(reason="Форма «литр» пока не поддерживается"),
        ),
        pytest.param(
            "Приход OIL-001 2 литра", 2.0, "л",
            marks=pytest.mark.xfail(reason="Форма «литра» пока не поддерживается"),
        ),
        pytest.param(
            "Приход WRAP-030 500 грамм", 0.5, "кг",
            marks=pytest.mark.xfail(reason="Форма «грамм» пока не поддерживается"),
        ),
    ])
    def test_unit_inflections(self, catalog, text, expected_qty, expected_unit):
        result = normalize_movement(text, catalog)
        assert result["qty"] == expected_qty, (
            f"'{text}': qty = {result['qty']!r}, ожидалось {expected_qty!r}"
        )
        assert result["unit"] == expected_unit, (
            f"'{text}': unit = {result['unit']!r}, ожидалось {expected_unit!r}"
        )


# ─── 2.3. Отрицательные числа и корректировки ───────────────────────

class TestNegativeQuantities:
    """Отрицательные количества с разными типами минуса."""

    @pytest.mark.parametrize("text,expected_qty", [
        ("Корректировка: -120 шт", -120.0),   # U+002D hyphen
        ("Корректировка: −120 шт", -120.0),   # U+2212 minus sign
        ("Корректировка: -0,5 кг",   -0.5),
    ])
    def test_negative(self, catalog, text, expected_qty):
        result = normalize_movement(text, catalog)
        assert result["qty"] == expected_qty, (
            f"'{text}': qty = {result['qty']!r}, ожидалось {expected_qty!r}"
        )
        assert result["operation"] == "correction"


# ─── 2.4. Даты — все поддерживаемые форматы ────────────────────────

class TestDateFormats:
    """Все форматы дат, которые должны поддерживаться."""

    @pytest.mark.parametrize("text,expected_date", [
        ("05.03.2026",        "2026-03-05"),  # dd.mm.yyyy
        ("5.03.2026",         "2026-03-05"),  # d.mm.yyyy
        ("05.03.26",          "2026-03-05"),  # dd.mm.yy
        ("1 марта 2026",      "2026-03-01"),  # текстовый
        ("1 марта 2026 г.",   "2026-03-01"),
        ("12 марта 2026 г.",  "2026-03-12"),
        ("2026-03-08",        "2026-03-08"),  # ISO
        ("03/06/26",          "2026-03-06"),  # US mm/dd/yy
    ])
    def test_dates(self, catalog, text, expected_date):
        result = normalize_movement(text, catalog)
        assert result["date"] == expected_date, (
            f"'{text}': date = {result['date']!r}, ожидалось {expected_date!r}"
        )


# ─── 2.5. Операции — все типы ───────────────────────────────────────

class TestOperations:
    """Все 5 типов операций + приоритеты."""

    @pytest.mark.parametrize("text,expected_op", [
        ("приход OIL-001 1 л",          "receipt"),
        ("поступление OIL-001 1 л",     "receipt"),
        ("расход OIL-001 1 л",          "consume"),
        ("использовано OIL-001 1 л",    "consume"),
        ("списание OIL-001 1 л",        "writeoff"),
        ("истёк срок OIL-001 1 л",      "writeoff"),
        ("возврат OIL-001 1 л",         "return"),
        ("корректировка OIL-001 1 л",   "correction"),
        ("инвентаризация OIL-001 1 л",  "correction"),
    ])
    def test_operations(self, catalog, text, expected_op):
        result = normalize_movement(text, catalog)
        assert result["operation"] == expected_op, (
            f"'{text}': operation = {result['operation']!r}, "
            f"ожидалось {expected_op!r}"
        )

    def test_writeoff_priority_over_consume(self, catalog):
        """«списание ... истёк срок» — writeoff, не consume."""
        result = normalize_movement(
            "Списание SCRB-020 1 кг, истёк срок", catalog,
        )
        assert result["operation"] == "writeoff"


# ─── 2.6. SKU — нормализация написания ──────────────────────────────

class TestSkuNormalization:
    """Разные написания одного и того же SKU."""

    @pytest.mark.parametrize("text,expected_sku", [
        ("OIL-001",   "OIL-001"),
        ("oil 001",   "OIL-001"),
        ("OIL 001",   "OIL-001"),
        ("oil-001",   "OIL-001"),
    ])
    def test_sku_variants(self, catalog, text, expected_sku):
        result = normalize_movement(f"Приход {text} 1 л", catalog)
        assert result["sku"] == expected_sku, (
            f"'{text}': sku = {result['sku']!r}, ожидалось {expected_sku!r}"
        )


# ─── 2.7. Алиасы названий (без SKU) ─────────────────────────────────

class TestSkuAliases:
    """Сопоставление названий без SKU через алиасы."""

    @pytest.mark.parametrize("text,expected_sku", [
        ("Приход тапочек одноразовых 100 пар", "CONS-051"),
        ("Приход шапочек 200 шт",              "CONS-052"),
        ("Приход скраба кофейного 1 кг",       "SCRB-020"),
        ("Приход альгинатной маски 1 кг",      "WRAP-030"),
    ])
    def test_aliases(self, catalog, text, expected_sku):
        result = normalize_movement(text, catalog)
        assert result["sku"] == expected_sku, (
            f"'{text}': sku = {result['sku']!r}, ожидалось {expected_sku!r}"
        )


# ─── 2.8. Граничные случаи ─────────────────────────────────────────

class TestEdgeCases:
    """Мусор, пустые строки, минимальный ввод."""

    def test_empty_string(self, catalog):
        result = normalize_movement("", catalog)
        assert all(v is None for v in result.values())

    def test_whitespace_only(self, catalog):
        result = normalize_movement("   ", catalog)
        assert all(v is None for v in result.values())

    def test_too_short(self, catalog):
        result = normalize_movement("xy", catalog)
        assert all(v is None for v in result.values())

    def test_garbage(self, catalog):
        """Мусорный ввод не падает и возвращает валидную структуру."""
        result = normalize_movement("qwerty asdf 123 !!!", catalog)
        assert isinstance(result, dict)
        assert set(result.keys()) == {
            "date", "sku", "location", "operation",
            "qty", "unit", "batch", "doc_no",
        }

    def test_all_fields_present(self, catalog):
        """Результат всегда содержит все 8 ключей."""
        result = normalize_movement(
            "05.03.2026 приход OIL-001 10 л", catalog,
        )
        assert set(result.keys()) == {
            "date", "sku", "location", "operation",
            "qty", "unit", "batch", "doc_no",
        }

    def test_qty_is_number_or_none(self, catalog):
        """qty — либо None, либо конечное число."""
        for text in ["приход OIL-001 5 л", "мусор", "123"]:
            result = normalize_movement(text, catalog)
            qty = result["qty"]
            if qty is not None:
                assert isinstance(qty, (int, float))
                assert not math.isnan(qty)
                assert not math.isinf(qty)