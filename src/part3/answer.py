"""Оркестратор Части 3: разбор вопроса и формирование ответа.

Схема работы:
1. Пробуем LLM (GigaChat) → разбор вопроса.
2. Если LLM дала валидный интент → вызываем функцию расчёта.
3. Форматируем ответ для пользователя.
4. Если LLM недоступна → fallback на rules (keyword matching).
5. Если rules не справились → «вне домена» или уточнение.

What-if сценарии (scenario_multiplier):
- если задан, применяем к forecast_demand;
- понижаем confidence в 2 раза;
- добавляем предупреждение в ответ.

Возвращает: (params, confidence, answer_text).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.part2.forecast import fill_missing, forecast_demand
from src.part3 import formatter
from src.part3.config import (
    ANSWER_CONFIDENCE_BASE,
    INTENT_CONFIDENCE_THRESHOLD,
    PENALTY_AMBIGUOUS_INTENT,
    PENALTY_MISSING_PERIOD,
    PENALTY_MISSING_SKU,
    WHAT_IF_CONFIDENCE_PENALTY,
)
from src.part3.llm import llm_available, parse_question_with_llm
from src.part3.rules import parse_question as parse_question_with_rules

# ─── Хелперы ─────────────────────────────────────────────────────────

def _is_params_complete(intent: str, params: dict) -> bool:
    """Проверяет, достаточно ли данных для ответа."""
    if intent == "unknown":
        return False

    if intent in ("forecast_purchase", "stock_check") and not params.get("sku"):
        return False

    # Возвращаем negated condition напрямую (SIM103)
    return not (
        intent in ("forecast_purchase", "budget")
        and not params.get("period_days")
    )


def _compute_confidence(params: dict) -> float:
    """Вычисляет уверенность ответа."""
    confidence = ANSWER_CONFIDENCE_BASE
    intent = params.get("intent", "unknown")

    if intent == "unknown":
        return 0.0

    if intent in ("forecast_purchase", "stock_check") and not params.get("sku"):
        confidence -= PENALTY_MISSING_SKU

    if intent in ("forecast_purchase", "budget") and not params.get("period_days"):
        confidence -= PENALTY_MISSING_PERIOD

    if params.get("intent_confidence", 1.0) < INTENT_CONFIDENCE_THRESHOLD:
        confidence -= PENALTY_AMBIGUOUS_INTENT

    if params.get("scenario_multiplier") is not None:
        confidence *= WHAT_IF_CONFIDENCE_PENALTY

    return max(0.0, min(1.0, round(confidence, 4)))


def _describe_missing(params: dict) -> str:
    """Описывает, каких данных не хватает."""
    intent = params.get("intent")

    if intent in ("forecast_purchase", "stock_check") and not params.get("sku"):
        return "какой товар вас интересует?"

    if intent in ("forecast_purchase", "budget") and not params.get("period_days"):
        return "на какой период рассчитать?"

    return "уточните параметры запроса."


# ─── Применение what-if ─────────────────────────────────────────────

def _apply_what_if(
    result: dict[str, Any],
    multiplier: float,
) -> dict[str, Any]:
    """Применяет what-if множитель к результату forecast_demand."""
    adjusted = dict(result)

    for key in ("avg_daily_consumption", "forecast_demand",
                "safety_stock", "reorder_point"):
        adjusted[key] = round(result[key] * multiplier, 4)

    adjusted["recommended_qty"] = round(result["recommended_qty"] * multiplier, 2)
    adjusted["estimated_cost"] = round(result["estimated_cost"] * multiplier, 2)

    return adjusted


# ─── Сборщики данных ────────────────────────────────────────────────

def _collect_reorder_items(
    catalog: dict[str, dict],
    history: dict,
    period: int,
    sku_filter: str | None = None,
) -> list[dict]:
    """Собирает товары, которые нужно заказать."""
    items = []
    for sku, item in catalog.items():
        if sku_filter and sku != sku_filter:
            continue

        if sku not in history.get("weekly_consumption", {}):
            continue

        try:
            r = forecast_demand(history, sku, period, {"catalog": catalog})
        except (ValueError, KeyError, ZeroDivisionError):
            continue

        if r["recommended_qty"] > 0:
            items.append({
                "sku": sku,
                "name": item["name"],
                "unit": item["unit"],
                "recommended_qty": r["recommended_qty"],
                "cost": r["estimated_cost"],
                "stockout_date": r["stockout_date"],
            })

    items.sort(key=lambda x: x["stockout_date"] or "9999")
    return items


def _collect_budget_items(
    catalog: dict[str, dict],
    history: dict,
    period: int,
    sku_filter: str | None = None,
) -> list[dict]:
    """Собирает бюджет закупок."""
    items = []
    for sku, item in catalog.items():
        if sku_filter and sku != sku_filter:
            continue

        if sku not in history.get("weekly_consumption", {}):
            continue

        try:
            r = forecast_demand(history, sku, period, {"catalog": catalog})
        except (ValueError, KeyError, ZeroDivisionError):
            continue

        items.append({
            "sku": sku,
            "name": item["name"],
            "unit": item["unit"],
            "recommended_qty": r["recommended_qty"],
            "cost": r["estimated_cost"],
        })
    return items


def _collect_deficit_items(
    catalog: dict[str, dict],
    history: dict,
    period: int | None = None,
) -> list[dict]:
    """Собирает товары в риске дефицита."""
    as_of = history.get("as_of", "")
    items = []

    for sku, item in catalog.items():
        if sku not in history.get("weekly_consumption", {}):
            continue

        horizon = period if period else item.get("lead_time_days", 30)

        try:
            r = forecast_demand(history, sku, horizon, {"catalog": catalog})
        except (ValueError, KeyError, ZeroDivisionError):
            continue

        if r["stockout_date"]:
            try:
                d0 = date.fromisoformat(as_of)
                d1 = date.fromisoformat(r["stockout_date"])
                days_left = (d1 - d0).days
            except ValueError:
                days_left = None

            items.append({
                "sku": sku,
                "name": item["name"],
                "unit": item["unit"],
                "stockout_date": r["stockout_date"],
                "days_left": days_left,
                "recommended_qty": r["recommended_qty"],
                "cost": r["estimated_cost"],
            })

    items.sort(key=lambda x: x["stockout_date"] or "9999")
    return items


def _collect_trends(
    catalog: dict[str, dict],
    history: dict,
) -> list[dict]:
    """Собирает тренды по каждому SKU."""
    trends = []
    for sku, item in catalog.items():
        series = history.get("weekly_consumption", {}).get(sku, [])
        filled = fill_missing(series)
        if not filled or len(filled) < 2:
            continue

        first = filled[0]
        last = filled[-1]
        if first == 0:
            continue

        change_pct = (last - first) / first * 100

        trends.append({
            "sku": sku,
            "name": item["name"],
            "first_week": first,
            "last_week": last,
            "change_pct": change_pct,
        })

    trends.sort(key=lambda x: -abs(x["change_pct"]))
    return trends


# ─── Формирование ответа по интенту ─────────────────────────────────

def _build_answer(
    intent: str,
    params: dict,
    catalog: dict[str, dict],
    history: dict,
    confidence: float,
) -> str:
    """Вызывает нужную функцию расчёта и форматирует ответ."""

    if intent == "forecast_purchase":
        sku = params["sku"]
        period = params["period_days"]
        result = forecast_demand(history, sku, period, {"catalog": catalog})

        multiplier = params.get("scenario_multiplier")
        if multiplier is not None:
            result = _apply_what_if(result, multiplier)
            return formatter.format_what_if(
                sku, catalog[sku], result, period, multiplier, confidence,
            )

        return formatter.format_forecast_purchase(
            sku, catalog[sku], result, period,
        )

    if intent == "stock_check":
        sku = params["sku"]
        result = forecast_demand(history, sku, 30, {"catalog": catalog})
        return formatter.format_stock_check(sku, catalog[sku], result)

    if intent == "reorder_list":
        period = params.get("period_days") or 30
        sku_filter = params.get("sku")
        items = _collect_reorder_items(catalog, history, period, sku_filter)
        return formatter.format_reorder_list(items)

    if intent == "budget":
        period = params["period_days"]
        limit = params.get("budget_limit")
        sku_filter = params.get("sku")
        items = _collect_budget_items(catalog, history, period, sku_filter)
        return formatter.format_budget(items, period, limit)

    if intent == "deficit_risk":
        period = params.get("period_days")
        location = params.get("location")
        items = _collect_deficit_items(catalog, history, period)
        return formatter.format_deficit_risk(items, location)

    if intent == "expiry_risk":
        return formatter.format_expiry_risk(items=[])

    if intent == "price_dynamics":
        sku = params.get("sku")
        item = catalog.get(sku) if sku else None
        return formatter.format_price_dynamics(sku, item, None, None)

    if intent == "explain":
        trends = _collect_trends(catalog, history)
        return formatter.format_explain(trends)

    return formatter.format_unknown()


# ─── Основная функция ───────────────────────────────────────────────

def answer_question(
    question: str,
    context: dict,
) -> tuple[dict, float, str]:
    """
    Разбирает вопрос и формирует ответ.

    Returns:
        (params, confidence, answer_text).
    """
    # Ранний выход для пустого вопроса — не зовём LLM на мусор
    if not question or not question.strip():
        return (
            {"intent": "unknown"},
            0.0,
            formatter.format_clarify("какой у вас вопрос?"),
        )

    catalog = context["catalog"]
    history = context["history"]
    use_llm = context.get("use_llm", True)

    # ─── Шаг 1: пробуем LLM ─────────────────────────────────────
    if use_llm and llm_available():
        params = parse_question_with_llm(question, catalog)
        if params and params.get("intent") != "unknown":
            if _is_params_complete(params["intent"], params):
                confidence = _compute_confidence(params)
                answer = _build_answer(
                    params["intent"], params, catalog, history, confidence,
                )
                return params, confidence, answer

            missing = _describe_missing(params)
            clarify_params = {**params, "intent": "unknown"}
            return (
                clarify_params,
                _compute_confidence(params),
                formatter.format_clarify(missing),
            )

    # ─── Шаг 2: пробуем rules ───────────────────────────────────
    params = parse_question_with_rules(question)

    if params["intent"] != "unknown" and _is_params_complete(params["intent"], params):
        confidence = _compute_confidence(params)
        answer = _build_answer(
            params["intent"], params, catalog, history, confidence,
        )
        return params, confidence, answer

    if params["intent"] == "unknown":
        return (
            params,
            0.0,
            formatter.format_unknown(),
        )

    missing = _describe_missing(params)
    clarify_params = {**params, "intent": "unknown"}
    return (
        clarify_params,
        _compute_confidence(params),
        formatter.format_clarify(missing),
    )