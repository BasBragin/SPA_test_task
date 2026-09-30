"""Тесты для вспомогательных функций Части 2.

Покрывают:
- fill_missing: заполнение пропусков (линейная интерполяция, края, все None).
- ewma: экспоненциальное сглаживание.
- _round_up_to_pack: округление вверх до упаковки и min_order_qty.
- _coefficient_of_variation: CV для оценки волатильности.
"""

from __future__ import annotations

import pytest

from src.part2.forecast import (
    _coefficient_of_variation,
    _round_up_to_pack,
    ewma,
    fill_missing,
)

# ─── fill_missing ─────────────────────────────────────────────────────

class TestFillMissing:

    def test_no_missing(self):
        """Без пропусков — возвращает исходный список."""
        values = [1.0, 2.0, 3.0]
        assert fill_missing(values) == values

    def test_missing_in_middle(self):
        """Один пропуск в середине — линейная интерполяция."""
        values = [6.2, 5.8, 6.5, 6.0, None, 6.3, 6.1]
        result = fill_missing(values)
        # i=4, i_left=3, i_right=5, gap=2
        # t = (4-3)/2 = 0.5
        # value = 6.0 + 0.5 * (6.3 - 6.0) = 6.15
        assert result[4] == pytest.approx(6.15)
        assert len(result) == 7
        assert all(v is not None for v in result)

    def test_missing_at_start(self):
        """Пропуск в начале — берём первое известное."""
        values = [None, None, 5.0, 6.0]
        result = fill_missing(values)
        assert result[0] == 5.0
        assert result[1] == 5.0
        assert result[2] == 5.0

    def test_missing_at_end(self):
        """Пропуск в конце — берём последнее известное."""
        values = [5.0, 6.0, None, None]
        result = fill_missing(values)
        assert result[2] == 6.0
        assert result[3] == 6.0

    def test_multiple_consecutive_missing(self):
        """Несколько подряд пропусков — линейная интерполяция по индексам."""
        values = [4.0, None, None, None, 8.0]
        result = fill_missing(values)
        # i=1: 4 + (1/4) * 4 = 5.0
        # i=2: 4 + (2/4) * 4 = 6.0
        # i=3: 4 + (3/4) * 4 = 7.0
        assert result == [4.0, 5.0, 6.0, 7.0, 8.0]

    def test_multiple_gaps(self):
        """Несколько отдельных пропусков."""
        values = [1.0, None, 3.0, None, 5.0]
        result = fill_missing(values)
        # i=1: 1 + 0.5 * (3-1) = 2.0
        # i=3: 3 + 0.5 * (5-3) = 4.0
        assert result == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_all_missing(self):
        """Все None → пустой список."""
        assert fill_missing([None, None, None]) == []

    def test_empty_list(self):
        """Пустой список → пустой список."""
        assert fill_missing([]) == []

    def test_real_wrap_030(self):
        """Реальные данные WRAP-030: пропуск на 5-й неделе."""
        values = [6.2, 5.8, 6.5, 6.0, None, 6.3, 6.1, 6.4, 6.0, 6.6, 6.2, 6.9]
        result = fill_missing(values)
        assert result[4] == pytest.approx(6.15)
        assert len(result) == 12

    def test_single_known_value(self):
        """Одно известное значение, остальные None."""
        values = [None, None, 5.0, None, None]
        result = fill_missing(values)
        # Все пропуски = 5.0 (единственное известное)
        assert result == [5.0, 5.0, 5.0, 5.0, 5.0]


# ─── ewma ─────────────────────────────────────────────────────────────

class TestEwma:

    def test_single_value(self):
        """Одно значение — возвращает его же."""
        assert ewma([5.0]) == 5.0

    def test_constant_series(self):
        """Постоянный ряд — возвращает это же значение."""
        assert ewma([3.0, 3.0, 3.0, 3.0]) == pytest.approx(3.0)

    def test_simple_case(self):
        """Классический пример: [1, 2, 3], α=0.5."""
        # S1 = 1
        # S2 = 0.5*2 + 0.5*1 = 1.5
        # S3 = 0.5*3 + 0.5*1.5 = 2.25
        assert ewma([1.0, 2.0, 3.0], alpha=0.5) == pytest.approx(2.25)

    def test_alpha_one(self):
        """α=1 — EWMA = последнее значение."""
        assert ewma([1.0, 2.0, 3.0], alpha=1.0) == 3.0

    def test_alpha_zero(self):
        """α=0 — EWMA = первое значение."""
        assert ewma([1.0, 2.0, 3.0], alpha=0.0) == 1.0

    def test_empty_raises(self):
        """Пустой список — ошибка."""
        with pytest.raises(ValueError):
            ewma([])


# ─── _round_up_to_pack ────────────────────────────────────────────────

class TestRoundUpToPack:

    @pytest.mark.parametrize("qty,pack,min_qty,expected", [
        # Стандартные случаи
        (12.0, 5, 10, 15.0),     # ceil(12/5)=3, 3*5=15
        (10.0, 5, 10, 10.0),     # ровно 2 упаковки
        (3.0,  5, 10, 10.0),     # меньше упаковки, но ≥ min
        (1.0,  5, 10, 10.0),     # то же
        (5.95, 5, 10, 10.0),     # ceil(5.95/5)=2, 2*5=10
        (110.07, 5, 10, 115.0),  # ceil(110.07/5)=23, 23*5=115
        (97.44, 1, 5, 98.0),     # pack=1, min=5
        (200.0, 50, 100, 200.0), # CONS-051
        (250.0, 100, 200, 300.0),# CONS-052
    ])
    def test_rounding(self, qty, pack, min_qty, expected):
        result = _round_up_to_pack(qty, pack_size=pack, min_order_qty=min_qty)
        assert result == pytest.approx(expected), (
            f"qty={qty}, pack={pack}, min={min_qty}: "
            f"получили {result}, ожидали {expected}"
        )

    def test_zero_qty(self):
        """qty <= 0 → 0.0."""
        assert _round_up_to_pack(0.0, pack_size=5, min_order_qty=10) == 0.0
        assert _round_up_to_pack(-5.0, pack_size=5, min_order_qty=10) == 0.0

    def test_negative_returns_zero(self):
        """Отрицательное → 0.0 (не заказываем в минус)."""
        assert _round_up_to_pack(-100.0, pack_size=5, min_order_qty=10) == 0.0


# ─── _coefficient_of_variation ───────────────────────────────────────

class TestCoefficientOfVariation:

    def test_constant_series(self):
        """Постоянный ряд — CV = 0."""
        assert _coefficient_of_variation([5.0, 5.0, 5.0]) == 0.0

    def test_simple_case(self):
        """[2, 4, 6] → std=2, mean=4, CV=0.5."""
        result = _coefficient_of_variation([2.0, 4.0, 6.0])
        assert result == pytest.approx(0.5)

    def test_single_value(self):
        """Одно значение → CV = 0."""
        assert _coefficient_of_variation([5.0]) == 0.0

    def test_empty(self):
        """Пустой список → CV = 0."""
        assert _coefficient_of_variation([]) == 0.0

    def test_zero_mean(self):
        """Mean = 0 → CV = 0 (защита от деления)."""
        assert _coefficient_of_variation([0.0, 0.0]) == 0.0