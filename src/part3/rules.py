"""Fallback: разбор вопроса без LLM.

Использует keyword matching и regex для извлечения:
- интента (forecast_purchase, deficit_risk, ...);
- SKU (OIL-001, масло, скраба, ...);
- периода (30, 90, 180 дней);
- бюджетного лимита (200 тысяч, 200000, ...);
- what-if сценария (+20%, −10%).
"""

from __future__ import annotations

import re

from src.part3.config import (
    INTENT_KEYWORDS,
    PERIOD_PATTERNS,
    RUS_NUMBERS,
)

# ─── Синонимы SKU ────────────────────────────────────────────────────
# Используем ОСНОВЫ слов (без окончаний).
# OIL-002 ДОЛЖЕН идти до OIL-001 — «ароматическое масло»
# содержит и «ароматическ», и «масл».
SKU_SYNONYMS: dict[str, list[str]] = {
    "OIL-002": ["ароматическ", "лаванд", "аромамасл"],
    "OIL-001": ["масл базов", "миндал", "массажн масл", "масл"],
    "SCRB-020": ["скраб", "кофейн"],
    "WRAP-030": ["маск", "альгинат", "обёртыван", "обертыван"],
    "CONS-051": ["тапоч", "тапк"],
    "CONS-052": ["шапоч", "шапк"],
}

# ─── Синонимы локаций ────────────────────────────────────────────────
LOCATION_SYNONYMS: dict[str, str] = {
    "ms-01": "MS-01",
    "ms 01": "MS-01",
    "мс-01": "MS-01",
    "ms-02": "MS-02",
    "ms 02": "MS-02",
    "мс-02": "MS-02",
    "сочи": "Сочи",
    "красн": "Красная Поляна",
    "полян": "Красная Поляна",
}


# ─── Нормализация чисел словами ─────────────────────────────────────

def _normalize_numbers(text: str) -> str:
    """Заменяет числа словами на цифры: 'три' → '3'."""
    for word, num in RUS_NUMBERS.items():
        text = re.sub(rf"\b{word}\b", str(num), text, flags=re.IGNORECASE)
    return text


# ─── Извлечение интентов ─────────────────────────────────────────────

def detect_intents(question: str) -> dict[str, int]:
    """Определяет интенты по ключевым словам."""
    q = question.lower()
    scores: dict[str, int] = {}

    for intent, keywords in INTENT_KEYWORDS.items():
        count = 0
        for kw in keywords:
            if kw in q:
                count += 1
        if count > 0:
            scores[intent] = count

    return scores


def pick_intent(scores: dict[str, int]) -> tuple[str, float]:
    """Выбирает интент с максимальным числом совпадений."""
    if not scores:
        return "unknown", 0.0

    sorted_intents = sorted(scores.items(), key=lambda x: -x[1])
    top_intent, top_score = sorted_intents[0]

    if len(sorted_intents) == 1:
        return top_intent, 0.9

    second_score = sorted_intents[1][1]
    gap = (top_score - second_score) / max(top_score, 1)

    confidence = min(1.0, 0.5 + gap * 0.5)
    return top_intent, confidence


# ─── Извлечение SKU ─────────────────────────────────────────────────

def extract_sku(question: str) -> str | None:
    """Ищет SKU по явному коду или синониму."""
    q = question.lower()

    # 1. Явный код (OIL-001, oil 001, ...)
    explicit = re.search(r"\b([a-z]{2,4})[\s\-]?(\d{2,3})\b", q)
    if explicit:
        prefix, number = explicit.groups()
        candidate = f"{prefix.upper()}-{number.zfill(3)}"
        if candidate in SKU_SYNONYMS:
            return candidate

    # 2. По синониму (основа слова)
    for sku, synonyms in SKU_SYNONYMS.items():
        for syn in synonyms:
            if syn in q:
                return sku

    return None


# ─── Извлечение локации ─────────────────────────────────────────────

def extract_location(question: str) -> str | None:
    """Ищет локацию по синониму."""
    q = question.lower()
    for syn, canonical in LOCATION_SYNONYMS.items():
        if syn in q:
            return canonical
    return None


# ─── Извлечение периода ─────────────────────────────────────────────

def extract_period_days(question: str) -> int | None:
    """Ищет период в днях."""
    q = _normalize_numbers(question.lower())

    for pattern, multiplier in PERIOD_PATTERNS:
        m = re.search(pattern, q)
        if m:
            if m.groups():
                try:
                    number = int(m.group(1))
                    return number * multiplier
                except (ValueError, IndexError):
                    continue
            else:
                return multiplier

    return None


# ─── Извлечение бюджетного лимита ───────────────────────────────────

def extract_budget_limit(question: str) -> float | None:
    """Ищет бюджетный лимит: «200 тысяч», «200000», «200 000 руб»."""
    q = question.lower()

    thousands = re.search(r"(\d+)\s*(тыс|тысяч)", q)
    if thousands:
        return float(thousands.group(1)) * 1000

    plain = re.search(r"(\d[\d\s]{2,})\s*(?:руб|₽|тыс)?", q)
    if plain:
        digits = re.sub(r"\s", "", plain.group(1))
        if digits.isdigit() and len(digits) >= 4:
            return float(digits)

    return None


# ─── Извлечение what-if сценария ────────────────────────────────────

def extract_scenario_multiplier(question: str) -> float | None:
    """
    Ищет what-if сценарий: «на 20%», «+20%», «вырастет на 20%»,
    «упадёт на 10%».

    Возвращает множитель (1.2 для +20%, 0.9 для −10%) или None.
    """
    q = question.lower()

    # Рост: «вырастет на 20%», «увеличится на 20%», «+20%»
    growth_patterns = [
        r"(?:выраст|увеличит|рост|подним|повыс)\w*\s*(?:ся)?\s*(?:на\s*)?(\d+)\s*%",
        r"\+\s*(\d+)\s*%",
    ]
    for pattern in growth_patterns:
        m = re.search(pattern, q)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 500:
                return round(1 + num / 100, 4)

    # Падение: «упадёт на 10%», «снизится на 10%», «−10%»
    fall_patterns = [
        r"(?:упад|снизит|уменьш|пониз)\w*\s*(?:ся)?\s*(?:на\s*)?(\d+)\s*%",
        r"[−-]\s*(\d+)\s*%",
    ]
    for pattern in fall_patterns:
        m = re.search(pattern, q)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 100:
                return round(1 - num / 100, 4)

    return None


# ─── Основная функция fallback ──────────────────────────────────────

def parse_question(question: str) -> dict:
    """
    Разбирает вопрос без LLM.

    Returns:
        {
            "intent": str,
            "intent_confidence": float,
            "sku": str | None,
            "location": str | None,
            "period_days": int | None,
            "budget_limit": float | None,
            "scenario_multiplier": float | None,
        }
    """
    scores = detect_intents(question)
    intent, intent_conf = pick_intent(scores)

    return {
        "intent": intent,
        "intent_confidence": intent_conf,
        "sku": extract_sku(question),
        "location": extract_location(question),
        "period_days": extract_period_days(question),
        "budget_limit": extract_budget_limit(question),
        "scenario_multiplier": extract_scenario_multiplier(question),
    }