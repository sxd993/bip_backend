"""
Модели для системы сделок и обращений
"""

from pydantic import BaseModel, validator
from typing import Optional, List, Literal
from datetime import datetime

class FileUpload(BaseModel):
    """Модель для загружаемого файла"""
    name: str
    base64: str
    size: Optional[int] = None
    
    @validator('base64')
    def validate_base64(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Файл поврежден или пустой')
        return v

class CreateAppealData(BaseModel):
    """Создание нового обращения"""
    appeal_type: Literal["DEBTOR", "GENERAL"]  # Дебиторка или общий
    title: str
    comment: str
    files: Optional[List[FileUpload]] = []
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Заголовок должен содержать минимум 3 символа')
        return v.strip()
    
    @validator('comment')
    def validate_comment(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Комментарий должен содержать минимум 10 символов')
        return v.strip()

class AppealResponse(BaseModel):
    """Ответ при создании обращения"""
    deal_id: str
    title: str
    stage_name: str
    created_at: datetime
    message: str

class DealStatus(BaseModel):
    """Статус сделки"""
    id: str
    title: str
    stage_id: str
    stage_name: str
    created_at: str
    opportunity: Optional[str] = "0"
    last_activity: Optional[str] = None