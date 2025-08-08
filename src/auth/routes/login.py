"""
Модуль authentication.py
========================

Модуль для аутентификации пользователей (вход/выход).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from src.utils.jwt_handler import create_access_token
from ..utils.password_handler import verify_password
from config import ACCESS_TOKEN_EXPIRE_MINUTES
from database import connect_to_db
import mysql.connector
from ..models import LoginData
import os

router = APIRouter()


@router.post("/login")
async def login(data: LoginData):
    """Вход пользователя по логину/телефону и паролю"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Ищем пользователя по почте или телефону
        cursor.execute(
            "SELECT * FROM users WHERE email = %s OR phone = %s",
            (data.email_or_phone, data.email_or_phone),
        )
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=401, detail="Неверный номер телефона/почта или пароль")

        # Проверяем пароль
        if not verify_password(data.password, user["password"]):
            cursor.close()
            conn.close()
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")

        # Получаем информацию о компании (если юр. лицо)
        company_info = None
        if user["user_type"] == "legal" and user["company_id"]:
            cursor.execute(
                "SELECT * FROM companies WHERE id = %s", (user["company_id"],)
            )
            company_info = cursor.fetchone()

        # Создаем токен
        token_data = { 
            "sub": user["email"],
            "user_id": user["id"],
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "contact_id": user["contact_id"],
            "company_id": user.get("company_id"),
            "department_id": user.get("department_id"),
        }
        access_token = create_access_token(token_data, ACCESS_TOKEN_EXPIRE_MINUTES)

        response_data = {
            "message": "Вход выполнен успешно",
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "balance": float(user["balance"]),
        }

        if company_info:
            response_data["company"] = {
                "name": company_info["name"],
                "inn": company_info["inn"],
                "balance": float(company_info["balance"]),
            }

        response = JSONResponse(content=response_data)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True if os.getenv("ENV") == "production" else False, 
            samesite="none" if os.getenv("ENV") == "production" else "lax", 
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

        cursor.close()
        conn.close()
        return response

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")


@router.post("/logout")
async def logout():
    """Выход из системы"""
    response = JSONResponse(content={"message": "Выход выполнен успешно"})
    
    # Удаляем cookie с теми же параметрами, что и при создании
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True if os.getenv("ENV") == "production" else False,
        samesite="none" if os.getenv("ENV") == "production" else "lax",
        path="/",
    )
    
    return response