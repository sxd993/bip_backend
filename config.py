"""
Модуль config.py
================

Этот модуль содержит конфигурационные параметры для приложения.

Зависимости:
- os
- pathlib
- dotenv
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка .env файла
load_dotenv(Path(__file__).parent / ".env")

# JWT настройки
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15


# Bitrix24 настройки
BITRIX_DOMAIN = os.getenv("BITRIX_DOMAIN")
BITRIX_TOKEN = os.getenv("BITRIX_TOKEN")


# MySQL настройки
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


# Проверка обязательных переменных
REQUIRED_ENV_VARS = [
    ("SECRET_KEY", SECRET_KEY),
    ("BITRIX_DOMAIN", BITRIX_DOMAIN),
    ("BITRIX_TOKEN", BITRIX_TOKEN),
    ("DB_USER", DB_USER),
    ("DB_PASSWORD", DB_PASSWORD),
    ("DB_NAME", DB_NAME),
]

missing_vars = [name for name, value in REQUIRED_ENV_VARS if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")


# CORS настройки
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
]