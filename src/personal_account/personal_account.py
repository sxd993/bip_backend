"""
Модуль auth.py
==============

Главный модуль аутентификации, объединяющий все подмодули.
"""

from fastapi import APIRouter
from .legal.routes.employees import router as employees_router
from .legal.routes.departaments import router as departament_router

router = APIRouter()

# Подключаем все подмодули для личного кабинета юридического лица
router.include_router(employees_router, tags=["employees"])
router.include_router(departament_router, tags=["departments"])
