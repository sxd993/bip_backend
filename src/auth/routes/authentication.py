"""
Модуль auth.py
==============

Главный модуль аутентификации, объединяющий все подмодули.
"""

from fastapi import APIRouter
from .registration import router as registration_router
from .login import router as authentication_router

router = APIRouter()

# Подключаем все подмодули
router.include_router(registration_router, tags=["registration"])
router.include_router(authentication_router, tags=["authentication"])
