"""Блок 1: тесты на реальных данных из Приложения 1 задания."""

from __future__ import annotations

import pytest

from src.part1.part1_normalize import normalize_movement

# ─── Ожидаемые результаты M1–M8 ──────────────────────────────────────

EXPECTED = {
    "M1": {
        "date": "2026-03-05", "sku": "OIL-001", "location": "MS-01",
        "operation": "receipt", "qty": 10.0, "unit": "л",
        "batch": None, "doc_no": "НК-345",
    },
    "M2": {
        "date": "2026-03-01", "sku": "OIL-001", "location": "MS-01",
        "operation": "consume", "qty": 0.45, "unit": "л",
        "batch": "B-OIL-001-012", "doc_no": None,
    },
    "M3": {
        "date": "2026-03-06", "sku": "SCRB-020", "location": "Сочи",
        "operation": "writeoff", "qty": 1.2, "unit": "кг",
        "batch": None, "doc_no": None,
    },
    "M4": {
        "date": "2026-03-07", "sku": "WRAP-030", "location": "MS-02",
        "operation": "consume", "qty": 3.5, "unit": "кг",
        "batch": "B-WRAP-030-004", "doc_no": None,
    },
    "M5": {
        "date": "2026-03-12", "sku": "OIL-002", "location": None,
        "operation": "return", "qty": 2.0, "unit": "л",
        "batch": None, "doc_no": None,
    },
    "M6": {
        "date": "2026-03-08", "sku": "CONS-051", "location": "MS-01",
        "operation": "consume", "qty": 48.0, "unit": "пар",
        "batch": None, "doc_no": None,
    },
    "M7": {
        "date": "2026-03-15", "sku": "CONS-052", "location": "MS-02",
        "operation": "correction", "qty": -120.0, "unit": "шт",
        "batch": None, "doc_no": None,
    },
    "M8": {
        "date": None, "sku": "CONS-051", "location": "Красная Поляна",
        "operation": "receipt", "qty": 200.0, "unit": "пар",
        "batch": None, "doc_no": None,
    },
}


# ─── Тестовые данные M1–M8 ───────────────────────────────────────────

RECORDS = [
    {"id": "M1", "text": "05.03.2026 MS-01 приход OIL-001, 2 канистры по 5 л, НК-345"},
    {"id": "M2", "text": "1 марта 2026 MS-01 расход oil 001 — 450 мл, B-OIL-001-012"},
    {"id": "M3", "text": "03/06/26 Сочи списание SCRB-020 1,2 кг, истёк срок"},
    {"id": "M4", "text": "07.03.26 ms-02 WRAP 030 расход 3,5кг, парт.B-WRAP-030-004"},
    {"id": "M5", "text": "Возврат 12 марта 2026 г.: OIL-002, 2 л, брак упаковки"},
    {"id": "M6", "text": "2026-03-08; MS-01; CONS-051; расход; 48 пар"},
    {"id": "M7", "text": "Корректировка 15.03.2026, MS-02, CONS-052: −120 шт"},
    {"id": "M8", "text": "Приход тапочек одноразовых, 4 уп. по 50 пар, Красная Поляна"},
]


# ─── Параметризованный тест ──────────────────────────────────────────

@pytest.mark.parametrize("record", RECORDS, ids=[r["id"] for r in RECORDS])
def test_movements_from_task(catalog, record):
    """M1–M8 распарсены корректно."""
    result = normalize_movement(record["text"], catalog)
    expected = EXPECTED[record["id"]]

    for field, value in expected.items():
        assert result[field] == value, (
            f"{record['id']}: поле '{field}' = {result[field]!r}, "
            f"ожидалось {value!r}"
        )


# ─── Отдельный тест: все 8 полей присутствуют ───────────────────────

@pytest.mark.parametrize("record", RECORDS, ids=[r["id"] for r in RECORDS])
def test_all_fields_present(catalog, record):
    """Результат содержит все 8 обязательных ключей."""
    result = normalize_movement(record["text"], catalog)
    assert set(result.keys()) == {
        "date", "sku", "location", "operation",
        "qty", "unit", "batch", "doc_no",
    }