"""Fallback-меню категорий.

Работает без LLM: пользователь выбирает действие из меню,
затем указывает параметры. Меню зовёт те же функции расчёта
(forecast_demand и др.), что и LLM-путь.

Навигация:
- [0] Назад — вернуться на уровень выше.
- [q] Выход — выйти из программы.

Используется:
- при отсутствии API-ключа;
- при ошибке LLM;
- как явный режим CLI (--menu).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from src.part2.forecast import forecast_demand

# ─── Специальные значения ────────────────────────────────────────────
BACK = "__back__"
EXIT = "__exit__"


# ─── Пункты меню ─────────────────────────────────────────────────────
# В главном меню [q] уже включён сюда, поэтому _pick_from_list
# вызывается с allow_exit=False (чтобы не было дублирования).

MENU_ITEMS = [
    ("1", "forecast_purchase", "Прогноз закупки (сколько и когда заказать)"),
    ("2", "reorder_list",      "Список товаров к заказу (что срочно)"),
    ("3", "budget",            "Бюджет закупок на период"),
    ("4", "deficit_risk",      "Риск дефицита (что закончится)"),
    ("5", "stock_check",       "Остаток товара на складе"),
    ("q", "exit",              "Выход"),
]


# ─── Ввод от пользователя ────────────────────────────────────────────

def _input(prompt: str) -> str:
    """Обёртка над input для тестируемости."""
    return input(prompt).strip()


def _pick_from_list(
    prompt: str,
    options: list[tuple[str, str, str]],
    *,
    allow_back: bool = True,
    allow_exit: bool = True,
) -> str | None:
    """Показывает список вариантов и возвращает выбранное значение."""
    print(f"\n{prompt}")
    for key, label, _ in options:
        print(f"  [{key}] {label}")

    if allow_back:
        print("  [0] Назад")
    if allow_exit:
        print("  [q] Выход")

    while True:
        answer = _input("Ваш выбор: ").lower()
        if not answer:
            return None

        if answer == "0" and allow_back:
            return BACK
        if answer == "q" and allow_exit:
            return EXIT

        for key, _, value in options:
            if answer == key:
                return value

        print("Некорректный выбор. Попробуйте снова.")


def _ask_sku(catalog: dict[str, dict]) -> str | None:
    """Показывает нумерованный список SKU."""
    options = [
        (str(i), f"{sku} — {item['name']}", sku)
        for i, (sku, item) in enumerate(catalog.items(), start=1)
    ]
    return _pick_from_list("Выберите товар:", options)


def _ask_period() -> int | str | None:
    """Спрашивает период в днях. Может вернуть BACK / EXIT."""
    options = [
        ("1", "30 дней (месяц)", "30"),
        ("2", "90 дней (квартал)", "90"),
        ("3", "180 дней (полгода)", "180"),
        ("4", "365 дней (год)", "365"),
    ]
    value = _pick_from_list("Выберите период:", options)
    if value in (None, BACK, EXIT):
        return value
    return int(value)


def _ask_budget() -> float | str | None:
    """Спрашивает бюджетный лимит."""
    answer = _input(
        "Бюджетный лимит в рублях "
        "(0 — назад, q — выход, Enter — без лимита): "
    ).lower()

    if answer == "0":
        return BACK
    if answer == "q":
        return EXIT
    if not answer:
        return None

    try:
        return float(answer.replace(" ", "").replace(",", "."))
    except ValueError:
        print("Некорректное число. Лимит не установлен.")
        return None


# ─── Хелперы ─────────────────────────────────────────────────────────

def _is_back_or_exit(value: Any) -> bool:
    """Проверяет, вернул ли пользователь back/exit."""
    return value in (BACK, EXIT)


def _early_return(value: Any) -> tuple[dict, Any]:
    """Формирует ответ для back/exit."""
    return {"intent": value}, {}


# ─── Обработчики интентов ────────────────────────────────────────────

def _handle_forecast(
    catalog: dict[str, dict],
    history: dict,
) -> tuple[dict, dict]:
    """Обработчик forecast_purchase."""
    sku = _ask_sku(catalog)
    if _is_back_or_exit(sku):
        return _early_return(sku)
    if sku is None:
        return {"intent": "unknown"}, {}

    period = _ask_period()
    if _is_back_or_exit(period):
        return _early_return(period)
    if period is None:
        return {"intent": "forecast_purchase", "sku": sku}, {}

    result = forecast_demand(history, sku, period, {"catalog": catalog})
    return (
        {"intent": "forecast_purchase", "sku": sku, "period_days": period},
        result,
    )


def _handle_reorder_list(
    catalog: dict[str, dict],
    history: dict,
) -> tuple[dict, list[dict]]:
    """Обработчик reorder_list."""
    period = _ask_period()
    if _is_back_or_exit(period):
        return _early_return(period)
    if period is None:
        period = 30

    items = []
    for sku, item in catalog.items():
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
    return {"intent": "reorder_list", "period_days": period}, items


def _handle_budget(
    catalog: dict[str, dict],
    history: dict,
) -> tuple[dict, list[dict]]:
    """Обработчик budget."""
    period = _ask_period()
    if _is_back_or_exit(period):
        return _early_return(period)
    if period is None:
        period = 30

    budget = _ask_budget()
    if _is_back_or_exit(budget):
        return _early_return(budget)

    items = []
    for sku, item in catalog.items():
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

    params = {
        "intent": "budget",
        "period_days": period,
        "budget_limit": budget,
    }
    return params, items


def _handle_deficit_risk(
    catalog: dict[str, dict],
    history: dict,
) -> tuple[dict, list[dict]]:
    """Обработчик deficit_risk."""
    period = _ask_period()
    if _is_back_or_exit(period):
        return _early_return(period)
    if period is None:
        period = 30

    as_of = history.get("as_of", "")
    items = []

    for sku, item in catalog.items():
        if sku not in history.get("weekly_consumption", {}):
            continue

        try:
            r = forecast_demand(history, sku, period, {"catalog": catalog})
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
            })

    items.sort(key=lambda x: x["stockout_date"] or "9999")
    return {"intent": "deficit_risk", "period_days": period}, items


def _handle_stock_check(
    catalog: dict[str, dict],
    history: dict,
) -> tuple[dict, dict]:
    """Обработчик stock_check."""
    sku = _ask_sku(catalog)
    if _is_back_or_exit(sku):
        return _early_return(sku)
    if sku is None:
        return {"intent": "unknown"}, {}

    result = forecast_demand(history, sku, 30, {"catalog": catalog})
    return {"intent": "stock_check", "sku": sku}, result


# ─── Карта обработчиков ─────────────────────────────────────────────

HANDLERS: dict[str, Callable] = {
    "forecast_purchase": _handle_forecast,
    "reorder_list": _handle_reorder_list,
    "budget": _handle_budget,
    "deficit_risk": _handle_deficit_risk,
    "stock_check": _handle_stock_check,
}


# ─── Главная функция ─────────────────────────────────────────────────

def run_menu(
    catalog: dict[str, dict],
    history: dict,
) -> tuple[dict, Any]:
    """Запускает интерактивное меню."""
    while True:
        print("\n" + "=" * 50)
        print("Главное меню:")
        print("=" * 50)

        options = [
            (key, label, intent)
            for key, intent, label in MENU_ITEMS
        ]
        intent = _pick_from_list(
            "Действие:", options,
            allow_back=False,
            allow_exit=False,
        )

        if intent is None or intent == EXIT or intent == "exit":
            print("\nВыход из меню.")
            return {"intent": "exit"}, None

        if intent == BACK:
            continue

        handler = HANDLERS.get(intent)
        if handler is None:
            return {"intent": "unknown"}, None

        params, data = handler(catalog, history)

        if params.get("intent") == BACK:
            continue
        if params.get("intent") == EXIT:
            print("\nВыход из меню.")
            return {"intent": "exit"}, None

        return params, data