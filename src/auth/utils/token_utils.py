"""
Модуль token_utils.py
=====================

Утилиты для генерации и работы с токенами приглашений
"""

import secrets
import string

def generate_company_token() -> str:
    """
    Генерирует случайный токен из 32 символов для приглашения в компанию
    
    Returns:
        str: Токен из 32 символов (буквы и цифры)
    """
    # Используем только буквы и цифры для простоты
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(32))
    return token