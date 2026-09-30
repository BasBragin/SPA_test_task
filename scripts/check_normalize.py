"""CLI для проверки normalize_movement.

Использование:
    # Одна строка вручную
    python scripts/check_normalize.py "05.03.2026 MS-01 приход OIL-001 1 л"

    # Несколько строк через --text (можно повторять)
    python scripts/check_normalize.py --text "строка 1" --text "строка 2"

    # Свой JSON-файл со списком записей
    python scripts/check_normalize.py --json my_records.json

    # Стандартный dataset из задания
    python scripts/check_normalize.py --dataset

    # Вывод в JSON (для машинной обработки)
    python scripts/check_normalize.py --json my_records.json --output-format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы импорт src работал
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.part1.part1_normalize import load_catalog, normalize_movement

FIELDS = ["date", "sku", "location", "operation", "qty", "unit", "batch", "doc_no"]


# ─── Вывод ────────────────────────────────────────────────────────────

def print_table(rows: list[dict]) -> None:
    """Печатает список результатов в виде таблицы."""
    header = f"{'ID':<6} " + " ".join(f"{f:<13}" for f in FIELDS)
    print(header)
    print("-" * len(header))

    for row in rows:
        rid = row.get("id", "")
        values = [str(row.get(f)) for f in FIELDS]
        print(f"{rid:<6} " + " ".join(f"{v:<13}" for v in values))


def print_json(rows: list[dict]) -> None:
    """Печатает результаты в JSON."""
    print(json.dumps(rows, ensure_ascii=False, indent=2))


# ─── Загрузка входных данных ─────────────────────────────────────────

def records_from_texts(texts: list[str]) -> list[dict]:
    """Из списка строк делает список записей с id."""
    return [
        {"id": f"T{i + 1}", "text": t}
        for i, t in enumerate(texts)
    ]


def records_from_json(path: Path) -> list[dict]:
    """Загружает записи из JSON-файла.

    Ожидаемый формат: [{"id": "...", "text": "..."}, ...]
    Или просто список строк: ["строка 1", "строка 2"]
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise TypeError(f"Ожидался список в {path}, получено {type(data).__name__}")

    records = []
    for i, item in enumerate(data):
        if isinstance(item, str):
            records.append({"id": f"X{i + 1}", "text": item})
        elif isinstance(item, dict) and "text" in item:
            records.append({
                "id": item.get("id", f"X{i + 1}"),
                "text": item["text"],
            })
        else:
            raise TypeError(
                f"Элемент {i} в {path}: ожидался str или dict с 'text', "
                f"получено {type(item).__name__}"
            )
    return records


def records_from_dataset() -> list[dict]:
    """Загружает стандартный dataset_part1.json из репозитория."""
    path = PROJECT_ROOT / "src" / "part1" / "dataset_part1.json"
    return records_from_json(path)


# ─── Основная логика ─────────────────────────────────────────────────

def run(records: list[dict], output_format: str = "table") -> int:
    """Прогоняет записи через normalize_movement и печатает результат.

    Возвращает 0 при успехе, 1 при ошибке.
    """
    catalog = load_catalog()
    results = []

    for record in records:
        try:
            parsed = normalize_movement(record["text"], catalog)
        except (ValueError, KeyError, TypeError) as e:
            print(f"Ошибка на {record['id']}: {e}", file=sys.stderr)
            return 1

        results.append({"id": record["id"], "text": record["text"], **parsed})

    if output_format == "json":
        print_json(results)
    else:
        print_table(results)

    return 0


# ─── CLI ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_normalize",
        description="Проверка normalize_movement на строке, JSON или dataset.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "text_positional",
        nargs="?",
        help="Одна строка для парсинга (позиционный аргумент).",
    )
    source.add_argument(
        "--text",
        action="append",
        default=[],
        help="Строка для парсинга (можно указывать несколько раз).",
    )
    source.add_argument(
        "--json",
        type=Path,
        help="Путь к JSON-файлу со списком записей.",
    )
    source.add_argument(
        "--dataset",
        action="store_true",
        help="Использовать стандартный dataset_part1.json.",
    )

    parser.add_argument(
        "--output-format",
        choices=["table", "json"],
        default="table",
        help="Формат вывода (по умолчанию table).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    records: list[dict] = []

    if args.dataset:
        records = records_from_dataset()
    elif args.json:
        if not args.json.exists():
            print(f"Файл не найден: {args.json}", file=sys.stderr)
            return 1
        records = records_from_json(args.json)
    elif args.text:
        records = records_from_texts(args.text)
    elif args.text_positional:
        records = records_from_texts([args.text_positional])
    else:
        parser.print_help()
        return 1

    return run(records, output_format=args.output_format)


if __name__ == "__main__":
    sys.exit(main())