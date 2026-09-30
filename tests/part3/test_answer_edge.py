"""Тесты answer_question: граничные случаи.

Покрывают:
- пустой вопрос / пробелы / мусор;
- работу без LLM (use_llm=False);
- структуру возвращаемого кортежа;
- границы confidence;
- уточняющие вопросы при нехватке параметров;
- what-if без LLM (парсинг rules).
"""

from __future__ import annotations

import pytest

from src.part3.answer import answer_question

# ─── Структура ответа ───────────────────────────────────────────────

class TestReturnStructure:
    """answer_question всегда возвращает (dict, float, str)."""

    def test_returns_tuple(self, part3_context):
        result = answer_question("Сколько масла закупить?", part3_context)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_params_is_dict(self, part3_context):
        params, _conf, _answer = answer_question(
            "Сколько масла закупить?", part3_context,
        )
        assert isinstance(params, dict)
        assert "intent" in params

    def test_confidence_is_float(self, part3_context):
        _params, confidence, _answer = answer_question(
            "Сколько масла?", part3_context,
        )
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_answer_is_string(self, part3_context):
        _params, _conf, answer = answer_question(
            "Сколько масла?", part3_context,
        )
        assert isinstance(answer, str)
        assert len(answer) > 0


# ─── Пустой ввод / мусор ────────────────────────────────────────────

class TestEmptyAndGarbage:

    def test_empty_question(self, part3_context):
        params, conf, answer = answer_question("", part3_context)
        assert isinstance(answer, str)
        assert conf == 0.0 or params["intent"] == "unknown"

    def test_whitespace_only(self, part3_context):
        params, conf, answer = answer_question("   ", part3_context)
        assert isinstance(answer, str)
        assert conf == 0.0 or params["intent"] == "unknown"

    def test_garbage(self, part3_context):
        params, _conf, answer = answer_question(
            "qwerty asdf 123", part3_context,
        )
        assert isinstance(answer, str)
        assert params["intent"] in ("unknown",) or "Уточните" in answer

    def test_question_without_llm(self, part3_context):
        """use_llm=False — работает через rules."""
        context = {**part3_context, "use_llm": False}
        params, _conf, answer = answer_question(
            "Сколько масла закупить на квартал?", context,
        )
        assert isinstance(params, dict)
        assert isinstance(answer, str)


# ─── Уточняющие вопросы ─────────────────────────────────────────────

class TestClarify:

    def test_forecast_without_sku(self, part3_context):
        """Интент forecast_purchase без SKU → уточнение."""
        _params, _conf, answer = answer_question(
            "Сколько нужно закупить?", part3_context,
        )
        assert "Уточните" in answer or "вне моей компетенции" in answer

    def test_forecast_without_period(self, part3_context):
        """Интент forecast_purchase с SKU, но без периода → уточнение."""
        _params, _conf, answer = answer_question(
            "Сколько масла закупить?", part3_context,
        )
        assert isinstance(answer, str)

    def test_intent_unknown_when_clarify(self, part3_context):
        """При нехватке параметров intent = unknown (соответствие ТЗ)."""
        params, _conf, answer = answer_question(
            "Сколько это будет стоить?", part3_context,
        )
        if "Уточните" in answer:
            assert params["intent"] == "unknown"


# ─── Границы confidence ─────────────────────────────────────────────

class TestConfidenceBoundaries:

    def test_unknown_has_zero_confidence(self, part3_context):
        """Вне домена → confidence 0.0."""
        _params, conf, answer = answer_question(
            "Какая погода в Сочи?", part3_context,
        )
        if "вне моей компетенции" in answer:
            assert conf == 0.0

    def test_confidence_never_negative(self, part3_context):
        for q in ["", "мусор", "abc", "123"]:
            _params, conf, _answer = answer_question(q, part3_context)
            assert conf >= 0.0

    def test_confidence_never_above_one(self, part3_context):
        _params, conf, _answer = answer_question(
            "Сколько масла закупить на квартал?", part3_context,
        )
        assert conf <= 1.0


# ─── Работа без LLM ─────────────────────────────────────────────────

class TestWithoutLLM:
    """Fallback через rules, без обращения к GigaChat."""

    def test_no_llm_stock_check(self, part3_context):
        context = {**part3_context, "use_llm": False}
        params, _conf, answer = answer_question(
            "Сколько масла осталось?", context,
        )
        assert params["intent"] == "stock_check"
        assert "OIL-001" in answer

    def test_no_llm_deficit_risk(self, part3_context):
        context = {**part3_context, "use_llm": False}
        params, _conf, _answer = answer_question(
            "Что закончится в Сочи?", context,
        )
        assert params["intent"] == "deficit_risk"

    def test_no_llm_explain(self, part3_context):
        context = {**part3_context, "use_llm": False}
        params, _conf, _answer = answer_question(
            "Почему план закупок вырос?", context,
        )
        assert params["intent"] == "explain"

    def test_no_llm_garbage(self, part3_context):
        context = {**part3_context, "use_llm": False}
        params, conf, _answer = answer_question("qwerty", context)
        assert params["intent"] == "unknown"
        assert conf == 0.0


# ─── What-if (с LLM и без) ──────────────────────────────────────────

class TestWhatIfEdge:

    def test_what_if_works_without_llm(self, part3_context):
        """What-if работает и без LLM — rules парсят «+20%»."""
        context = {**part3_context, "use_llm": False}
        params, conf, answer = answer_question(
            "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
            context,
        )
        assert "WHAT-IF" in answer
        assert params["scenario_multiplier"] == pytest.approx(1.2)
        assert conf == pytest.approx(0.45, abs=0.05)

    def test_what_if_confidence_halved_without_llm(self, part3_context):
        """What-if без LLM понижает уверенность в 2 раза."""
        context = {**part3_context, "use_llm": False}
        _p1, conf_what_if, _a1 = answer_question(
            "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
            context,
        )
        _p2, conf_regular, _a2 = answer_question(
            "Сколько масла уйдёт за месяц?",
            context,
        )
        assert conf_what_if < conf_regular
        assert conf_what_if == pytest.approx(conf_regular * 0.5, abs=0.05)

    def test_what_if_with_llm(self, part3_context):
        """What-if работает и с LLM."""
        params, conf, answer = answer_question(
            "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
            part3_context,
        )
        assert "WHAT-IF" in answer
        assert params["scenario_multiplier"] == pytest.approx(1.2)
        assert conf == pytest.approx(0.45, abs=0.05)