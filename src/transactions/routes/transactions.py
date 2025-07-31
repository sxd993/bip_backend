from fastapi import APIRouter, Depends, HTTPException
from src.utils.jwt_handler import get_token, decode_access_token
from database import connect_to_db
import mysql.connector

router = APIRouter()

@router.get("/get-transactions")
async def get_transactions(token: str = Depends(get_token)):
    """Получение информации о текущих транзакциях пользователя"""
    try:
        # Декодируем токен
        token_data = decode_access_token(token)
        user_id = token_data.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Невалидный токен")

        # Подключаемся к базе данных
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Получаем транзакции пользователя
        cursor.execute(
            "SELECT id, amount, transaction_type, created_at FROM transactions WHERE user_id = %s",
            (user_id,),
        )
        transactions = cursor.fetchall()

        if not transactions:
            cursor.close()
            conn.close()
            return {"transactions": []}

        # Формируем ответ
        response_data = {
            "transactions": [
                {
                    "id": tx["id"],
                    "amount": float(tx["amount"]),
                    "transaction_type": tx["transaction_type"],
                    "created_at": tx["created_at"].isoformat(),
                }
                for tx in transactions
            ]
        }

        cursor.close()
        conn.close()
        return response_data

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")