"""
Модуль models.py
===============

Этот модуль содержит Pydantic модели для валидации данных в API аутентификации.

Модели:
- LoginData: Для входа пользователя
- RegisterPhysicalPersonData: Для регистрации физического лица
- RegisterLegalEntityData: Для регистрации юридического лица
- AddEmployeeData: Для добавления сотрудника в компанию
"""

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Literal
import re
from dateutil.parser import parse

class LoginData(BaseModel):
    login: str
    password: str

class RegisterPhysicalPersonData(BaseModel):
    """Регистрация физического лица"""
    login: str
    first_name: str
    second_name: str
    last_name: str
    birthdate: str
    phone: str
    email: EmailStr
    password: str

    @validator("birthdate")
    def validate_birthdate(cls, v):
        try:
            parse(v)
            return v
        except ValueError:
            raise ValueError("Некорректный формат даты рождения")

    @validator("phone")
    def validate_phone(cls, v):
        digits_only = re.sub(r"\D", "", v)
        if not re.match(r"^[78]?\d{10}$", digits_only):
            raise ValueError("Некорректный формат номера телефона")
        if len(digits_only) == 10:
            return "7" + digits_only
        elif digits_only.startswith("8"):
            return "7" + digits_only[1:]
        return digits_only

class RegisterLegalEntityData(BaseModel):
    """Регистрация юридического лица"""
    company_name: str
    inn: str
    employee_first_name: str
    employee_second_name: str
    employee_last_name: str
    phone: str
    email: EmailStr
    password: str

    @validator("inn")
    def validate_inn(cls, v):
        if not re.match(r"^\d{10}$|^\d{12}$", v):
            raise ValueError("ИНН должен содержать 10 или 12 цифр")
        return v

    @validator("phone")
    def validate_phone(cls, v):
        digits_only = re.sub(r"\D", "", v)
        if not re.match(r"^[78]?\d{10}$", digits_only):
            raise ValueError("Некорректный формат номера телефона")
        if len(digits_only) == 10:
            return "7" + digits_only
        elif digits_only.startswith("8"):
            return "7" + digits_only[1:]
        return digits_only

class AddEmployeeData(BaseModel):
    """Добавление сотрудника в компанию"""
    first_name: str
    second_name: str
    last_name: str
    phone: str
    email: EmailStr
    password: str
    role: Literal["Сотрудник", "Руководитель отдела"]
    department_id: Optional[int] = None

    @validator("department_id")
    def validate_department_id(cls, v, values):
        if "role" in values and values["role"] == "Сотрудник" and v is None:
            raise ValueError("Для роли 'Сотрудник' необходимо указать department_id")
        return v