"""
Модуль info.py
======================

Модуль для получения информации о компании.
"""

from fastapi import APIRouter, HTTPException, Depends
from src.utils.jwt_handler import get_token, decode_access_token
from database import connect_to_db
import mysql.connector

router = APIRouter()


@router.get("/company/info")
async def get_company_info(token: str = Depends(get_token)):
    """
    Получение информации о компании.
    Токен видят только руководители.
    """
    try:
        # Декодируем токен
        current_user = decode_access_token(token)
        
        # Проверяем, что пользователь из юридического лица
        if current_user.get("user_type") != "legal":
            raise HTTPException(
                status_code=403,
                detail="Доступно только для юридических лиц"
            )
        
        # Получаем company_id
        company_id = current_user.get("company_id")
        if not company_id:
            raise HTTPException(
                status_code=404,
                detail="У вас нет привязанной компании"
            )
        
        # Подключаемся к БД
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем данные компании
        cursor.execute(
            """SELECT id, name, inn, invite_token, phone, email, balance, created_at
               FROM companies 
               WHERE id = %s""",
            (company_id,)
        )
        company = cursor.fetchone()
        
        if not company:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=404,
                detail="Компания не найдена"
            )
        
        # Получаем количество сотрудников
        cursor.execute(
            "SELECT COUNT(*) as employees_count FROM users WHERE company_id = %s",
            (company_id,)
        )
        employees_count = cursor.fetchone()["employees_count"]
        
        cursor.close()
        conn.close()
        
        # Формируем ответ
        response_data = {
            "id": company["id"],
            "name": company["name"],
            "inn": company["inn"],
            "phone": company["phone"],
            "email": company["email"],
            "balance": float(company["balance"]),
            "employees_count": employees_count,
            "created_at": company["created_at"].isoformat() if company["created_at"] else None,
        }
        
        # Токен приглашения показываем только руководителю
        if current_user.get("role") == "Руководитель":
            response_data["invite_token"] = company["invite_token"]
            response_data["token_message"] = "Передайте этот токен сотрудникам для регистрации"
        
        return response_data
        
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")