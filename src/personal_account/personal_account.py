"""
Модуль auth.py
==============

Главный модуль аутентификации, объединяющий все подмодули.
"""

from fastapi import APIRouter

router = APIRouter()

# Подключаем все подмодули для личного кабинета юридического лица
from .legal.routes.info import router as company_router
from .legal.routes.employees import router as employees_router

router.include_router(employees_router, tags=["employees"])
router.include_router(company_router, tags=["company"])

# Подключаем все подмодули для личного кабинета физического лица
