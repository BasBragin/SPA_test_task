"""Streamlit-чат для Части 3.

Запуск:
    streamlit run app.py

Возможности:
- Чат с LLM (GigaChat).
- Прогон 15 вопросов из ТЗ.
- Просмотр категориального меню (fallback).

Для скриншотов в RESULTS.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Загружаем .env ДО импорта src — чтобы GIGACHAT_CREDENTIALS
# был доступен в llm_available().
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

from src.part3.answer import answer_question

# ─── Конфигурация страницы ──────────────────────────────────────────

st.set_page_config(
    page_title="SPA-помощник",
    page_icon="",
    layout="wide",
)


# ─── Загрузка данных ─────────────────────────────────────────────────

@st.cache_data
def load_data():
    with open(PROJECT_ROOT / "catalog.json", encoding="utf-8") as f:
        catalog_list = json.load(f)
    catalog = {item["sku"]: item for item in catalog_list}

    with open(
        PROJECT_ROOT / "src" / "part2" / "dataset_part2.json",
        encoding="utf-8",
    ) as f:
        history = json.load(f)

    return catalog, history


CATALOG, HISTORY = load_data()
CONTEXT = {"catalog": CATALOG, "history": HISTORY}


QUESTIONS_15 = [
    "Сколько масла закупить на три месяца и сколько это будет стоить?",
    "Что нужно заказать в ближайшие 14 дней?",
    "Какой бюджет закупок на квартал?",
    "Что закончится до следующей поставки в Сочи?",
    "Какие партии сгорят в этом месяце?",
    "Насколько подорожало ароматическое масло у поставщика?",
    "Сколько альгинатной маски осталось в Красной Поляне?",
    "Посчитай закупку скраба на полгода при лимите 200 тысяч",
    "Почему план закупок вырос по сравнению с прошлым кварталом?",
    "Сколько стоит закупить всё, что в риске дефицита?",
    "Сколько масла уйдёт за месяц, если загрузка вырастет на 20%?",
    "Заказать масло",
    "Сколько это будет стоить?",
    "Когда привезут заказ от поставщика?",
    "Какая погода в Сочи на выходных?",
]


# ─── Утилита для рендера ответа ─────────────────────────────────────
# Если в ответе есть таблица (символы ─), используем st.code —
# он сохраняет моноширинный шрифт и пробелы.
# Иначе — st.markdown для обычного текста.

def render_answer(answer: str) -> None:
    """Рендерит ответ: таблицу — через st.code, текст — через st.markdown."""
    if "─" in answer:
        st.code(answer, language=None)
    else:
        st.markdown(answer)


# ─── Заголовок ───────────────────────────────────────────────────────

st.title("SPA-помощник по складскому учёту")
st.caption("MVP: прогноз закупок, риск дефицита, бюджет и объяснения")


# ─── Вкладки ─────────────────────────────────────────────────────────

tab_chat, tab_15, tab_menu = st.tabs([
    "Чат",
    "15 вопросов из ТЗ",
    "Категориальное меню (fallback)",
])


# ─── Вкладка 1: Чат ──────────────────────────────────────────────────

with tab_chat:
    st.header("Чат с ИИ-помощником")
    st.markdown(
        "Задайте вопрос на русском языке. "
        "Например: *«Сколько масла закупить на квартал?»*"
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                render_answer(msg["content"])
            else:
                st.markdown(msg["content"])

    if prompt := st.chat_input("Ваш вопрос..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Думаю..."):
                params, confidence, answer = answer_question(prompt, CONTEXT)

            render_answer(answer)
            st.caption(
                f"Интент: `{params.get('intent')}` · "
                f"Уверенность: `{confidence:.2f}`"
            )

        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )

    if st.button("Очистить историю"):
        st.session_state.messages = []
        st.rerun()


# ─── Вкладка 2: 15 вопросов ─────────────────────────────────────────

with tab_15:
    st.header("Прогон 15 вопросов из ТЗ")
    st.markdown(
        "Все вопросы из Приложения 1. Нажмите кнопку — "
        "получите ответы для каждого."
    )

    if st.button("Прогнать все 15 вопросов", type="primary"):
        progress = st.progress(0.0)
        results_container = st.container()

        for i, q in enumerate(QUESTIONS_15, 1):
            with (
                results_container,
                st.expander(f"{i}. {q}", expanded=False),
                st.spinner("Обработка..."),
            ):
                params, confidence, answer = answer_question(q, CONTEXT)

                render_answer(answer)
                st.caption(
                    f"Интент: `{params.get('intent')}` · "
                    f"SKU: `{params.get('sku')}` · "
                    f"Период: `{params.get('period_days')}` · "
                    f"Уверенность: `{confidence:.2f}`"
                )

            progress.progress(i / len(QUESTIONS_15))

        st.success(f"Готово: {len(QUESTIONS_15)} ответов")


# ─── Вкладка 3: Меню fallback ───────────────────────────────────────

with tab_menu:
    st.header("Категориальное меню (fallback)")
    st.markdown(
        "Режим без LLM: пользователь выбирает действие из меню. "
        "Используется при отсутствии API-ключа."
    )

    st.info(
        "В браузере интерактивное меню (input) не работает. "
        "Для тестирования меню запустите CLI: "
        "`python scripts/check_question.py --menu`"
    )

    st.markdown("### Как выглядит меню")
    st.code(
        """
==================================================
Главное меню:
==================================================

Действие:
  [1] Прогноз закупки (сколько и когда заказать)
  [2] Список товаров к заказу (что срочно)
  [3] Бюджет закупок на период
  [4] Риск дефицита (что закончится)
  [5] Остаток товара на складе
  [q] Выход
Ваш выбор:
        """,
        language="text",
    )

    st.markdown("### Пример результата (Прогноз закупки → OIL-001 → 90 дней)")
    st.code(
        """
Прогноз закупки: OIL-001 — Массажное масло базовое (миндаль)
Период: 90 дней

Показатель               Значение
──────────────────────────────────────────────
Средний дневной расход   1.74 л
Прогноз потребности      156.18 л
Текущий остаток          50.40 л
В пути                   20.00 л
Страховой запас          24.29 л
Точка заказа             36.44 л
──────────────────────────────────────────────
Рекомендуемая закупка    115.00 л
Оценка стоимости         144 790.75 ₽
Ожидаемое истощение      2026-10-25
Уверенность              0.84
        """,
        language="text",
    )