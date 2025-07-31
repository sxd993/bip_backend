"""
Модуль registration.py
=====================

Модуль для регистрации пользователей (физических и юридических лиц).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from src.utils.jwt_handler import create_access_token
from ..utils.password_handler import hash_password
from config import ACCESS_TOKEN_EXPIRE_MINUTES
from database import connect_to_db
import mysql.connector
from models import RegisterPhysicalPersonData, RegisterLegalEntityData
from ..utils.auth_utils import (
    create_bitrix_contact,
    create_bitrix_company,
    create_bitrix_requisite,
)

router = APIRouter()


@router.post("/register/physical")
async def register_physical_person(data: RegisterPhysicalPersonData):
    """Регистрация физического лица"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

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

        # Создаем контакт в Bitrix24
        contact_data = {
            "NAME": data.first_name,
            "SECOND_NAME": data.second_name,
            "LAST_NAME": data.last_name,
            "BIRTHDATE": data.birthdate,
            "PHONE": [{"VALUE": data.phone, "VALUE_TYPE": "WORK"}],
            "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
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
                last_name, birthdate, phone, email, contact_id, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data.login,
                hashed_password,
                "physical",
                "Пользователь",
                data.first_name,
                data.second_name,
                data.last_name,
                data.birthdate,
                data.phone,
                data.email,
                contact_id,
                0.0,
            ),
        )
        conn.commit()

        # Получаем только что созданного пользователя
        cursor.execute("SELECT * FROM users WHERE phone = %s", (data.phone,))
        user = cursor.fetchone()

        # Создаем access_token
        token_data = {
            "sub": user["login"],
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
            "message": "Регистрация успешно завершена",
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "balance": float(user["balance"]),
        }
        response = JSONResponse(content=response_data)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        cursor.close()
        conn.close()
        return response

    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")


@router.post("/register/legal")
async def register_legal_entity(data: RegisterLegalEntityData):
    """Регистрация юридического лица"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM companies WHERE inn = %s", (data.inn,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400, detail="Компания с таким ИНН уже зарегистрирована"
            )

        cursor.execute("SELECT * FROM users WHERE phone = %s", (data.phone,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400, detail="Пользователь с таким телефоном уже существует"
            )

        # Создаем компанию в Bitrix24
        company_data = {
            "TITLE": data.company_name,
            "PHONE": [{"VALUE": data.phone, "VALUE_TYPE": "WORK"}],
            "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
        }
        company_id = create_bitrix_company(company_data)

        if not company_id:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=500, detail="Ошибка создания компании в Bitrix24"
            )

        # Создаем реквизиты компании с ИНН
        requisite_id = create_bitrix_requisite(company_id, data.inn, data.company_name)

        if not requisite_id:
            print(f"Ошибка создания реквизитов для компании {company_id}")

        contact_data = {
            "NAME": data.employee_first_name,
            "SECOND_NAME": data.employee_second_name,
            "LAST_NAME": data.employee_last_name,
            "PHONE": [{"VALUE": data.phone, "VALUE_TYPE": "WORK"}],
            "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
            "COMPANY_ID": company_id,
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

        # Создаем пользователя в БД (Руководитель)
        cursor.execute(
            """INSERT INTO users (
                login, password, user_type, role, first_name, second_name, 
                last_name, phone, email, contact_id, company_id, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data.email,
                hashed_password,
                "legal",
                "Руководитель",
                data.employee_first_name,
                data.employee_second_name,
                data.employee_last_name,
                data.phone,
                data.email,
                contact_id,
                None,  # company_id будет обновлен после создания компании
                0.0,
            ),
        )
        user_id = cursor.lastrowid

        # Создаем компанию в БД с creator_id
        cursor.execute(
            """INSERT INTO companies (
                name, inn, phone, email, bitrix_company_id, balance, creator_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                data.company_name,
                data.inn,
                data.phone,
                data.email,
                company_id,
                0.0,
                user_id,
            ),
        )
        company_db_id = cursor.lastrowid

        # Обновляем company_id в записи пользователя
        cursor.execute(
            "UPDATE users SET company_id = %s WHERE id = %s",
            (company_db_id, user_id),
        )

        # Создаем начальный отдел
        cursor.execute(
            """INSERT INTO departments (
                company_id, name, balance
            ) VALUES (%s, %s, %s)""",
            (
                company_db_id,
                "Основной отдел",
                0.0,
            ),
        )

        conn.commit()

        cursor.execute("SELECT * FROM users WHERE phone = %s", (data.phone,))
        user = cursor.fetchone()

        token_data = {
            "sub": user["login"],
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
            "message": "Регистрация компании успешно завершена",
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "balance": float(user["balance"]),
        }
        response = JSONResponse(content=response_data)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        cursor.close()
        conn.close()
        return response

    except mysql.connector.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")
