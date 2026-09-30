"""Блок 3: гибкий ввод — строка вручную, JSON из репозитория, свой JSON.

Демонстрирует три режима работы с нормализатором:
1. Программный вызов normalize_movement(text) — строка задаётся прямо в тесте.
2. Загрузка списка записей из dataset_part1.json и пакетная обработка.
3. Свой JSON от пользователя — создаётся во временной папке tmp_path.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.part1.part1_normalize import normalize_movement

# ─── 3.1. Ручной ввод строки ────────────────────────────────────────

class TestManualInput:
    """Строка задаётся прямо в тесте — для отладки и демонстрации."""

    def test_single_manual_line(self, catalog):
        """Классический пример из задания."""
        text = "05.03.2026 MS-01 приход OIL-001, 2 канистры по 5 л, НК-345"
        result = normalize_movement(text, catalog)

        assert result["date"] == "2026-03-05"
        assert result["sku"] == "OIL-001"
        assert result["location"] == "MS-01"
        assert result["operation"] == "receipt"
        assert result["qty"] == 10.0
        assert result["unit"] == "л"
        assert result["batch"] is None
        assert result["doc_no"] == "НК-345"

    @pytest.mark.parametrize("text", [
        "05.03.2026 ms-01 приход oil-001 1 л",
        "05.03.2026 MS-01 ПРИХОД OIL-001 1 л",
        "05.03.2026  MS-01   приход   OIL-001   1 л",
        "05.03.2026 MS-01 приход oil 001 1 л",
    ])
    def test_user_typed_variants(self, catalog, text):
        """Пользователь может ввести строку с любым регистром и пробелами."""
        result = normalize_movement(text, catalog)
        assert result["sku"] == "OIL-001", f"'{text}': sku = {result['sku']!r}"
        assert result["operation"] == "receipt"
        assert result["qty"] == 1.0
        assert result["unit"] == "л"
        assert result["date"] == "2026-03-05"

    def test_semicolon_separated(self, catalog):
        """Формат с разделителями-точками с запятой (как M6)."""
        text = "2026-03-08; MS-01; CONS-051; расход; 48 пар"
        result = normalize_movement(text, catalog)

        assert result["date"] == "2026-03-08"
        assert result["location"] == "MS-01"
        assert result["sku"] == "CONS-051"
        assert result["operation"] == "consume"
        assert result["qty"] == 48.0
        assert result["unit"] == "пар"

    def test_partial_input_no_sku(self, catalog):
        """Без SKU — часть полей может быть None, но структура сохраняется."""
        text = "05.03.2026 приход 5 л"
        result = normalize_movement(text, catalog)

        assert result["date"] == "2026-03-05"
        assert result["operation"] == "receipt"
        assert result["qty"] == 5.0
        assert set(result.keys()) == {
            "date", "sku", "location", "operation",
            "qty", "unit", "batch", "doc_no",
        }


# ─── 3.2. Пакетная обработка из dataset_part1.json ──────────────────

class TestJsonBatchInput:
    """Загрузка записей из JSON-файла в репозитории и пакетная обработка."""

    @pytest.fixture(scope="class")
    @classmethod
    def dataset_path(cls) -> Path:
        """Путь к dataset_part1.json в репозитории."""
        return (
            Path(__file__).resolve().parent.parent.parent
            / "src" / "part1" / "dataset_part1.json"
        )

    def test_dataset_exists(self, dataset_path):
        """Файл существует и корректно читается."""
        assert dataset_path.exists(), f"Не найден {dataset_path}"
        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 8, f"Ожидалось 8 записей, получено {len(data)}"

    def test_batch_processing(self, catalog, dataset_path):
        """Все записи из JSON обрабатываются без ошибок."""
        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)

        for record in data:
            result = normalize_movement(record["text"], catalog)
            assert set(result.keys()) == {
                "date", "sku", "location", "operation",
                "qty", "unit", "batch", "doc_no",
            }, f"{record['id']}: неполный набор ключей"

    def test_all_records_have_sku_or_location(self, catalog, dataset_path):
        """Хотя бы одно из {sku, location} извлечено для каждой записи."""
        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)

        for record in data:
            result = normalize_movement(record["text"], catalog)
            assert result["sku"] or result["location"], (
                f"{record['id']}: не извлечён ни sku, ни location. "
                f"Результат: {result}"
            )

    def test_operations_are_valid(self, catalog, dataset_path):
        """Все операции входят в допустимый набор."""
        valid = {"receipt", "consume", "writeoff", "return", "correction"}

        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)

        for record in data:
            result = normalize_movement(record["text"], catalog)
            if result["operation"] is not None:
                assert result["operation"] in valid, (
                    f"{record['id']}: недопустимая операция "
                    f"{result['operation']!r}"
                )

    def test_quantities_are_finite(self, catalog, dataset_path):
        """qty — либо None, либо конечное число."""
        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)

        for record in data:
            result = normalize_movement(record["text"], catalog)
            qty = result["qty"]
            if qty is not None:
                assert isinstance(qty, (int, float)), (
                    f"{record['id']}: qty не число — {type(qty)}"
                )
                assert not math.isnan(qty), f"{record['id']}: qty = NaN"
                assert not math.isinf(qty), f"{record['id']}: qty = inf"

    def test_no_unexpected_none_in_m1(self, catalog, dataset_path):
        """Для M1 все обязательные поля заполнены."""
        with open(dataset_path, encoding="utf-8") as f:
            data = json.load(f)

        m1 = next(r for r in data if r["id"] == "M1")
        result = normalize_movement(m1["text"], catalog)

        required = ["date", "sku", "location", "operation", "qty", "unit"]
        for field in required:
            assert result[field] is not None, (
                f"M1: поле '{field}' = None, ожидалось заполненное значение"
            )


# ─── 3.3. Гибкий ввод: свой JSON от пользователя ────────────────────

class TestCustomJsonInput:
    """Пользователь может указать свой JSON с записями."""

    @staticmethod
    def _make_json(tmp_path: Path, data: list[dict]) -> Path:
        """Создаёт временный JSON-файл и возвращает путь."""
        path = tmp_path / "custom_records.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def test_custom_json_two_records(self, catalog, tmp_path):
        """Простой пользовательский JSON на 2 записи."""
        custom_data = [
            {"id": "X1", "text": "05.03.2026 MS-01 приход OIL-001 1 л"},
            {"id": "X2", "text": "06.03.2026 MS-02 расход OIL-002 500 мл"},
        ]
        path = self._make_json(tmp_path, custom_data)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        results = [normalize_movement(r["text"], catalog) for r in data]

        assert results[0]["sku"] == "OIL-001"
        assert results[0]["qty"] == 1.0
        assert results[0]["operation"] == "receipt"

        assert results[1]["sku"] == "OIL-002"
        assert results[1]["qty"] == 0.5
        assert results[1]["operation"] == "consume"

    def test_custom_json_single_record(self, catalog, tmp_path):
        """Пользователь прогнал один корнер-кейс."""
        custom_data = [
            {
                "id": "CORNER-1",
                "text": "Корректировка 15.03.2026, MS-02, CONS-052: −120 шт",
            },
        ]
        path = self._make_json(tmp_path, custom_data)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        result = normalize_movement(data[0]["text"], catalog)
        assert result["operation"] == "correction"
        assert result["qty"] == -120.0
        assert result["unit"] == "шт"

    def test_custom_json_empty_list(self, catalog, tmp_path):
        """Пустой JSON — не падает."""
        path = self._make_json(tmp_path, [])

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        results = [normalize_movement(r["text"], catalog) for r in data]
        assert results == []

    def test_custom_json_unknown_sku(self, catalog, tmp_path):
        """Неизвестный SKU — sku = None, но структура сохраняется."""
        custom_data = [
            {"id": "UNK", "text": "05.03.2026 MS-01 приход UNKNOWN-999 1 л"},
        ]
        path = self._make_json(tmp_path, custom_data)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        result = normalize_movement(data[0]["text"], catalog)
        assert result["sku"] is None
        assert result["date"] == "2026-03-05"
        assert result["operation"] == "receipt"
        assert result["qty"] == 1.0

    def test_custom_json_batch_of_three(self, catalog, tmp_path):
        """Пакет из трёх записей — все обрабатываются."""
        custom_data = [
            {"id": "B1", "text": "1 марта 2026 MS-01 приход OIL-001 500 мл"},
            {"id": "B2", "text": "02.03.2026 MS-02 расход SCRB-020 1 кг"},
            {"id": "B3", "text": "03.03.2026 Сочи списание WRAP-030 0,5 кг"},
        ]
        path = self._make_json(tmp_path, custom_data)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        results = [normalize_movement(r["text"], catalog) for r in data]

        assert results[0]["sku"] == "OIL-001"
        assert results[0]["qty"] == 0.5
        assert results[1]["sku"] == "SCRB-020"
        assert results[1]["qty"] == 1.0
        assert results[2]["sku"] == "WRAP-030"
        assert results[2]["location"] == "Сочи"


# ─── 3.4. Формат ответа — единый для всех режимов ───────────────────

class TestResultShape:
    """Независимо от входа, ответ всегда одинаковой формы."""

    @pytest.mark.parametrize("text", [
        "05.03.2026 MS-01 приход OIL-001 1 л",
        "мусор",
        "",
        "2026-03-08; MS-01; CONS-051; расход; 48 пар",
        "Возврат 12 марта 2026 г.: OIL-002, 2 л",
    ])
    def test_same_keys_always(self, catalog, text):
        """Все 8 ключей присутствуют всегда."""
        result = normalize_movement(text, catalog)
        assert set(result.keys()) == {
            "date", "sku", "location", "operation",
            "qty", "unit", "batch", "doc_no",
        }

    @pytest.mark.parametrize("text", [
        "05.03.2026 MS-01 приход OIL-001 1 л",
        "2026-03-08; MS-01; CONS-051; расход; 48 пар",
    ])
    def test_types_are_correct(self, catalog, text):
        """Типы полей: str | None для строк, float | None для qty."""
        result = normalize_movement(text, catalog)

        for field in ["date", "sku", "location", "operation", "unit", "batch", "doc_no"]:
            assert result[field] is None or isinstance(result[field], str), (
                f"{field}: {type(result[field])}"
            )

        assert result["qty"] is None or isinstance(result["qty"], float), (
            f"qty: {type(result['qty'])}"
        )