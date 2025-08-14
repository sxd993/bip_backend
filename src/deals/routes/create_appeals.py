"""
API маршруты для создания обращений и управления сделками
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from pydantic import BaseModel
from src.utils.jwt_handler import get_token, decode_access_token
import requests
from config import BITRIX_DOMAIN, BITRIX_TOKEN

router = APIRouter()

# Модели
class CreateAppealData(BaseModel):
    appeal_type: str
    title: str
    comment: str
    files: List[dict] = []

class AppealResponse(BaseModel):
    deal_id: str
    title: str
    stage_name: str
    created_at: datetime
    message: str

class DealStatus(BaseModel):
    id: str
    title: str
    stage_id: str
    stage_name: str
    created_at: str
    opportunity: str
    status_color: str = "bg-blue-50 text-blue-700 border-blue-200"
    status_icon: str = "📝"

# Конфигурация
APPEAL_TYPE_MAPPING = {
    "DEBTOR": {"category_id": "1", "title_prefix": "Дебиторская задолженность: "},
    "GENERAL": {"category_id": "0", "title_prefix": "Общий вопрос: "}
}

# Вспомогательные функции
def get_status_style(stage_name: str) -> tuple[str, str]:
    """Определяет цвет и иконку для статуса"""
    stage_name_lower = stage_name.lower()
    
    if any(word in stage_name_lower for word in ['нов', 'создан']):
        return "bg-blue-50 text-blue-700 border-blue-200", "📝"
    elif any(word in stage_name_lower for word in ['подготовк', 'планирован']):
        return "bg-yellow-50 text-yellow-700 border-yellow-200", "⚙️"
    elif any(word in stage_name_lower for word in ['оплат', 'счет']):
        return "bg-orange-50 text-orange-700 border-orange-200", "💰"
    elif any(word in stage_name_lower for word in ['выполнен', 'в работе']):
        return "bg-indigo-50 text-indigo-700 border-indigo-200", "🚀"
    elif any(word in stage_name_lower for word in ['завершен', 'выигран']):
        return "bg-green-50 text-green-700 border-green-200", "✅"
    elif any(word in stage_name_lower for word in ['проигран', 'отклонен']):
        return "bg-red-50 text-red-700 border-red-200", "❌"
    else:
        return "bg-gray-50 text-gray-700 border-gray-200", "📝"

async def get_stages_map() -> dict:
    """Получает маппинг статусов ID -> Название"""
    try:
        response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.status.list.json",
            params={"filter[ENTITY_ID]": "DEAL_STAGE"}
        )
        response.raise_for_status()
        
        stages = response.json().get("result", [])
        return {
            stage["STATUS_ID"]: stage["NAME"]
            for stage in stages
            if stage.get("STATUS_ID") and stage.get("NAME")
        }
    except:
        return {}

async def get_deals_with_stages(contact_id: str, closed_filter: str = None) -> List[DealStatus]:
    """Получает сделки с статусами"""
    # Параметры запроса
    params = {
        "filter[CONTACT_ID]": contact_id,
        "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE"],
        "order[DATE_CREATE]": "DESC"
    }
    if closed_filter:
        params["filter[CLOSED]"] = closed_filter
    
    # Получаем сделки
    deals_response = requests.get(
        f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
        params=params
    )
    deals_response.raise_for_status()
    deals = deals_response.json().get("result", [])
    
    # Получаем статусы
    stages_map = await get_stages_map()
    
    # Формируем результат
    result = []
    for deal in deals:
        stage_id = deal.get("STAGE_ID", "")
        stage_name = stages_map.get(stage_id, "Неизвестно")
        status_color, status_icon = get_status_style(stage_name)
        
        result.append(DealStatus(
            id=deal["ID"],
            title=deal["TITLE"],
            stage_id=stage_id,
            stage_name=stage_name,
            created_at=deal["DATE_CREATE"],
            opportunity=deal.get("OPPORTUNITY", "0"),
            status_color=status_color,
            status_icon=status_icon
        ))
    
    return result

# API endpoints
@router.get("/stages")
async def get_deal_stages():
    """Получение всех статусов сделок"""
    try:
        stages_map = await get_stages_map()
        stages = [
            {"id": k, "name": v, "sort": 0}
            for k, v in stages_map.items()
        ]
        return {"stages": stages, "total": len(stages)}
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix24: {str(e)}")

@router.get("/current", response_model=List[DealStatus])
async def get_current_deals(token: str = Depends(get_token)):
    """Получение текущих активных сделок"""
    try:
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Отсутствует contact_id")
        
        return await get_deals_with_stages(contact_id, "N")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix24: {str(e)}")

@router.get("/history", response_model=List[DealStatus])
async def get_deals_history(token: str = Depends(get_token)):
    """Получение истории всех сделок"""
    try:
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Отсутствует contact_id")
        
        return await get_deals_with_stages(contact_id)
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix24: {str(e)}")

@router.post("/create", response_model=AppealResponse)
async def create_appeal(appeal_data: CreateAppealData, token: str = Depends(get_token)):
    """Создание нового обращения"""
    try:
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Отсутствует contact_id")
        
        appeal_config = APPEAL_TYPE_MAPPING.get(appeal_data.appeal_type)
        if not appeal_config:
            raise HTTPException(status_code=400, detail="Неподдерживаемый тип обращения")
        
        # Создаем сделку
        deal_fields = {
            "TITLE": appeal_config["title_prefix"] + appeal_data.title,
            "CONTACT_ID": contact_id,
            "STAGE_ID": "NEW",  # Простой способ - используем "NEW"
            "CATEGORY_ID": appeal_config["category_id"],
            "COMMENTS": appeal_data.comment,
            "OPPORTUNITY": "0",
            "CURRENCY_ID": "RUB",
            "OPENED": "Y",
        }
        
        # Добавляем компанию если есть
        company_id = user_data.get("company_id")
        if company_id:
            from database import connect_to_db
            conn = connect_to_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT bitrix_company_id FROM companies WHERE id = %s", (company_id,))
            company_data = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if company_data and company_data.get("bitrix_company_id"):
                deal_fields["COMPANY_ID"] = company_data["bitrix_company_id"]
        
        # Создаем сделку
        response = requests.post(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.add.json",
            json={"fields": deal_fields}
        )
        response.raise_for_status()
        
        deal_id = str(response.json().get("result"))
        if not deal_id:
            raise HTTPException(status_code=500, detail="Ошибка создания сделки")
        
        # Добавляем активность
        activity_fields = {
            "OWNER_TYPE_ID": 2,
            "OWNER_ID": deal_id,
            "TYPE_ID": 4,
            "SUBJECT": "Создано обращение",
            "DESCRIPTION": appeal_data.comment,
            "COMPLETED": "Y",
            "AUTHOR_ID": contact_id,
        }
        
        if appeal_data.files:
            activity_fields["FILES"] = [
                {"fileData": [file.name, file.base64]} 
                for file in appeal_data.files
            ]
        
        requests.post(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.activity.add.json",
            json={"fields": activity_fields}
        )
        
        return AppealResponse(
            deal_id=deal_id,
            title=deal_fields["TITLE"],
            stage_name="Новая",
            created_at=datetime.now(),
            message="Обращение успешно создано"
        )
        
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix24: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Непредвиденная ошибка: {str(e)}")