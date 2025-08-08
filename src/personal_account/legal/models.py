from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Literal


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