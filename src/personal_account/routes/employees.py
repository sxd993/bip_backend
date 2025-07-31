"""
Модуль employees.py
==================

Модуль для управления сотрудниками компаний.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from src.utils.jwt_handler import get_token, decode_access_token
from src.auth.utils.password_handler import hash_password
from database import connect_to_db
import mysql.connector
from models import AddEmployeeData
from src.auth.utils.auth_utils import create_bitrix_contact

router = APIRouter()


@router.post("/company/add-employee")
async def add_employee(data: AddEmployeeData, token: str = Depends(get_token)):
    """Добавление сотрудника в компанию (только для Руководитель и Руководитель отдела)"""
    try:
        # Декодируем токен
        current_user = decode_access_token(token)

        # Проверка роли пользователя (разрешено только для Руководитель и Руководитель отдела)
        if current_user.get("role") not in ["Руководитель", "Руководитель отдела"]:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав: требуется роль 'Руководитель' или 'Руководитель отдела'",
            )

        # Проверка, что пользователь принадлежит к юридическому лицу и имеет company_id
        if current_user.get("user_type") != "legal" or not current_user.get(
            "company_id"
        ):
            raise HTTPException(
                status_code=403,
                detail="Только пользователи юридического лица могут добавлять сотрудников",
            )

        # Получаем company_id и department_id текущего пользователя
        company_id = current_user.get("company_id")
        user_department_id = current_user.get("department_id")
        user_role = current_user.get("role")

        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Получаем bitrix_company_id из таблицы companies
        cursor.execute(
            "SELECT bitrix_company_id FROM companies WHERE id = %s",
            (company_id,)
        )
        company_result = cursor.fetchone()
        if not company_result or not company_result.get("bitrix_company_id"):
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=500,
                detail="Не найден Bitrix ID компании"
            )
        
        bitrix_company_id = company_result["bitrix_company_id"]

        # Проверяем, не существует ли уже пользователь
        cursor.execute(
            "SELECT * FROM users WHERE phone = %s OR email = %s",
            (data.phone, data.email),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="Пользователь с таким телефоном или email уже существует",
            )

        # Ограничения по ролям
        if user_role == "Руководитель отдела":
            # Для Руководитель отдела разрешаем только роль Сотрудник
            if data.role == "Руководитель отдела":
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail="Назначение роли 'Руководитель отдела' разрешено только для Руководитель",
                )
            # Ограничиваем department_id только отделом текущего пользователя
            if not user_department_id:
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail="У вас нет отдела для добавления сотрудников",
                )
            if data.department_id != user_department_id:
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail="Вы можете добавлять сотрудников только в свой отдел",
                )

        # Проверяем, что department_id указан для роли Сотрудник и валиден
        if data.role == "Сотрудник" and not data.department_id:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="Для роли 'Сотрудник' необходимо указать department_id",
            )

        if data.department_id:
            cursor.execute(
                "SELECT * FROM departments WHERE id = %s AND company_id = %s",
                (data.department_id, company_id),
            )
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail="Указанный отдел не существует или не принадлежит компании",
                )

        # Создаем контакт в Bitrix24 - используем bitrix_company_id
        contact_data = {
            "NAME": data.first_name,
            "SECOND_NAME": data.second_name,
            "LAST_NAME": data.last_name,
            "PHONE": [{"VALUE": data.phone, "VALUE_TYPE": "WORK"}],
            "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
            "COMPANY_ID": bitrix_company_id,
        }
        contact_id = create_bitrix_contact(contact_data)

        if not contact_id:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=500, detail="Ошибка создания контакта в Bitrix24"
            )

        # Хешируем пароль
        hashed_password = hash_password(data.password)

        # Создаем пользователя в БД
        cursor.execute(
            """INSERT INTO users (
                login, password, user_type, role, first_name, second_name, 
                last_name, phone, email, contact_id, company_id, department_id, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data.phone,
                hashed_password,
                "legal",
                data.role,
                data.first_name,
                data.second_name,
                data.last_name,
                data.phone,
                data.email,
                contact_id,
                company_id,
                data.department_id,
                0.0,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return JSONResponse(content={"message": "Сотрудник успешно добавлен"})

    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")