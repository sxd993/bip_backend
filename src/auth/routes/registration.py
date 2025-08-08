from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from src.utils.jwt_handler import create_access_token
from ..utils.password_handler import hash_password
from ..utils.token_utils import generate_company_token
from config import ACCESS_TOKEN_EXPIRE_MINUTES
from database import connect_to_db
import mysql.connector
from ..models import RegisterPhysicalPersonData, RegisterLegalEntityData, RegisterEmployeeData
from ..utils.auth_utils import (
    create_bitrix_contact,
    create_bitrix_company,
    create_bitrix_requisite,
    find_bitrix_contact,
    format_phone_with_plus,
)

router = APIRouter()


@router.post("/register/physical")
async def register_physical_person(data: RegisterPhysicalPersonData):
    """Регистрация физического лица"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Проверка существования пользователя
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

        # Форматируем телефон с "+"
        phone_with_plus = format_phone_with_plus(data.phone)

        # Проверка контакта в Bitrix24
        contact_id = find_bitrix_contact(data.email, phone_with_plus)

        # Хешируем пароль
        hashed_password = hash_password(data.password)

        # Создаем пользователя в БД (телефон сохраняем с "+")
        cursor.execute(
            """INSERT INTO users (
                password, user_type, role, first_name, second_name, 
                last_name, birthdate, phone, email, contact_id, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                hashed_password,
                "physical",
                "Пользователь",
                data.first_name,
                data.second_name,
                data.last_name,
                data.birthdate,
                phone_with_plus,  # Сохраняем с "+"
                data.email,
                contact_id,  # Может быть None
                0.0,
            ),
        )
        user_id = cursor.lastrowid

        # Если контакта нет, создаем в Bitrix24
        if not contact_id:
            contact_data = {
                "NAME": data.first_name,
                "SECOND_NAME": data.second_name,
                "LAST_NAME": data.last_name,
                "BIRTHDATE": data.birthdate,
                "PHONE": [{"VALUE": phone_with_plus, "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
            }
            contact_id = create_bitrix_contact(contact_data)
            if not contact_id:
                conn.rollback()
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=500, detail="Ошибка создания контакта в Bitrix24"
                )

            # Обновляем contact_id
            cursor.execute(
                "UPDATE users SET contact_id = %s WHERE id = %s",
                (contact_id, user_id),
            )

        conn.commit()

        # Получаем пользователя
        cursor.execute("SELECT * FROM users WHERE phone = %s", (phone_with_plus,))
        user = cursor.fetchone()

        # Создаем access_token
        token_data = {
            "user_id": user["id"],
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "contact_id": user["contact_id"],
            "company_id": user.get("company_id"),
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
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")


@router.post("/register/legal")
async def register_legal_entity(data: RegisterLegalEntityData):
    """Регистрация юридического лица (руководитель компании)"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Проверка существования
        cursor.execute(
            """
            SELECT u.id FROM users u WHERE u.phone = %s OR u.email = %s
            UNION
            SELECT c.id FROM companies c WHERE c.inn = %s
            """,
            (data.phone, data.email, data.inn),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=400, detail="Пользователь или компания уже существуют"
            )

        # Форматируем телефон с "+"
        phone_with_plus = format_phone_with_plus(data.phone)

        # Проверка контакта в Bitrix24
        contact_id = find_bitrix_contact(data.email, phone_with_plus)

        # Хешируем пароль
        hashed_password = hash_password(data.password)

        # Создаем пользователя в БД (телефон сохраняем с "+")
        cursor.execute(
            """INSERT INTO users (
                password, user_type, role, first_name, second_name, 
                last_name, phone, email, contact_id, company_id, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                hashed_password,
                "legal",
                "Руководитель",
                data.employee_first_name,
                data.employee_second_name,
                data.employee_last_name,
                phone_with_plus,  # Сохраняем с "+"
                data.email,
                contact_id,  # Может быть None
                None,
                0.0,
            ),
        )
        user_id = cursor.lastrowid

        # Генерируем токен для компании
        company_token = generate_company_token()

        # Создаем компанию в БД с токеном
        cursor.execute(
            """INSERT INTO companies (
                name, inn, invite_token, phone, email, bitrix_company_id, balance, creator_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                data.company_name,
                data.inn,
                company_token,  # Токен для приглашения
                phone_with_plus,  # Сохраняем с "+"
                data.email,
                None,  # bitrix_company_id пока None
                0.0,
                user_id,
            ),
        )
        company_db_id = cursor.lastrowid

        # Создаем компанию в Bitrix24
        company_data = {
            "TITLE": data.company_name,
            "PHONE": [{"VALUE": phone_with_plus, "VALUE_TYPE": "WORK"}],
            "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
        }
        company_id = create_bitrix_company(company_data)
        if not company_id:
            conn.rollback()
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=500, detail="Ошибка создания компании в Bitrix24"
            )

        # Обновляем bitrix_company_id
        cursor.execute(
            "UPDATE companies SET bitrix_company_id = %s WHERE id = %s",
            (company_id, company_db_id),
        )

        # Создаем реквизиты в Bitrix24
        requisite_id = create_bitrix_requisite(company_id, data.inn, data.company_name)
        if not requisite_id:
            conn.rollback()
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=500, detail="Ошибка создания реквизитов в Bitrix24"
            )

        # Если контакта нет, создаем в Bitrix24
        if not contact_id:
            contact_data = {
                "NAME": data.employee_first_name,
                "SECOND_NAME": data.employee_second_name,
                "LAST_NAME": data.employee_last_name,
                "PHONE": [{"VALUE": phone_with_plus, "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
                "COMPANY_ID": company_id,
            }
            contact_id = create_bitrix_contact(contact_data)
            if not contact_id:
                conn.rollback()
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=500, detail="Ошибка создания контакта в Bitrix24"
                )

            # Обновляем contact_id
            cursor.execute(
                "UPDATE users SET contact_id = %s WHERE id = %s",
                (contact_id, user_id),
            )

        # Обновляем company_id в записи пользователя
        cursor.execute(
            "UPDATE users SET company_id = %s WHERE id = %s",
            (company_db_id, user_id),
        )

        conn.commit()

        # Получаем пользователя
        cursor.execute("SELECT * FROM users WHERE phone = %s", (phone_with_plus,))
        user = cursor.fetchone()

        # Создаем access_token
        token_data = {
            "user_id": user["id"],
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "contact_id": user["contact_id"],
            "company_id": user.get("company_id"),
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
            "company_token": company_token,  # Возвращаем токен руководителю
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
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")


@router.post("/register/employee")
async def register_employee(data: RegisterEmployeeData):
    """Регистрация сотрудника компании по токену приглашения"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)

        # Проверка существования пользователя
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

        # Проверяем токен и получаем компанию
        cursor.execute(
            "SELECT id, name, bitrix_company_id FROM companies WHERE invite_token = %s",
            (data.company_token,),
        )
        company = cursor.fetchone()
        
        if not company:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=404,
                detail="Компания с таким токеном не найдена. Проверьте правильность токена",
            )

        # Форматируем телефон с "+"
        phone_with_plus = format_phone_with_plus(data.phone)

        # Проверка контакта в Bitrix24
        contact_id = find_bitrix_contact(data.email, phone_with_plus)

        # Хешируем пароль
        hashed_password = hash_password(data.password)

        # Создаем пользователя в БД как сотрудника
        cursor.execute(
            """INSERT INTO users (
                password, user_type, role, first_name, second_name, 
                last_name, phone, email, contact_id, company_id, 
                position, balance
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                hashed_password,
                "legal",
                "Сотрудник",  # Роль - Сотрудник
                data.first_name,
                data.second_name,
                data.last_name,
                phone_with_plus,
                data.email,
                contact_id,  # Может быть None
                company["id"],  # ID компании из БД
                data.position,  # Должность (фиктивная)
                0.0,
            ),
        )
        user_id = cursor.lastrowid

        # Если контакта нет, создаем в Bitrix24 и привязываем к компании
        if not contact_id:
            contact_data = {
                "NAME": data.first_name,
                "SECOND_NAME": data.second_name,
                "LAST_NAME": data.last_name,
                "PHONE": [{"VALUE": phone_with_plus, "VALUE_TYPE": "WORK"}],
                "EMAIL": [{"VALUE": data.email, "VALUE_TYPE": "WORK"}],
                "COMPANY_ID": company["bitrix_company_id"],  # Привязываем к компании в Bitrix
            }
            contact_id = create_bitrix_contact(contact_data)
            if not contact_id:
                conn.rollback()
                cursor.close()
                conn.close()
                raise HTTPException(
                    status_code=500, detail="Ошибка создания контакта в Bitrix24"
                )

            # Обновляем contact_id
            cursor.execute(
                "UPDATE users SET contact_id = %s WHERE id = %s",
                (contact_id, user_id),
            )

        conn.commit()

        # Получаем пользователя
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        # Создаем access_token
        token_data = {
            "user_id": user["id"],
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "contact_id": user["contact_id"],
            "company_id": user.get("company_id"),
            "position": user.get("position"),
        }
        access_token = create_access_token(token_data, ACCESS_TOKEN_EXPIRE_MINUTES)

        response_data = {
            "message": f"Регистрация успешно завершена. Вы присоединились к компании {company['name']}",
            "user_type": user["user_type"],
            "role": user["role"],
            "first_name": user["first_name"],
            "second_name": user["second_name"],
            "last_name": user["last_name"],
            "position": data.position,
            "company_name": company["name"],
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
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Ошибка базы данных: {str(e)}")
    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")