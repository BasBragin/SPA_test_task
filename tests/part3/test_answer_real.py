"""Тесты answer_question на 15 вопросах из Приложения 1.

Требуют доступ к GigaChat (API-ключ + интернет).
Если LLM недоступна — тесты пропускаются.
"""

from __future__ import annotations

import pytest

from src.part3.answer import answer_question
from src.part3.llm import llm_available

# Пропускаем весь модуль, если LLM недоступна
pytestmark = pytest.mark.skipif(
    not llm_available(),
    reason="GIGACHAT_CREDENTIALS не задан — LLM-тесты пропущены",
)


# ─── Ожидания по 15 вопросам ────────────────────────────────────────

QUESTIONS_EXPECTED = [
    {
        "text": "Сколько масла закупить на три месяца и сколько это будет стоить?",
        "intent": "forecast_purchase",
        "sku": "OIL-001",
        "period_days": 90,
        "answer_contains": ["OIL-001", "90 дней"],
    },
    {
        "text": "Что нужно заказать в ближайшие 14 дней?",
        "intent": "reorder_list",
        "sku": None,
        "period_days": 14,
        "answer_contains": ["Товары к заказу"],
    },
    {
        "text": "Какой бюджет закупок на квартал?",
        "intent": "budget",
        "sku": None,
        "period_days": 90,
        "answer_contains": ["Бюджет закупок"],
    },
    {
        "text": "Что закончится до следующей поставки в Сочи?",
        "intent": "deficit_risk",
        "sku": None,
        "period_days": None,
        "answer_contains": ["Риск дефицита", "Сочи"],
    },
    {
        "text": "Какие партии сгорят в этом месяце?",
        "intent": "expiry_risk",
        "sku": None,
        "period_days": None,
        "answer_contains": ["срок", "годности", "expiry_date"],
    },
    {
        "text": "Насколько подорожало ароматическое масло у поставщика?",
        "intent": "price_dynamics",
        "sku": "OIL-002",
        "period_days": None,
        "answer_contains": ["OIL-002"],
    },
    {
        "text": "Сколько альгинатной маски осталось в Красной Поляне?",
        "intent": "stock_check",
        "sku": "WRAP-030",
        "period_days": None,
        "answer_contains": ["WRAP-030", "Остаток"],
    },
    {
        "text": "Посчитай закупку скраба на полгода при лимите 200 тысяч",
        "intent": "forecast_purchase",
        "sku": "SCRB-020",
        "period_days": 180,
        "answer_contains": ["SCRB-020", "180 дней"],
    },
    {
        "text": "Почему план закупок вырос по сравнению с прошлым кварталом?",
        "intent": "explain",
        "sku": None,
        "period_days": None,
        "answer_contains": ["Объяснение", "Возможные причины"],
    },
    {
        "text": "Сколько стоит закупить всё, что в риске дефицита?",
        "intent": "deficit_risk",
        "sku": None,
        "period_days": None,
        "answer_contains": ["Риск дефицита"],
    },
    {
        "text": "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
        "intent": "forecast_purchase",
        "sku": "OIL-001",
        "period_days": 30,
        "answer_contains": ["WHAT-IF", "×1.20"],
    },
    {
        "text": "Заказать масло",
        "intent": "reorder_list",
        "sku": "OIL-001",
        "period_days": None,
        "answer_contains": ["OIL-001"],
    },
    {
        "text": "Сколько это будет стоить?",
        "intent": None,
        "sku": None,
        "period_days": None,
        "answer_contains": ["Уточните"],
    },
    {
        "text": "Когда привезут заказ от поставщика?",
        "intent": "unknown",
        "sku": None,
        "period_days": None,
        "answer_contains": ["вне моей компетенции"],
    },
    {
        "text": "Какая погода в Сочи на выходных?",
        "intent": "unknown",
        "sku": None,
        "period_days": None,
        "answer_contains": ["вне моей компетенции"],
    },
]


# ─── Параметризованный тест по интенту ──────────────────────────────

@pytest.mark.parametrize(
    "case",
    QUESTIONS_EXPECTED,
    ids=[f"Q{i + 1}" for i in range(len(QUESTIONS_EXPECTED))],
)
def test_intent(part3_context, case):
    """Интент определён правильно."""
    if case["intent"] is None:
        pytest.skip("Интент не проверяется для этого вопроса")

    params, _conf, _answer = answer_question(case["text"], part3_context)
    assert params["intent"] == case["intent"], (
        f"'{case['text']}': intent={params['intent']}, "
        f"ожидалось {case['intent']}"
    )


# ─── Проверка SKU ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    [c for c in QUESTIONS_EXPECTED if c["sku"] is not None],
    ids=[
        f"Q{i + 1}" for i, c in enumerate(QUESTIONS_EXPECTED)
        if c["sku"] is not None
    ],
)
def test_sku(part3_context, case):
    """SKU извлечён правильно."""
    params, _conf, _answer = answer_question(case["text"], part3_context)
    assert params["sku"] == case["sku"], (
        f"'{case['text']}': sku={params['sku']}, "
        f"ожидалось {case['sku']}"
    )


# ─── Проверка периода ───────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    [c for c in QUESTIONS_EXPECTED if c["period_days"] is not None],
    ids=[
        f"Q{i + 1}" for i, c in enumerate(QUESTIONS_EXPECTED)
        if c["period_days"] is not None
    ],
)
def test_period(part3_context, case):
    """Период извлечён правильно."""
    params, _conf, _answer = answer_question(case["text"], part3_context)
    assert params["period_days"] == case["period_days"], (
        f"'{case['text']}': period={params['period_days']}, "
        f"ожидалось {case['period_days']}"
    )


# ─── Проверка содержимого ответа ───────────────────────────────────

@pytest.mark.parametrize(
    "case",
    QUESTIONS_EXPECTED,
    ids=[f"Q{i + 1}" for i in range(len(QUESTIONS_EXPECTED))],
)
def test_answer_contains(part3_context, case):
    """Ответ содержит ключевые слова."""
    _params, _conf, answer = answer_question(case["text"], part3_context)
    for keyword in case["answer_contains"]:
        assert keyword in answer, (
            f"'{case['text']}': в ответе нет '{keyword}'\n"
            f"Ответ: {answer[:300]}"
        )


# ─── Проверка confidence ────────────────────────────────────────────

@pytest.mark.parametrize(
    "case",
    QUESTIONS_EXPECTED,
    ids=[f"Q{i + 1}" for i in range(len(QUESTIONS_EXPECTED))],
)
def test_confidence_in_range(part3_context, case):
    """Confidence в диапазоне [0.0, 1.0]."""
    _params, confidence, _answer = answer_question(
        case["text"], part3_context,
    )
    assert 0.0 <= confidence <= 1.0


# ─── Отдельный тест what-if ─────────────────────────────────────────

def test_what_if_confidence_halved(part3_context):
    """What-if понижает уверенность в 2 раза."""
    _p1, conf_what_if, _a1 = answer_question(
        "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
        part3_context,
    )
    _p2, conf_regular, _a2 = answer_question(
        "Сколько масла уйдёт за месяц?",
        part3_context,
    )
    assert conf_what_if < conf_regular
    assert conf_what_if == pytest.approx(conf_regular * 0.5, abs=0.05)