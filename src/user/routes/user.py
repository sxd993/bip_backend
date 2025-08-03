from fastapi import APIRouter, Depends, HTTPException
from src.utils.jwt_handler import get_token, decode_access_token
from database import connect_to_db
import mysql.connector

router = APIRouter()


@router.get("/get-info")
async def get_user(token: str = Depends(get_token)):
    """Получение информации о текущем пользователе"""
    try:
        # Декодируем токен
        token_data = decode_access_token(token)
        user_id = token_data.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Невалидный токен")

        # Подключаемся к базе данных
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Получаем актуальные данные пользователя из БД
        cursor.execute(
            "SELECT id, user_type, role, first_name, second_name, last_name, "
            "phone, email, contact_id, company_id, department_id, balance, created_at "
            "FROM users WHERE id = %s",
            (user_id,),
        )
        user = cursor.fetchone()

        if not user:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем информацию о компании (если юр. лицо)
        company_info = None
        if user["user_type"] == "legal" and user["company_id"]:
            cursor.execute(
                "SELECT id, name, inn, balance FROM companies WHERE id = %s",
                (user["company_id"],),
            )
            company_info = cursor.fetchone()

        # Формируем базовый ответ
        response_data = {
            "id": user["id"],
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "phone": user["phone"],
            "email": user["email"],
            "contact_id": user["contact_id"],
            "balance": float(user["balance"]),
            "created_at": (
                user["created_at"].isoformat() if user["created_at"] else None
            ),
        }


        if user["user_type"] == "legal":
            response_data["company_id"] = user["company_id"]
            response_data["department_id"] = user["department_id"]

        if company_info:
            response_data["company"] = {
                "id": company_info["id"],
                "name": company_info["name"],
                "inn": company_info["inn"],
                "balance": float(company_info["balance"]),
            }

        cursor.close()
        conn.close()

        return response_data

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")
