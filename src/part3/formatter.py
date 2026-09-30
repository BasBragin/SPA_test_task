"""Форматирование ответов для пользователя.

Принимает результат forecast_demand и превращает его в 
человекочитаемый текст: таблицы, пояснения, уточнения.
"""

from __future__ import annotations

from typing import Any

# ─── Утилиты ─────────────────────────────────────────────────────────

def _hr(width: int = 46) -> str:
    return "─" * width


def _row(label: str, value: str, label_width: int = 24, value_width: int = 20) -> str:
    return f"{label:<{label_width}} {value:<{value_width}}"


# ─── Форматтеры интентов ─────────────────────────────────────────────

def format_forecast_purchase(
    sku: str,
    catalog_item: dict,
    result: dict[str, Any],
    horizon_days: int,
) -> str:
    """Таблица прогноза закупки для одного SKU."""
    unit = catalog_item["unit"]

    lines = [
        f"Прогноз закупки: {sku} — {catalog_item['name']}",
        f"Период: {horizon_days} дней",
        "",
        _row("Показатель", "Значение"),
        _hr(),
        _row("Средний дневной расход", f"{result['avg_daily_consumption']:.2f} {unit}"),
        _row("Прогноз потребности", f"{result['forecast_demand']:.2f} {unit}"),
        _row("Текущий остаток", f"{result['current_stock']:.2f} {unit}"),
        _row("В пути", f"{result['incoming_qty']:.2f} {unit}"),
        _row("Страховой запас", f"{result['safety_stock']:.2f} {unit}"),
        _row("Точка заказа", f"{result['reorder_point']:.2f} {unit}"),
        _hr(),
        _row("Рекомендуемая закупка", f"{result['recommended_qty']:.2f} {unit}"),
        _row("Оценка стоимости", f"{result['estimated_cost']:,.2f} ₽".replace(",", " ")),
    ]

    if result["stockout_date"]:
        lines.append(_row("Ожидаемое истощение", result["stockout_date"]))

    lines.append(_row("Уверенность", f"{result['confidence']:.2f}"))

    lines.append("")
    lines.append("Обоснование:")
    lines.append(result["explanation"])

    return "\n".join(lines)


def format_what_if(
    sku: str,
    catalog_item: dict,
    result: dict[str, Any],
    horizon_days: int,
    multiplier: float,
    adjusted_confidence: float,
) -> str:
    """Таблица прогноза закупки с what-if сценарием."""
    unit = catalog_item["unit"]
    change_pct = (multiplier - 1) * 100

    lines = [
        f"Прогноз закупки (WHAT-IF): {sku} — {catalog_item['name']}",
        f"Период: {horizon_days} дней",
        f"Сценарий: изменение на {change_pct:+.0f}% (множитель ×{multiplier:.2f})",
        "",
        "ВНИМАНИЕ: это ПРЕДПОЛОЖЕНИЕ, а не реальный прогноз.",
        "Расчёт основан на допущении сценария.",
        "Рекомендуется перепроверить исходные данные.",
        "",
        _row("Показатель", "Значение"),
        _hr(),
        _row("Средний дневной расход", f"{result['avg_daily_consumption']:.2f} {unit}"),
        _row("Прогноз потребности", f"{result['forecast_demand']:.2f} {unit}"),
        _row("Текущий остаток", f"{result['current_stock']:.2f} {unit}"),
        _row("В пути", f"{result['incoming_qty']:.2f} {unit}"),
        _row("Страховой запас", f"{result['safety_stock']:.2f} {unit}"),
        _row("Точка заказа", f"{result['reorder_point']:.2f} {unit}"),
        _hr(),
        _row("Рекомендуемая закупка", f"{result['recommended_qty']:.2f} {unit}"),
        _row("Оценка стоимости", f"{result['estimated_cost']:,.2f} ₽".replace(",", " ")),
    ]

    if result["stockout_date"]:
        lines.append(_row("Ожидаемое истощение", result["stockout_date"]))

    lines.append(_row(
        "Уверенность",
        f"{adjusted_confidence:.2f} (понижена из-за сценария)",
    ))

    lines.append("")
    lines.append("Данные основаны на предположении — перепроверьте.")

    return "\n".join(lines)


def format_reorder_list(items: list[dict[str, Any]]) -> str:
    """Список SKU, которые нужно заказать."""
    if not items:
        return "Все товары в норме. Срочных заказов нет."

    lines = [
        "Товары к заказу:",
        "",
        f"{'SKU':<12} {'Товар':<28} {'Закупка':<12} {'Стоимость':<14} {'Истощение':<12}",
        _hr(80),
    ]

    total_cost = 0.0
    for item in items:
        cost = item.get("cost", 0.0)
        total_cost += cost
        lines.append(
            f"{item['sku']:<12} "
            f"{item['name'][:26]:<28} "
            f"{item['recommended_qty']:>6.2f} {item['unit']:<4} "
            f"{cost:>12,.2f} ₽ "
            f"{item.get('stockout_date') or '—':<12}".replace(",", " ")
        )

    lines.append(_hr(80))
    lines.append(f"Итого: {total_cost:,.2f} ₽".replace(",", " "))

    return "\n".join(lines)


def format_budget(
    items: list[dict[str, Any]],
    period_days: int,
    budget_limit: float | None = None,
) -> str:
    """Бюджет закупок на период."""
    if not items:
        return f"На период {period_days} дней закупки не требуются."

    total = sum(item.get("cost", 0.0) for item in items)

    lines = [
        f"Бюджет закупок на {period_days} дней",
        "",
        f"{'SKU':<12} {'Товар':<28} {'Закупка':<12} {'Стоимость':<14}",
        _hr(70),
    ]

    for item in items:
        lines.append(
            f"{item['sku']:<12} "
            f"{item['name'][:26]:<28} "
            f"{item['recommended_qty']:>6.2f} {item['unit']:<4} "
            f"{item.get('cost', 0.0):>12,.2f} ₽".replace(",", " ")
        )

    lines.append(_hr(70))
    lines.append(f"Итого: {total:,.2f} ₽".replace(",", " "))

    if budget_limit is not None:
        lines.append(f"Лимит: {budget_limit:,.2f} ₽".replace(",", " "))
        if total > budget_limit:
            lines.append(f"Превышение: {total - budget_limit:,.2f} ₽".replace(",", " "))
        else:
            lines.append(f"Остаток: {budget_limit - total:,.2f} ₽".replace(",", " "))

    return "\n".join(lines)


def format_deficit_risk(
    items: list[dict[str, Any]],
    location: str | None = None,
) -> str:
    """Список SKU в риске дефицита."""
    if not items:
        loc = f" в {location}" if location else ""
        return f"Товаров с риском дефицита{loc} не обнаружено."

    header = "Риск дефицита"
    if location:
        header += f": {location}"

    lines = [
        header,
        "",
        (
            f"{'SKU':<12} {'Товар':<28} {'Истощение':<12} {'Дней':<6} "
            f"{'Закупка':<12} {'Стоимость':<14}"
        ),
        _hr(100),
    ]

    for item in items:
        cost = item.get("cost", 0.0)
        lines.append(
            f"{item['sku']:<12} "
            f"{item['name'][:26]:<28} "
            f"{item.get('stockout_date') or '—':<12} "
            f"{item.get('days_left', '—')!s:<6} "
            f"{item['recommended_qty']:>6.2f} {item['unit']:<4} "
            f"{cost:>12,.2f} ₽".replace(",", " ")
        )

    if location:
        lines.append("")
        lines.append(
            "Примечание: в данных нет разбивки по филиалам — "
            "показан общий остаток. Для отчёта по конкретному "
            f"филиалу ({location}) нужны данные с разбивкой по локациям."
        )

    return "\n".join(lines)


def format_expiry_risk(items: list[dict[str, Any]]) -> str:
    """Список SKU в риске списания."""
    if not items:
        return (
            "Данных о сроках годности партий нет. "
            "Рекомендую добавить поле `expiry_date` в учётную систему."
        )

    lines = [
        "Риск списания (истекает срок годности):",
        "",
        f"{'SKU':<12} {'Товар':<28} {'Партия':<18} {'Истекает':<12}",
        _hr(72),
    ]
    for item in items:
        lines.append(
            f"{item['sku']:<12} "
            f"{item['name'][:26]:<28} "
            f"{item.get('batch', '—'):<18} "
            f"{item.get('expiry_date', '—'):<12}"
        )
    return "\n".join(lines)


def format_price_dynamics(
    sku: str | None,
    catalog_item: dict | None,
    old_price: float | None,
    new_price: float | None,
) -> str:
    """Динамика цены."""
    if catalog_item is None:
        return (
            "Данных о динамике цен нет. "
            "В каталоге только текущая цена. "
            "Рекомендую добавить историю цен."
        )

    if old_price is None or new_price is None:
        return (
            f"Для {sku} ({catalog_item['name']}) доступна только текущая цена: "
            f"{catalog_item['price']:.2f} ₽. Истории цен нет."
        )

    delta = new_price - old_price
    pct = (delta / old_price * 100) if old_price else 0.0

    lines = [
        f"Динамика цены: {sku} — {catalog_item['name']}",
        "",
        f"Было:  {old_price:,.2f} ₽".replace(",", " "),
        f"Стало: {new_price:,.2f} ₽".replace(",", " "),
        f"Изменение: {delta:+,.2f} ₽ ({pct:+.1f}%)".replace(",", " "),
    ]
    return "\n".join(lines)


def format_stock_check(
    sku: str,
    catalog_item: dict,
    result: dict[str, Any],
) -> str:
    """Остаток товара на складе."""
    unit = catalog_item["unit"]
    available = result["current_stock"] + result["incoming_qty"]
    avg = result["avg_daily_consumption"]

    lines = [
        f"Остаток: {sku} — {catalog_item['name']}",
        "",
        _row("Текущий остаток", f"{result['current_stock']:.2f} {unit}"),
        _row("В пути", f"{result['incoming_qty']:.2f} {unit}"),
        _row("Итого доступно", f"{available:.2f} {unit}"),
        "",
        _row("Средний дневной расход", f"{avg:.2f} {unit}/день"),
    ]

    if avg > 0:
        days_left = available / avg
        lines.append(_row("Хватит примерно на", f"{days_left:.0f} дней"))

    return "\n".join(lines)


def format_explain(sku_trends: list[dict[str, Any]]) -> str:
    """Объяснение динамики: что выросло и возможные причины."""
    lines = ["Объяснение динамики плана закупок:", ""]

    if not sku_trends:
        lines.append("Данных для анализа динамики нет.")
        return "\n".join(lines)

    lines.append(f"{'SKU':<12} {'Товар':<28} {'Было':<10} {'Стало':<10} {'Δ%':<10}")
    lines.append("─" * 72)

    for t in sku_trends:
        lines.append(
            f"{t['sku']:<12} "
            f"{t['name'][:26]:<28} "
            f"{t['first_week']:>6.2f}    "
            f"{t['last_week']:>6.2f}    "
            f"{t['change_pct']:>+6.1f}%"
        )

    lines.append("")
    lines.append("Возможные причины роста:")
    lines.append("- рост числа клиентов / броней;")
    lines.append("- увеличение загрузки мастеров;")
    lines.append("- маркетинговые акции / скидки;")
    lines.append("- сезонный фактор.")

    return "\n".join(lines)


# ─── Специальные ответы ─────────────────────────────────────────────

def format_unknown() -> str:
    """Ответ для вопросов вне домена задачи."""
    return (
        "К сожалению, этот вопрос вне моей компетенции.\n"
        "Я помогаю со складским учётом и планированием закупок.\n"
        "\n"
        "Что я умею:\n"
        "- Прогноз закупки (сколько и когда заказать)\n"
        "- Список товаров к заказу\n"
        "- Бюджет закупок\n"
        "- Риск дефицита и списания\n"
        "- Динамика цен\n"
        "- Остаток товара"
    )


def format_clarify(missing: str, options: list[str] | None = None) -> str:
    """Уточняющий вопрос."""
    text = f"Уточните, пожалуйста: {missing}"

    if options:
        text += "\n\nВарианты:\n" + "\n".join(f"- {opt}" for opt in options)

    return text