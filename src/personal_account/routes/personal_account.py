"""
Модуль auth.py
==============

Главный модуль аутентификации, объединяющий все подмодули.
"""

from fastapi import APIRouter
from .departaments import router as departament_router
from .employees import router as employees_router

router = APIRouter()

# Подключаем все подмодули
router.include_router(employees_router, tags=["employees"])
router.include_router(departament_router, tags=["departments"])
