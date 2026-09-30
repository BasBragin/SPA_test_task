"""Минимальная проверка связи с GigaChat.

Запуск:
    python scripts/check_gigachat.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

credentials = os.getenv("GIGACHAT_CREDENTIALS")
if not credentials:
    print("GIGACHAT_CREDENTIALS не задан в .env")
    sys.exit(1)

print(f"Ключ найден, длина: {len(credentials)} символов")
print(f"Начало: {credentials[:20]}...")

try:
    from gigachat import GigaChat
except ImportError as e:
    print(f"Не установлен пакет gigachat: {e}")
    sys.exit(1)

print("\nПодключаемся к GigaChat...")

try:
    with GigaChat(
        credentials=credentials,
        verify_ssl_certs=False,
        scope="GIGACHAT_API_PERS",
        model="GigaChat-2",
    ) as giga:
        response = giga.chat("Ответь одним словом: работает?")
        print("\nОтвет от GigaChat:")
        print(f"   {response.choices[0].message.content}")
except (OSError, ValueError, KeyError, TypeError) as e:
    print(f"\nОшибка: {type(e).__name__}: {e}")
    sys.exit(1)