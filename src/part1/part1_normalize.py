"""Часть 1: нормализация записей движения товара."""

from __future__ import annotations

import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from src.part1.config import (
    COMPOSITE_UNIT_WORDS,
    DATE_FORMATS,
    LOCATION_KEYWORDS,
    MIN_TEXT_LENGTH,
    OPERATION_KEYWORDS,
    OPERATION_PRIORITY,
    RU_MONTHS,
    SKU_ALIASES,
    SKU_MATCH_THRESHOLD,
    SKU_PATTERN,
    UNIT_MULTIPLIERS,
)

# ───────────────────────────────────────────────────────────────────────
# Загрузка каталога
# ───────────────────────────────────────────────────────────────────────

# Путь к корню проекта: src/part1/part1_normalize.py → вверх на 3 уровня
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "catalog.json"


def load_catalog(path: str | Path | None = None) -> dict[str, dict]:
    """
    Загружает справочник товаров и индексирует по SKU.

    Args:
        path: Путь к catalog.json. Если None — используется путь
              относительно корня проекта.

    Returns:
        Словарь {sku: item}.
    """
    if path is None:
        path = DEFAULT_CATALOG_PATH
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    return {item["sku"]: item for item in items}


# ───────────────────────────────────────────────────────────────────────
# Парсинг дат
# ───────────────────────────────────────────────────────────────────────

def _parse_date(text: str) -> str | None:
    """
    Извлекает дату из текста и возвращает ISO-строку (YYYY-MM-DD).

    Поддерживает:
    - 05.03.2026, 07.03.26
    - 2026-03-08
    - 03/06/26 (интерпретируется как mm/dd/yy)
    - 1 марта 2026 г.
    """
    # 1. Текстовый месяц: "1 марта 2026", "12 марта 2026 г."
    ru_pattern = re.compile(
        r"\b(\d{1,2})\s+(" + "|".join(RU_MONTHS) + r")\s+(\d{4})",
        re.IGNORECASE,
    )
    m = ru_pattern.search(text)
    if m:
        day, month_name, year = m.groups()
        month = RU_MONTHS[month_name.lower()]
        return f"{int(year):04d}-{month:02d}-{int(day):02d}"

    # 2. Числовые форматы
    date_like = re.compile(r"\b(\d{1,4})[./-](\d{1,2})[./-](\d{2,4})\b")
    for match in date_like.finditer(text):
        raw = match.group(0)
        for fmt in DATE_FORMATS:
            try:
                # Даты в данных без времени и часового пояса — naive OK.
                dt = datetime.strptime(raw, fmt)  # noqa: DTZ007
                # Отсекаем нелепые года (например, 26 → 2026)
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


# ───────────────────────────────────────────────────────────────────────
# Парсинг операций
# ───────────────────────────────────────────────────────────────────────

def _parse_operation(text: str) -> str | None:
    """Определяет тип операции по ключевым словам."""
    text_lower = text.lower()
    for op in OPERATION_PRIORITY:
        for kw in OPERATION_KEYWORDS[op]:
            if kw in text_lower:
                return op
    return None


# ───────────────────────────────────────────────────────────────────────
# Парсинг SKU
# ───────────────────────────────────────────────────────────────────────

def _parse_sku(text: str, catalog: dict[str, dict]) -> str | None:
    """
    Извлекает SKU из текста.

    Сначала — прямой regex (OIL-001, oil 001, «oil 001»).
    Если не нашли — нечёткое сопоставление по названию из каталога.
    """
    # 1. Прямой regex
    for match in re.finditer(SKU_PATTERN, text):
        prefix, number = match.groups()
        candidate = f"{prefix.upper()}-{number.zfill(3)}"
        if candidate in catalog:
            return candidate

    # 2. Алиасы по названию (новое)
    text_lower = text.lower()
    for sku, aliases in SKU_ALIASES.items():
        if sku not in catalog:
            continue
        for alias in aliases:
            if alias in text_lower:
                return sku

    # 3. Fallback — нечёткое сопоставление (SequenceMatcher)
    best_sku: str | None = None
    best_score: float = 0.0
    for sku, item in catalog.items():
        name_lower = item["name"].lower()
        score = SequenceMatcher(None, name_lower, text_lower).ratio()
        for word in name_lower.split():
            if len(word) > 4 and word in text_lower:
                score = max(score, 0.8)
        if score > best_score:
            best_score = score
            best_sku = sku

    if best_score >= SKU_MATCH_THRESHOLD:
        return best_sku
    return None


# ───────────────────────────────────────────────────────────────────────
# Парсинг количества и единиц
# ───────────────────────────────────────────────────────────────────────

def _parse_qty_unit(
    text: str,
    sku: str | None,
    catalog: dict[str, dict],
) -> tuple[float | None, str | None]:
    """
    Извлекает количество и единицу, приводит к базовой единице позиции.
    """
    # 1. Составная единица: "N <слово> по M <единица>"
    composite = re.compile(
        r"(\d+[.,]?\d*)\s*(?:" + "|".join(COMPOSITE_UNIT_WORDS) + r")\w*\.?\s*по\s*"
        r"(\d+[.,]?\d*)\s*([а-яё]+)",
        re.IGNORECASE,
    )
    m = composite.search(text)
    if m:
        n1, n2, unit = m.groups()
        total = float(n1.replace(",", ".")) * float(n2.replace(",", "."))
        return _to_base_unit(total, unit.lower(), sku, catalog), _base_unit(sku, catalog)

    # 2. Простая единица: "450 мл", "3,5 кг", "48 пар", "−120 шт"
    simple = re.compile(
        r"(?<!\d)([−\-]?\d+(?:[.,]\d+)?)\s*(мл|л|г|кг|шт|пар|уп)\b",
        re.IGNORECASE,
    )
    for m in simple.finditer(text):
        qty_raw, unit = m.groups()
        unit_lower = unit.lower()
        qty = float(qty_raw.replace(",", ".").replace("−", "-"))

        # Пропускаем годы: 4-значные числа + 'г' (например, "2026 г.")
        if unit_lower == "г" and qty >= 1000:
            continue

        return _to_base_unit(qty, unit_lower, sku, catalog), _base_unit(sku, catalog)

    # 3. Только число без единицы — берём базовую единицу из каталога
    number = re.search(r"(?<!\d)([−\-]?\d+[.,]?\d*)", text)
    if number:
        qty = float(number.group(1).replace(",", ".").replace("−", "-"))
        return qty, _base_unit(sku, catalog)

    return None, None


def _to_base_unit(
    qty: float,
    unit: str,
    sku: str | None,
    catalog: dict[str, dict],
) -> float:
    """
    Приводит количество к базовой единице позиции.
    """
    multiplier = UNIT_MULTIPLIERS.get(unit, 1.0)

    if sku and sku in catalog:
        base_unit = catalog[sku]["unit"]
        if unit == base_unit:
            return qty

    if unit == "уп" and sku and sku in catalog:
        return qty * catalog[sku]["pack_size"]

    return qty * multiplier


def _base_unit(sku: str | None, catalog: dict[str, dict]) -> str | None:
    """Возвращает базовую единицу позиции из каталога."""
    if sku and sku in catalog:
        return catalog[sku]["unit"]
    return None


# ───────────────────────────────────────────────────────────────────────
# Парсинг локации, партии, документа
# ───────────────────────────────────────────────────────────────────────

def _parse_location(text: str) -> str | None:
    """Извлекает локацию по ключевым словам."""
    for loc in LOCATION_KEYWORDS:
        if loc.lower() in text.lower():
            return loc.upper() if loc.startswith("ms") else loc
    return None


def _parse_batch(text: str) -> str | None:
    """Извлекает номер партии (B-OIL-001-012)."""
    m = re.search(r"\b(B[\-][A-ZА-Я0-9\-]+)\b", text)
    return m.group(1) if m else None


def _parse_doc_no(text: str) -> str | None:
    """
    Извлекает номер документа (НК-345).

    Номера документов в данных — кириллические (НК-345),
    локации и SKU — латинские (MS-01, OIL-001). Ищем только
    кириллические префиксы, чтобы не путать с SKU.
    """
    for m in re.finditer(r"\b([А-ЯЁ]{1,3}[\-]\d{2,4})\b", text):
        return m.group(1)
    return None


# ───────────────────────────────────────────────────────────────────────
# Основная функция
# ───────────────────────────────────────────────────────────────────────

def normalize_movement(
    text: str,
    catalog: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """
    Нормализует текстовую запись движения товара в структурированный словарь.
    """
    if catalog is None:
        catalog = load_catalog()

    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        return _empty_result()

    sku = _parse_sku(text, catalog)
    qty, unit = _parse_qty_unit(text, sku, catalog)

    return {
        "date": _parse_date(text),
        "sku": sku,
        "location": _parse_location(text),
        "operation": _parse_operation(text),
        "qty": qty,
        "unit": unit,
        "batch": _parse_batch(text),
        "doc_no": _parse_doc_no(text),
    }


def _empty_result() -> dict[str, Any]:
    """Возвращает словарь с None для всех полей."""
    return {
        "date": None,
        "sku": None,
        "location": None,
        "operation": None,
        "qty": None,
        "unit": None,
        "batch": None,
        "doc_no": None,
    }