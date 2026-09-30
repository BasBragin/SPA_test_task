"""Единая точка входа для SPA Test Task.

Использование:
    # Прогон всех частей
    python main.py --all

    # Отдельные части
    python main.py --part1               # нормализация M1–M8
    python main.py --part2               # прогноз для 3 SKU × 2 горизонта
    python main.py --part3               # прогон 15 вопросов

    # Интерактивные режимы
    python main.py --chat                # чат с ИИ
    python main.py --menu                # категориальное меню (fallback)

    # Обёртки над CLI-скриптами
    python main.py --check-normalize --dataset
    python main.py --check-forecast --all --horizons 30 90
    python main.py --check-question --dataset
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.part1.part1_normalize import load_catalog as load_catalog_p1
from src.part1.part1_normalize import normalize_movement
from src.part2.forecast import forecast_demand
from src.part3.answer import answer_question
from src.part3.menu import run_menu

# ─── Общие загрузчики ────────────────────────────────────────────────

def _load_catalog() -> dict[str, dict]:
    """Загружает каталог для Частей 2 и 3."""
    path = PROJECT_ROOT / "catalog.json"
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["sku"]: item for item in items}


def _load_history() -> dict:
    """Загружает dataset_part2.json."""
    path = PROJECT_ROOT / "src" / "part2" / "dataset_part2.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_movements() -> list[dict]:
    """Загружает dataset_part1.json (M1–M8)."""
    path = PROJECT_ROOT / "src" / "part1" / "dataset_part1.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_questions() -> list[str]:
    """Загружает dataset_part3.json (15 вопросов)."""
    path = PROJECT_ROOT / "src" / "part3" / "dataset_part3.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data[0], str):
        return data
    return [item["text"] for item in data]


# ─── Часть 1 ─────────────────────────────────────────────────────────

def run_part1() -> None:
    """Прогон нормализации M1–M8."""
    print("\n" + "=" * 70)
    print("Часть 1: нормализация записей движения")
    print("=" * 70)

    catalog = load_catalog_p1()
    records = _load_movements()

    for record in records:
        result = normalize_movement(record["text"], catalog)
        print(f"\n{record['id']}: {record['text']}")
        print(f"  → {result}")


# ─── Часть 2 ─────────────────────────────────────────────────────────

def run_part2() -> None:
    """Прогноз для 3 SKU × 2 горизонта."""
    print("\n" + "=" * 70)
    print("Часть 2: прогноз потребности и рекомендация закупки")
    print("=" * 70)

    catalog = _load_catalog()
    history = _load_history()

    skus = list(history["weekly_consumption"].keys())
    horizons = [30, 90]

    for sku in skus:
        for horizon in horizons:
            result = forecast_demand(history, sku, horizon, {"catalog": catalog})
            print(f"\n{sku} — {horizon} дней:")
            print(f"  Средний дневной расход: {result['avg_daily_consumption']:.4f}")
            print(f"  Прогноз потребности:    {result['forecast_demand']:.4f}")
            print(f"  Рекомендуемая закупка:  {result['recommended_qty']:.2f}")
            print(f"  Стоимость:              {result['estimated_cost']:,.2f} ₽".replace(",", " "))
            print(f"  Истощение:              {result['stockout_date'] or 'не прогнозируется'}")
            print(f"  Уверенность:            {result['confidence']:.2f}")


# ─── Часть 3 ─────────────────────────────────────────────────────────

def run_part3() -> None:
    """Прогон 15 вопросов."""
    print("\n" + "=" * 70)
    print("Часть 3: разбор вопросов пользователя")
    print("=" * 70)

    catalog = _load_catalog()
    history = _load_history()
    questions = _load_questions()

    context = {"catalog": catalog, "history": history}

    for i, q in enumerate(questions, 1):
        params, confidence, answer = answer_question(q, context)
        print(f"\n{'-' * 70}")
        print(f"{i}. {q}")
        print(f"Интент: {params.get('intent')}, "
              f"уверенность: {confidence:.2f}")
        print("-" * 70)
        print(answer)


# ─── Интерактивные режимы ────────────────────────────────────────────

def run_chat() -> None:
    """Интерактивный чат с ИИ."""
    catalog = _load_catalog()
    history = _load_history()
    context = {"catalog": catalog, "history": history}

    print("\n" + "=" * 60)
    print("Чат с ИИ-помощником")
    print("Введите 'exit' или 'q' для выхода.")
    print("=" * 60 + "\n")

    while True:
        try:
            question = input("Ваш вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            return

        if not question:
            continue
        if question.lower() in ("exit", "q", "quit"):
            print("Выход.")
            return

        params, confidence, answer = answer_question(question, context)
        print()
        print(answer)
        print()
        print(f"[Интент: {params.get('intent')}, "
              f"уверенность: {confidence:.2f}]")
        print()


def run_menu_mode() -> None:
    """Категориальное меню (fallback без LLM)."""
    from src.part3 import formatter

    catalog = _load_catalog()
    history = _load_history()

    params, data = run_menu(catalog, history)

    if params.get("intent") == "exit":
        return

    if not data:
        print("Нет данных для отображения.")
        return

    intent = params.get("intent")

    if intent == "forecast_purchase" and isinstance(data, dict):
        sku = params["sku"]
        period = params["period_days"]
        print(formatter.format_forecast_purchase(
            sku, catalog[sku], data, period,
        ))
    elif intent == "reorder_list" and isinstance(data, list):
        print(formatter.format_reorder_list(data))
    elif intent == "budget" and isinstance(data, list):
        print(formatter.format_budget(
            data, params["period_days"], params.get("budget_limit"),
        ))
    elif intent == "deficit_risk" and isinstance(data, list):
        print(formatter.format_deficit_risk(data, params.get("location")))
    elif intent == "stock_check" and isinstance(data, dict):
        sku = params["sku"]
        print(formatter.format_stock_check(sku, catalog[sku], data))
    else:
        print(data)


# ─── Обёртки над CLI-скриптами ──────────────────────────────────────

def run_cli_script(script_name: str, script_args: list[str]) -> int:
    """Запускает CLI-скрипт из scripts/ с переданными аргументами."""
    script_path = PROJECT_ROOT / "scripts" / script_name
    if not script_path.exists():
        print(f"Скрипт не найден: {script_path}", file=sys.stderr)
        return 1

    cmd = [sys.executable, str(script_path), *script_args]
    return subprocess.call(cmd)


# ─── CLI ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main",
        description="SPA Test Task — единая точка входа.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Основные режимы
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--part1", action="store_true",
        help="Прогон нормализации M1–M8.",
    )
    modes.add_argument(
        "--part2", action="store_true",
        help="Прогноз для 3 SKU × 2 горизонта.",
    )
    modes.add_argument(
        "--part3", action="store_true",
        help="Прогон 15 вопросов.",
    )
    modes.add_argument(
        "--all", action="store_true",
        help="Прогон всех трёх частей.",
    )
    modes.add_argument(
        "--chat", action="store_true",
        help="Интерактивный чат с ИИ.",
    )
    modes.add_argument(
        "--menu", action="store_true",
        help="Категориальное меню (fallback).",
    )

    # Обёртки над CLI-скриптами
    modes.add_argument(
        "--check-normalize", action="store_true",
        help="CLI для Части 1 (см. scripts/check_normalize.py).",
    )
    modes.add_argument(
        "--check-forecast", action="store_true",
        help="CLI для Части 2 (см. scripts/check_forecast.py).",
    )
    modes.add_argument(
        "--check-question", action="store_true",
        help="CLI для Части 3 (см. scripts/check_question.py).",
    )

    # Флаги для проброса аргументов в CLI-скрипты
    parser.add_argument(
        "cli_args", nargs="*",
        help="Аргументы для CLI-скрипта (после --check-*).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Основные режимы
    if args.part1:
        run_part1()
        return 0
    if args.part2:
        run_part2()
        return 0
    if args.part3:
        run_part3()
        return 0
    if args.all:
        run_part1()
        run_part2()
        run_part3()
        return 0
    if args.chat:
        run_chat()
        return 0
    if args.menu:
        run_menu_mode()
        return 0

    # Обёртки над CLI
    if args.check_normalize:
        return run_cli_script("check_normalize.py", args.cli_args)
    if args.check_forecast:
        return run_cli_script("check_forecast.py", args.cli_args)
    if args.check_question:
        return run_cli_script("check_question.py", args.cli_args)

    # Ничего не выбрано
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())