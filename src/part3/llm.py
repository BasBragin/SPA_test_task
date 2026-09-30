"""Интеграция с GigaChat для разбора вопросов (NLU).

Модуль отвечает только за разбор вопроса:
- принимает текст вопроса и каталог;
- отправляет запрос в GigaChat с системным промптом;
- парсит JSON-ответ;
- верифицирует значения (SKU в каталоге, период > 0);
- применяет приоритетные фразы (если LLM ошиблась с интентом).

Расчёты чисел — НЕ здесь. За них отвечает forecast_demand и др.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from src.part3.config import (
    GIGACHAT_MODEL,
    GIGACHAT_SCOPE,
    GIGACHAT_TIMEOUT,
    INTENTS,
)
from src.part3.system_prompt import build_system_prompt

# ─── Приоритетные фразы ──────────────────────────────────────────────
PRIORITY_PHRASES: list[tuple[list[str], str]] = [
    (["в риске дефицита", "риск дефицита", "в риске", "закончится"], "deficit_risk"),
    (["срок годности", "сгорит", "сгорят", "истекает"], "expiry_risk"),
    (["осталось", "остаток на складе", "сколько на складе"], "stock_check"),
    (["почему", "отчего", "по какой причине", "причина"], "explain"),
    (["подорожало", "подешевело", "динамика цен"], "price_dynamics"),
]


# ─── Проверка доступности LLM ────────────────────────────────────────

def llm_available() -> bool:
    """Проверяет, задан ли ключ GigaChat."""
    return bool(os.getenv("GIGACHAT_CREDENTIALS"))


# ─── Парсинг JSON из ответа LLM ─────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any] | None:
    """Извлекает JSON из ответа LLM."""
    if not text:
        return None

    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ─── Верификация ─────────────────────────────────────────────────────

def _verify_params(
    params: dict[str, Any],
    catalog: dict[str, dict],
) -> dict[str, Any]:
    """
    Проверяет корректность разобранных параметров.

    - intent должен быть из списка INTENTS;
    - sku должен быть в каталоге (иначе None);
    - period_days > 0 (иначе None);
    - budget_limit > 0 (иначе None);
    - scenario_multiplier > 0 и < 10 (иначе None).
    """
    verified = dict(params)

    # Intent
    if verified.get("intent") not in INTENTS:
        verified["intent"] = "unknown"

    # SKU
    sku = verified.get("sku")
    if sku and sku not in catalog:
        verified["sku"] = None

    # Period
    period = verified.get("period_days")
    if period is not None:
        try:
            period = int(period)
            if period <= 0 or period > 365:
                period = None
        except (ValueError, TypeError):
            period = None
        verified["period_days"] = period

    # Budget
    budget = verified.get("budget_limit")
    if budget is not None:
        try:
            budget = float(budget)
            if budget <= 0:
                budget = None
        except (ValueError, TypeError):
            budget = None
        verified["budget_limit"] = budget

    # Scenario multiplier (what-if)
    multiplier = verified.get("scenario_multiplier")
    if multiplier is not None:
        try:
            multiplier = float(multiplier)
            # Допустимый диапазон: 0 < multiplier < 10
            if multiplier <= 0 or multiplier >= 10 or multiplier == 1.0:
                multiplier = None
        except (ValueError, TypeError):
            multiplier = None
        verified["scenario_multiplier"] = multiplier

    return verified


# ─── Приоритетные фразы ──────────────────────────────────────────────

def _apply_priority_phrases(
    params: dict[str, Any],
    question: str,
) -> dict[str, Any]:
    """Форсирует интент, если в вопросе есть приоритетная фраза."""
    q = question.lower()
    result = dict(params)

    for phrases, forced_intent in PRIORITY_PHRASES:
        for phrase in phrases:
            if phrase in q:
                result["intent"] = forced_intent
                result["reasoning"] = (
                    f"Приоритетная фраза «{phrase}» → {forced_intent}"
                )
                return result

    return result


# ─── Основная функция ───────────────────────────────────────────────

def parse_question_with_llm(
    question: str,
    catalog: dict[str, dict],
) -> dict[str, Any] | None:
    """
    Разбирает вопрос через GigaChat.

    Returns:
        Словарь с разобранными параметрами:
        {
            "intent": str,
            "sku": str | None,
            "location": str | None,
            "period_days": int | None,
            "budget_limit": float | None,
            "scenario_multiplier": float | None,
            "reasoning": str,
        }
        Или None, если LLM недоступна / ошибка.
    """
    if not llm_available():
        return None

    try:
        from gigachat import GigaChat
    except ImportError:
        return None

    credentials = os.getenv("GIGACHAT_CREDENTIALS")
    system_prompt = build_system_prompt(catalog)

    try:
        with GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,
            scope=GIGACHAT_SCOPE,
            model=GIGACHAT_MODEL,
            timeout=GIGACHAT_TIMEOUT,
        ) as giga:
            response = giga.chat({
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                "temperature": 0.1,
            })

            raw_text = response.choices[0].message.content
            parsed = _extract_json(raw_text)

            if parsed is None:
                return {
                    "intent": "unknown",
                    "sku": None,
                    "location": None,
                    "period_days": None,
                    "budget_limit": None,
                    "scenario_multiplier": None,
                    "reasoning": "LLM вернула невалидный JSON",
                }

            verified = _verify_params(parsed, catalog)
            return _apply_priority_phrases(verified, question)

    except Exception as e:  # noqa: BLE001
        return {
            "intent": "unknown",
            "sku": None,
            "location": None,
            "period_days": None,
            "budget_limit": None,
            "scenario_multiplier": None,
            "reasoning": f"Ошибка LLM: {type(e).__name__}: {e}",
        }