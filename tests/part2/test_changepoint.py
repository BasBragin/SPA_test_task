"""Тесты для детекции скачков (changepoint).

Покрывают:
- detect_level_shift: реальные данные (SCRB-020, OIL-001, WRAP-030),
  синтетика (скачок в середине, слишком мало точек, все равны).
- apply_level_shift: обрезка ряда до нового уровня.
"""

from __future__ import annotations

import pytest

from src.part2.changepoint import apply_level_shift, detect_level_shift

# ─── detect_level_shift: реальные данные ─────────────────────────────

class TestDetectLevelShiftReal:

    def test_scrb_020_has_shift(self):
        """SCRB-020: скачок ×2.25 на 9-й неделе."""
        scrb = [3.1, 2.9, 3.4, 3.0, 3.3, 3.2, 3.5, 3.1, 6.8, 7.4, 7.1, 7.6]
        shift = detect_level_shift(scrb)

        assert shift is not None
        assert shift["index"] == 8
        assert shift["left_mean"] == pytest.approx(3.1875, abs=0.01)
        assert shift["right_mean"] == pytest.approx(7.225, abs=0.01)
        assert shift["ratio"] == pytest.approx(2.2667, abs=0.01)
        assert shift["cv_right"] < 0.25

    def test_oil_001_no_shift(self):
        """OIL-001: плавный рост — устойчивого скачка нет."""
        oil = [8.4, 9.1, 8.8, 9.6, 10.2, 9.4, 11.0, 10.6, 12.3, 11.8, 12.9, 13.4]
        shift = detect_level_shift(oil)
        assert shift is None

    def test_wrap_030_no_shift(self):
        """WRAP-030: данные стабильны — скачка нет."""
        wrap = [6.2, 5.8, 6.5, 6.0, 6.15, 6.3, 6.1, 6.4, 6.0, 6.6, 6.2, 6.9]
        shift = detect_level_shift(wrap)
        assert shift is None


# ─── detect_level_shift: синтетика ──────────────────────────────────

class TestDetectLevelShiftSynthetic:

    def test_clear_shift_in_middle(self):
        """Явный скачок в середине."""
        values = [1.0, 1.1, 1.0, 1.05, 1.0, 5.0, 5.1, 5.0, 5.05, 5.0]
        shift = detect_level_shift(values)

        assert shift is not None
        assert shift["index"] == 5
        # left_mean = 1.03, right_mean = 5.03, ratio = 4.88
        assert shift["ratio"] == pytest.approx(4.88, abs=0.1)

    def test_shift_at_end(self):
        """Скачок в конце — тоже находится."""
        values = [3.0, 3.1, 3.0, 3.05, 3.0, 3.1, 6.0, 6.1, 6.0]
        shift = detect_level_shift(values)

        assert shift is not None
        assert shift["index"] == 6

    def test_no_shift_constant(self):
        """Постоянный ряд — скачка нет."""
        values = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        assert detect_level_shift(values) is None

    def test_small_shift_below_threshold(self):
        """Небольшой рост (< ×1.5) — не считается скачком."""
        values = [4.0, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 5.0]  # ratio = 1.25
        assert detect_level_shift(values) is None

    def test_shift_but_noisy_right(self):
        """Скачок есть, но справа «пила» (CV > 0.25) — не устойчивый."""
        values = [3.0, 3.0, 3.0, 3.0, 10.0, 5.0, 15.0, 4.0, 12.0]  # CV высокий
        shift = detect_level_shift(values)
        assert shift is None

    def test_too_short_series(self):
        """Ряд короче 2 * min_segment — None."""
        assert detect_level_shift([1.0, 2.0, 3.0]) is None
        assert detect_level_shift([1.0]) is None
        assert detect_level_shift([]) is None

    def test_zero_left_mean(self):
        """Ряд с нулями слева — не должен падать."""
        values = [0.0, 0.0, 0.0, 0.0, 5.0, 5.0, 5.0, 5.0]
        result = detect_level_shift(values)
        # Код пропускает точки с left_mean=0, но находит скачок
        # с первой точки, где left_mean > 0
        assert result is not None
        assert result["ratio"] >= 1.5

    def test_custom_threshold(self):
        """Свой порог ratio."""
        values = [4.0, 4.0, 4.0, 4.0, 5.0, 5.0, 5.0, 5.0]  # ratio = 1.25
        # При стандартном пороге 1.5 — None
        assert detect_level_shift(values) is None
        # При пороге 1.2 — скачок найден
        shift = detect_level_shift(values, ratio_threshold=1.2)
        assert shift is not None
        assert shift["index"] == 4


# ─── apply_level_shift ──────────────────────────────────────────────

class TestApplyLevelShift:

    def test_apply_with_shift(self):
        """Со скачком — возвращает только правую часть."""
        values = [1.0, 1.1, 1.0, 5.0, 5.1, 5.0]
        shift = {"index": 3, "left_mean": 1.03, "right_mean": 5.03,
                 "ratio": 4.88, "cv_right": 0.01}
        result = apply_level_shift(values, shift)
        assert result == [5.0, 5.1, 5.0]

    def test_apply_without_shift(self):
        """Без скачка — возвращает исходный ряд."""
        values = [1.0, 1.1, 1.0, 1.05]
        result = apply_level_shift(values, None)
        assert result == values

    def test_apply_real_scrb(self):
        """Реальный SCRB-020: обрезка до 4 недель."""
        scrb = [3.1, 2.9, 3.4, 3.0, 3.3, 3.2, 3.5, 3.1, 6.8, 7.4, 7.1, 7.6]
        shift = detect_level_shift(scrb)
        result = apply_level_shift(scrb, shift)
        assert result == [6.8, 7.4, 7.1, 7.6]
        assert len(result) == 4