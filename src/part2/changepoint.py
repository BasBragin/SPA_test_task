"""Детекция устойчивых скачков в данных расхода (changepoint).

Идея: перебираем все возможные точки разрыва, ищем ту, где средние
слева и справа отличаются сильнее всего. Если относительный рост
превышает порог И данные справа стабильны (CV мал) — считаем скачок
устойчивым (новый уровень спроса).
"""

from __future__ import annotations

from statistics import mean, stdev

from src.part2.config import (
    CHANGEPOINT_CV_MAX,
    CHANGEPOINT_MIN_SEGMENT,
    CHANGEPOINT_RATIO_THRESHOLD,
)


def _cv(values: list[float]) -> float:
    """Коэффициент вариации: std / mean. Возвращает 0.0 при mean = 0."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    if m == 0:
        return 0.0
    return stdev(values) / m


def detect_level_shift(
    values: list[float],
    min_segment: int = CHANGEPOINT_MIN_SEGMENT,
    ratio_threshold: float = CHANGEPOINT_RATIO_THRESHOLD,
    cv_max: float = CHANGEPOINT_CV_MAX,
) -> dict | None:
    """
    Ищет устойчивый скачок уровня в данных.

    Args:
        values: ряд значений (например, недельный расход).
        min_segment: минимум точек с каждой стороны от разрыва.
        ratio_threshold: минимальный относительный рост (right/left).
        cv_max: максимум CV справа — гарантия, что данные не «пила».

    Returns:
        Словарь {index, left_mean, right_mean, ratio, cv_right}
        или None, если устойчивого скачка не найдено.

    Example:
        >>> detect_level_shift([3.1, 2.9, 3.4, 3.0, 3.3, 3.2, 3.5, 3.1, 6.8, 7.4, 7.1, 7.6])
        {'index': 8, 'left_mean': 3.19, 'right_mean': 7.22, 'ratio': 2.26, 'cv_right': 0.05}
    """
    if len(values) < 2 * min_segment:
        return None

    best: dict | None = None

    for i in range(min_segment, len(values) - min_segment + 1):
        left = values[:i]
        right = values[i:]

        left_mean = mean(left)
        right_mean = mean(right)

        if left_mean <= 0:
            continue

        ratio = right_mean / left_mean
        if ratio < ratio_threshold:
            continue

        cv_right = _cv(right)
        if cv_right > cv_max:
            # Данные справа «пилообразные» — не устойчивый скачок.
            continue

        candidate = {
            "index": i,
            "left_mean": round(left_mean, 4),
            "right_mean": round(right_mean, 4),
            "ratio": round(ratio, 4),
            "cv_right": round(cv_right, 4),
        }

        # Выбираем скачок с максимальным относительным ростом.
        if best is None or candidate["ratio"] > best["ratio"]:
            best = candidate

    return best


def apply_level_shift(
    values: list[float],
    shift: dict | None,
) -> list[float]:
    """
    Возвращает ряд, обрезанный слева до точки скачка, если скачок найден.

    Логика: если уровень сменился, старая история нерелевантна для
    прогноза. Используем только «новый» сегмент.

    Args:
        values: исходный ряд.
        shift: результат detect_level_shift или None.

    Returns:
        Ряд, обрезанный до точки скачка, или исходный, если скачка нет.
    """
    if shift is None:
        return values
    return values[shift["index"]:]