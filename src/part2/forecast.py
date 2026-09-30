"""Часть 2: прогноз потребности и рекомендация закупки.

Функция forecast_demand рассчитывает:
- средний дневной расход (EWMA α=0.3);
- прогноз потребности на горизонт;
- текущий остаток и поставки в пути;
- страховой запас и точку заказа;
- рекомендуемый объём закупки (с округлением до упаковки);
- оценку стоимости;
- дату истощения;
- уверенность в прогнозе;
- текстовое объяснение.

Без обращения к LLM — только детерминированные расчёты.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, stdev

from src.part2.changepoint import apply_level_shift, detect_level_shift
from src.part2.config import (
    CONFIDENCE_BASE,
    CONFIDENCE_MIN_VOLATILITY_FACTOR,
    CONFIDENCE_MIN_WEEKS,
    CONFIDENCE_UNKNOWN_THRESHOLD,
    DAYS_PER_WEEK,
    EWMA_ALPHA,
    MAX_HORIZON_DAYS,
    MIN_HORIZON_DAYS,
)

# ─── Вспомогательные функции ─────────────────────────────────────────

def fill_missing(values: list[float | None]) -> list[float]:
    """
    Заполняет пропуски (None) в ряду линейной интерполяцией.

    - Пропуск в середине → линейная интерполяция между известными соседями.
    - Несколько подряд пропусков → равномерное распределение по индексам.
    - Пропуск в начале → первое известное значение.
    - Пропуск в конце → последнее известное значение.
    - Все None → пустой список.
    """
    if not values:
        return []

    if all(v is None for v in values):
        return []

    n = len(values)
    result = list(values)

    known_indices = [i for i, v in enumerate(values) if v is not None]

    if not known_indices:
        return []

    # Края
    first_known = known_indices[0]
    for i in range(first_known):
        result[i] = values[first_known]

    last_known = known_indices[-1]
    for i in range(last_known + 1, n):
        result[i] = values[last_known]

    # Интерполяция между известными
    for k in range(len(known_indices) - 1):
        i_left = known_indices[k]
        i_right = known_indices[k + 1]
        v_left = values[i_left]
        v_right = values[i_right]

        gap = i_right - i_left

        for i in range(i_left + 1, i_right):
            t = (i - i_left) / gap
            result[i] = v_left + t * (v_right - v_left)

    return result  # type: ignore[return-value]


def ewma(values: list[float], alpha: float = EWMA_ALPHA) -> float:
    """Экспоненциальное сглаживание (EWMA)."""
    if not values:
        raise ValueError("ewma: пустой список")

    s = values[0]
    for x in values[1:]:
        s = alpha * x + (1 - alpha) * s
    return s


def _coefficient_of_variation(values: list[float]) -> float:
    """Коэффициент вариации: std / mean. 0.0 при mean = 0 или len < 2."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    if m == 0:
        return 0.0
    return stdev(values) / m


def _round_up_to_pack(qty: float, pack_size: int, min_order_qty: int) -> float:
    """Округляет qty вверх до кратности pack_size и не меньше min_order_qty."""
    if qty <= 0:
        return 0.0

    packs = -(-qty // pack_size)  # ceil деление
    result = packs * pack_size

    result = max(result, min_order_qty)

    return float(result)


def _compute_confidence(weeks: int, cv: float, has_shift: bool) -> float:
    """
    Оценка уверенности в прогнозе (0.0 – 1.0).
    """
    length_factor = min(1.0, weeks / CONFIDENCE_MIN_WEEKS)

    volatility_factor = max(
        CONFIDENCE_MIN_VOLATILITY_FACTOR,
        1.0 - cv,
    )

    confidence = CONFIDENCE_BASE * length_factor * volatility_factor

    if has_shift:
        confidence *= 0.85

    return round(min(1.0, max(0.0, confidence)), 4)


def _build_explanation(
    sku: str,
    catalog_item: dict,
    weeks_used: int,
    has_shift: bool,
    avg_daily: float,
    forecast_demand: float,
    horizon_days: int,
    current_stock: float,
    incoming_qty: float,
    safety_stock: float,
    reorder_point: float,
    recommended_qty: float,
    estimated_cost: float,
    stockout_date: str | None,
    confidence: float,
) -> str:
    """Текстовое объяснение расчёта."""
    lines = [
        f"Прогноз для {sku} ({catalog_item['name']}) на {horizon_days} дней.",
        f"История: {weeks_used} недель"
        + (" (обнаружен скачок — используется только новый уровень)" if has_shift else ""),
        f"Средний дневной расход (EWMA α=0.3): {avg_daily:.4f} {catalog_item['unit']}/день.",
        f"Прогноз потребности: {forecast_demand:.4f} {catalog_item['unit']}.",
        f"Текущий остаток: {current_stock:.2f}, в пути: {incoming_qty:.2f}.",
        f"Страховой запас ({catalog_item['safety_stock_days']} дн): {safety_stock:.2f}.",
        f"Точка заказа: {reorder_point:.2f}.",
        (
            f"Рекомендуемая закупка: {recommended_qty:.2f} {catalog_item['unit']} "
            f"(упаковка {catalog_item['pack_size']}, минимум {catalog_item['min_order_qty']})."
        ),
        f"Оценка стоимости: {estimated_cost:.2f} ₽.",
        f"Ожидаемое истощение: {stockout_date or 'не прогнозируется в горизонте'}.",
        f"Уверенность: {confidence:.2f}"
        + (
            " — требуется уточнение."
            if confidence < CONFIDENCE_UNKNOWN_THRESHOLD
            else "."
        ),
    ]
    return "\n".join(lines)


# ─── Основная функция ────────────────────────────────────────────────

def forecast_demand(
    history: dict,
    sku: str,
    horizon_days: int,
    params: dict,
) -> dict:
    """
    Прогнозирует потребность и формирует рекомендацию закупки.
    """
    if horizon_days < MIN_HORIZON_DAYS or horizon_days > MAX_HORIZON_DAYS:
        raise ValueError(
            f"horizon_days={horizon_days} вне диапазона "
            f"[{MIN_HORIZON_DAYS}, {MAX_HORIZON_DAYS}]"
        )

    catalog = params.get("catalog", {})
    alpha = params.get("alpha", EWMA_ALPHA)

    if sku not in history.get("weekly_consumption", {}):
        raise ValueError(f"SKU {sku} отсутствует в history['weekly_consumption']")
    if sku not in catalog:
        raise ValueError(f"SKU {sku} отсутствует в catalog")

    catalog_item = catalog[sku]

    raw_values = history["weekly_consumption"][sku]
    filled = fill_missing(raw_values)

    if not filled:
        raise ValueError(f"SKU {sku}: нет данных для прогноза")

    shift = detect_level_shift(filled)
    has_shift = shift is not None
    effective = apply_level_shift(filled, shift)
    weeks_used = len(effective)

    smoothed_weekly = ewma(effective, alpha=alpha)
    avg_daily = smoothed_weekly / DAYS_PER_WEEK
    forecast_demand = avg_daily * horizon_days

    current_stock = float(history["current_stock"].get(sku, 0.0))
    incoming_qty = float(history["incoming_qty"].get(sku, 0.0))

    safety_stock = avg_daily * catalog_item["safety_stock_days"]
    reorder_point = avg_daily * (
        catalog_item["lead_time_days"] + catalog_item["safety_stock_days"]
    )

    needed = forecast_demand + safety_stock - current_stock - incoming_qty
    if needed <= 0:
        recommended_qty = 0.0
    else:
        recommended_qty = _round_up_to_pack(
            needed,
            pack_size=catalog_item["pack_size"],
            min_order_qty=catalog_item["min_order_qty"],
        )

    estimated_cost = recommended_qty * catalog_item["price"]

    total_available = current_stock + incoming_qty
    if avg_daily > 0:
        days_left = total_available / avg_daily
        as_of = date.fromisoformat(history["as_of"])
        stockout_dt = as_of + timedelta(days=days_left)
        if days_left <= horizon_days:
            stockout_date = stockout_dt.isoformat()
        else:
            stockout_date = None
    else:
        stockout_date = None

    cv = _coefficient_of_variation(effective)
    confidence = _compute_confidence(
        weeks=len(filled),
        cv=cv,
        has_shift=has_shift,
    )

    explanation = _build_explanation(
        sku=sku,
        catalog_item=catalog_item,
        weeks_used=weeks_used,
        has_shift=has_shift,
        avg_daily=avg_daily,
        forecast_demand=forecast_demand,
        horizon_days=horizon_days,
        current_stock=current_stock,
        incoming_qty=incoming_qty,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        recommended_qty=recommended_qty,
        estimated_cost=estimated_cost,
        stockout_date=stockout_date,
        confidence=confidence,
    )

    return {
        "avg_daily_consumption": round(avg_daily, 4),
        "forecast_demand": round(forecast_demand, 4),
        "current_stock": current_stock,
        "incoming_qty": incoming_qty,
        "safety_stock": round(safety_stock, 4),
        "reorder_point": round(reorder_point, 4),
        "recommended_qty": recommended_qty,
        "estimated_cost": round(estimated_cost, 2),
        "stockout_date": stockout_date,
        "confidence": confidence,
        "explanation": explanation,
    }