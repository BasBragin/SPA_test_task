"""CLI для проверки answer_question.

Использование:
    # Один вопрос вручную
    python scripts/check_question.py "Сколько масла закупить на квартал?"

    # Несколько вопросов через --text
    python scripts/check_question.py --text "вопрос 1" --text "вопрос 2"

    # Свой JSON с вопросами
    python scripts/check_question.py --json my_questions.json

    # Стандартный dataset_part3.json (15 вопросов из ТЗ)
    python scripts/check_question.py --dataset

    # Категориальное меню (fallback)
    python scripts/check_question.py --menu

    # Интерактивный чат
    python scripts/check_question.py --interactive

    # JSON-вывод
    python scripts/check_question.py --dataset --output-format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.part3.answer import answer_question
from src.part3.llm import llm_available
from src.part3.menu import run_menu

# ─── Загрузка данных ─────────────────────────────────────────────────

def load_catalog(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["sku"]: item for item in items}


def load_history(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def questions_from_json(path: Path) -> list[str]:
    """
    Загружает вопросы из JSON.

    Поддерживает:
    - список строк: ["вопрос 1", "вопрос 2"]
    - список dict: [{"text": "..."}, ...]
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise TypeError(f"Ожидался список в {path}")

    questions = []
    for i, item in enumerate(data):
        if isinstance(item, str):
            questions.append(item)
        elif isinstance(item, dict) and "text" in item:
            questions.append(item["text"])
        else:
            raise TypeError(f"Элемент {i}: ожидался str или dict с 'text'")
    return questions


# ─── Вывод ────────────────────────────────────────────────────────────

def print_answer(
    question: str,
    params: dict,
    confidence: float,
    answer: str,
    show_full: bool = True,
) -> None:
    """Печатает ответ в читаемом виде."""
    print("=" * 70)
    print(f"Вопрос: {question}")
    print(f"Интент: {params.get('intent')}, "
          f"SKU: {params.get('sku')}, "
          f"Период: {params.get('period_days')}, "
          f"Уверенность: {confidence:.2f}")
    print("-" * 70)

    if show_full:
        print(answer)
    else:
        print(answer[:500] + ("..." if len(answer) > 500 else ""))

    print()


def print_json(rows: list[dict]) -> None:
    print(json.dumps(rows, ensure_ascii=False, indent=2))


# ─── Режимы работы ───────────────────────────────────────────────────

def run_questions(
    questions: list[str],
    catalog: dict[str, dict],
    history: dict,
    use_llm: bool,
    output_format: str,
    show_full: bool,
) -> int:
    """Прогоняет список вопросов."""
    context = {
        "catalog": catalog,
        "history": history,
        "use_llm": use_llm,
    }

    rows = []
    for q in questions:
        params, confidence, answer = answer_question(q, context)
        rows.append({
            "question": q,
            "intent": params.get("intent"),
            "sku": params.get("sku"),
            "period_days": params.get("period_days"),
            "confidence": confidence,
            "answer": answer,
        })

    if output_format == "json":
        print_json(rows)
    else:
        for row in rows:
            print_answer(
                row["question"],
                {
                    "intent": row["intent"],
                    "sku": row["sku"],
                    "period_days": row["period_days"],
                },
                row["confidence"],
                row["answer"],
                show_full=show_full,
            )
    return 0


def run_interactive(
    catalog: dict[str, dict],
    history: dict,
    use_llm: bool,
) -> int:
    """Интерактивный чат: пользователь вводит вопросы с клавиатуры."""
    context = {
        "catalog": catalog,
        "history": history,
        "use_llm": use_llm,
    }

    print("\n" + "=" * 60)
    print("Чат с ИИ-помощником")
    print("Введите 'exit' или 'q' для выхода.")
    print("=" * 60 + "\n")

    while True:
        try:
            question = input("Ваш вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            return 0

        if not question:
            continue
        if question.lower() in ("exit", "q", "quit"):
            print("Выход.")
            return 0

        params, confidence, answer = answer_question(question, context)
        print()
        print(answer)
        print()
        print(f"[Интент: {params.get('intent')}, "
              f"уверенность: {confidence:.2f}]")
        print()


def run_menu_mode(catalog: dict[str, dict], history: dict) -> int:
    """Категориальное меню (fallback без LLM)."""
    from src.part3 import formatter

    params, data = run_menu(catalog, history)

    if params.get("intent") == "exit":
        return 0

    if not data:
        print("Нет данных для отображения.")
        return 0

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

    return 0


# ─── CLI ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_question",
        description="CLI для проверки answer_question.",
    )

    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "question_positional",
        nargs="?",
        help="Один вопрос (позиционный аргумент).",
    )
    source.add_argument(
        "--text",
        action="append",
        default=[],
        help="Вопрос (можно повторять).",
    )
    source.add_argument(
        "--json",
        type=Path,
        help="JSON-файл со списком вопросов.",
    )
    source.add_argument(
        "--dataset",
        action="store_true",
        help="Использовать dataset_part3.json (15 вопросов из ТЗ).",
    )
    source.add_argument(
        "--menu",
        action="store_true",
        help="Категориальное меню (fallback без LLM).",
    )
    source.add_argument(
        "--interactive",
        action="store_true",
        help="Интерактивный чат.",
    )

    parser.add_argument(
        "--catalog",
        type=Path,
        default=PROJECT_ROOT / "catalog.json",
        help="Путь к catalog.json.",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=PROJECT_ROOT / "src" / "part2" / "dataset_part2.json",
        help="Путь к dataset_part2.json.",
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Отключить LLM (использовать только rules).",
    )
    parser.add_argument(
        "--output-format",
        choices=["table", "json"],
        default="table",
        help="Формат вывода.",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help="Сокращённый вывод (первые 500 символов).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.catalog.exists():
        print(f"Catalog не найден: {args.catalog}", file=sys.stderr)
        return 1
    if not args.history.exists():
        print(f"History не найден: {args.history}", file=sys.stderr)
        return 1

    catalog = load_catalog(args.catalog)
    history = load_history(args.history)

    use_llm = not args.no_llm

    if use_llm and not llm_available():
        print(
            "GIGACHAT_CREDENTIALS не задан — работаю в fallback-режиме.",
            file=sys.stderr,
        )
        use_llm = False

    if args.menu:
        return run_menu_mode(catalog, history)

    if args.interactive:
        return run_interactive(catalog, history, use_llm)

    if args.dataset:
        dataset_path = PROJECT_ROOT / "src" / "part3" / "dataset_part3.json"
        if not dataset_path.exists():
            print(f"Dataset не найден: {dataset_path}", file=sys.stderr)
            return 1
        questions = questions_from_json(dataset_path)
    elif args.json:
        if not args.json.exists():
            print(f"JSON не найден: {args.json}", file=sys.stderr)
            return 1
        questions = questions_from_json(args.json)
    elif args.text:
        questions = args.text
    elif args.question_positional:
        questions = [args.question_positional]
    else:
        parser.print_help()
        return 1

    return run_questions(
        questions=questions,
        catalog=catalog,
        history=history,
        use_llm=use_llm,
        output_format=args.output_format,
        show_full=not args.short,
    )


if __name__ == "__main__":
    sys.exit(main())