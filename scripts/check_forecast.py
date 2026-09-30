"""CLI для проверки forecast_demand.

Использование:
    # Один SKU на 30 дней
    python scripts/check_forecast.py --sku OIL-001 --horizon 30

    # Все SKU из dataset на 90 дней
    python scripts/check_forecast.py --all --horizon 90

    # Все SKU на 30 и 90 дней (сводная таблица)
    python scripts/check_forecast.py --all --horizons 30 90

    # JSON-вывод
    python scripts/check_forecast.py --all --horizons 30 90 --output-format json

    # Свой dataset
    python scripts/check_forecast.py --dataset my_data.json --sku OIL-001 --horizon 30
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.part2.forecast import forecast_demand

# ─── Вывод ────────────────────────────────────────────────────────────

SUMMARY_FIELDS = [
    "sku", "horizon",
    "avg_daily_consumption", "forecast_demand",
    "current_stock", "incoming_qty",
    "safety_stock", "reorder_point",
    "recommended_qty", "estimated_cost",
    "stockout_date", "confidence",
]


def print_summary_table(rows: list[dict]) -> None:
    """Печатает сводную таблицу по всем SKU × горизонтам."""
    header = " ".join(f"{f:<22}" for f in SUMMARY_FIELDS)
    print(header)
    print("-" * len(header))

    for row in rows:
        values = []
        for f in SUMMARY_FIELDS:
            v = row.get(f, "")
            if isinstance(v, float):
                values.append(f"{v:<22.2f}")
            else:
                values.append(f"{v!s:<22}")
        print(" ".join(values))


def print_explanations(rows: list[dict]) -> None:
    """Печатает полный explanation для каждого кейса."""
    for row in rows:
        print(f"\n{'=' * 70}")
        print(f"SKU: {row['sku']}, горизонт: {row['horizon']} дней")
        print("=" * 70)
        print(row["explanation"])


def print_json(rows: list[dict]) -> None:
    print(json.dumps(rows, ensure_ascii=False, indent=2))


# ─── Загрузка данных ─────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_catalog(path: Path) -> dict[str, dict]:
    items = load_json(path)
    if isinstance(items, dict):
        return items
    return {item["sku"]: item for item in items}


# ─── Основная логика ─────────────────────────────────────────────────

def run(
    history: dict,
    catalog: dict,
    skus: list[str],
    horizons: list[int],
    output_format: str,
    show_explanation: bool,
) -> int:
    """Прогоняет forecast_demand для каждого SKU × горизонта."""
    rows = []

    for sku in skus:
        for h in horizons:
            try:
                result = forecast_demand(history, sku, h, {"catalog": catalog})
            except Exception as e:  # noqa: BLE001
                print(f"Ошибка на {sku} × {h} дней: {e}", file=sys.stderr)
                return 1

            rows.append({"sku": sku, "horizon": h, **result})

    if output_format == "json":
        print_json(rows)
    else:
        print_summary_table(rows)
        if show_explanation:
            print_explanations(rows)

    return 0


# ─── CLI ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_forecast",
        description="Проверка forecast_demand на реальных данных или своём dataset.",
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "src" / "part2" / "dataset_part2.json",
        help="Путь к dataset_part2.json (по умолчанию — из репозитория).",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=PROJECT_ROOT / "catalog.json",
        help="Путь к catalog.json (по умолчанию — из репозитория).",
    )

    sku_group = parser.add_mutually_exclusive_group(required=True)
    sku_group.add_argument("--sku", help="Один SKU для прогноза.")
    sku_group.add_argument("--all", action="store_true", help="Все SKU из dataset.")

    parser.add_argument(
        "--horizon", type=int, default=30,
        help="Горизонт в днях (используется, если не указан --horizons).",
    )
    parser.add_argument(
        "--horizons", type=int, nargs="+", default=None,
        help="Несколько горизонтов (например, --horizons 30 90).",
    )

    parser.add_argument(
        "--output-format",
        choices=["table", "json"],
        default="table",
    )
    parser.add_argument(
        "--explain", action="store_true",
        help="Показать полный explanation для каждого кейса.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        print(f"Dataset не найден: {args.dataset}", file=sys.stderr)
        return 1
    if not args.catalog.exists():
        print(f"Catalog не найден: {args.catalog}", file=sys.stderr)
        return 1

    history = load_json(args.dataset)
    catalog = load_catalog(args.catalog)

    # Определяем список SKU
    if args.all:
        skus = list(history["weekly_consumption"].keys())
    else:
        skus = [args.sku]

    # Определяем горизонты
    if args.horizons:
        horizons = args.horizons
    else:
        horizons = [args.horizon]

    return run(
        history=history,
        catalog=catalog,
        skus=skus,
        horizons=horizons,
        output_format=args.output_format,
        show_explanation=args.explain,
    )


if __name__ == "__main__":
    sys.exit(main())