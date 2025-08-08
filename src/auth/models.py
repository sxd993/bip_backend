"""
Модуль models.py
===============

Этот модуль содержит Pydantic модели для валидации данных в API аутентификации.

Модели:
- LoginData: Для входа пользователя
- RegisterPhysicalPersonData: Для регистрации физического лица
- RegisterLegalEntityData: Для регистрации юридического лица (руководитель)
- RegisterEmployeeData: Для регистрации сотрудника компании
"""

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Literal
import re
from dateutil.parser import parse

class LoginData(BaseModel):
    email_or_phone: str
    password: str

class RegisterPhysicalPersonData(BaseModel):
    """Регистрация физического лица"""
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
        return '+' + digits_only

class RegisterLegalEntityData(BaseModel):
    """Регистрация юридического лица (руководитель компании)"""
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

class RegisterEmployeeData(BaseModel):
    """Регистрация сотрудника компании по токену"""
    first_name: str
    second_name: str
    last_name: str
    position: str 
    phone: str
    email: EmailStr
    password: str
    company_token: str  # Токен приглашения от компании

    @validator("phone")
    def validate_phone(cls, v):
        digits_only = re.sub(r"\D", "", v)
        return '+' + digits_only
    
    @validator("company_token")
    def validate_token(cls, v):
        if len(v) != 32:
            raise ValueError("Некорректный токен компании")
        return v