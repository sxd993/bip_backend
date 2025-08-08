"""
Модуль employees.py
============================

Модуль для получения списка сотрудников компании.
"""

from fastapi import APIRouter, HTTPException, Depends
from src.utils.jwt_handler import get_token, decode_access_token
from database import connect_to_db
import mysql.connector

router = APIRouter()


@router.get("/company/employees")
async def get_company_employees(token: str = Depends(get_token)):
    """
    Получение списка всех сотрудников компании.
    Доступно только для руководителей.
    """
    try:
        # Декодируем токен
        current_user = decode_access_token(token)
        
        # Проверяем права доступа
        if current_user.get("role") != "Руководитель":
            raise HTTPException(
                status_code=403,
                detail="Только руководитель может просматривать список сотрудников"
            )
        
        company_id = current_user.get("company_id")
        if not company_id:
            raise HTTPException(
                status_code=404,
                detail="У вас нет привязанной компании"
            )
        
        # Подключаемся к БД
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем всех сотрудников компании
        cursor.execute(
            """SELECT id, first_name, second_name, last_name, 
                      phone, email, role, position, balance, created_at
               FROM users
               WHERE company_id = %s
               ORDER BY 
                   CASE role 
                       WHEN 'Руководитель' THEN 1
                       WHEN 'Сотрудник' THEN 2
                       ELSE 3
                   END,
                   created_at DESC""",
            (company_id,)
        )
        employees = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Форматируем данные
        formatted_employees = []
        for emp in employees:
            formatted_employees.append({
                "id": emp["id"],
                "full_name": f"{emp['last_name']} {emp['first_name']} {emp['second_name'] or ''}".strip(),
                "first_name": emp["first_name"],
                "second_name": emp["second_name"],
                "last_name": emp["last_name"],
                "phone": emp["phone"],
                "email": emp["email"],
                "role": emp["role"],
                "position": emp.get("position", "Не указана"),
                "balance": float(emp["balance"]),
                "created_at": emp["created_at"].isoformat() if emp["created_at"] else None
            })
        
        return {
            "employees": formatted_employees,
            "total_count": len(formatted_employees)
        }
        
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")