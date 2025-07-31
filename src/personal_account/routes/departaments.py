from fastapi import APIRouter, Depends, HTTPException
from src.utils.jwt_handler import get_token, decode_access_token
from database import connect_to_db
import mysql.connector

router = APIRouter()


@router.post("/departaments/create")
async def create_department(name: str, token: str = Depends(get_token)):
    """Создать новый департамент внутри компании (только для руководителей)"""
    try:
        token_data = decode_access_token(token)
        role = token_data.get("role")
        company_id = token_data.get("company_id")

        if role not in ["Руководитель"]:
            raise HTTPException(
                status_code=403, detail="Недостаточно прав для создания департамента"
            )
        if not company_id:
            raise HTTPException(status_code=400, detail="Компания не найдена")

        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Проверяем, есть ли уже департамент с таким именем в компании
        cursor.execute(
            "SELECT id FROM departments WHERE company_id = %s AND name = %s",
            (company_id, name),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400, detail="Департамент с таким именем уже существует"
            )

        # Создаём департамент
        cursor.execute(
            "INSERT INTO departments (company_id, name, balance) VALUES (%s, %s, %s)",
            (company_id, name, 0.0),
        )
        conn.commit()
        department_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return {"message": "Департамент успешно создан", "department_id": department_id}

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")


@router.get("/departaments/get")
async def get_departments(token: str = Depends(get_token)):
    """Получить список департаментов компании по company_id из токена"""
    try:
        token_data = decode_access_token(token)
        company_id = token_data.get("company_id")

        if not company_id:
            raise HTTPException(status_code=400, detail="Компания не найдена")

        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Получаем все департаменты компании с их балансом
        cursor.execute(
            "SELECT id, name, balance, created_at FROM departments WHERE company_id = %s ORDER BY created_at DESC",
            (company_id,),
        )
        departments = cursor.fetchall()

        cursor.close()
        conn.close()

        # Форматируем данные для ответа
        formatted_departments = []
        for dept in departments:
            formatted_departments.append(
                {
                    "id": dept["id"],
                    "name": dept["name"],
                    "balance": float(dept["balance"]),
                    "created_at": (
                        dept["created_at"].isoformat() if dept["created_at"] else None
                    ),
                }
            )

        return {
            "departments": formatted_departments,
            "total_count": len(formatted_departments),
        }

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")
