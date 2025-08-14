"""
API маршруты для создания обращений и управления сделками
"""

from fastapi import APIRouter, HTTPException, Depends
import requests
from typing import List
from datetime import datetime

from src.utils.jwt_handler import get_token, decode_access_token
from config import BITRIX_DOMAIN, BITRIX_TOKEN
from ..models import CreateAppealData, AppealResponse, DealStatus

router = APIRouter()

# Маппинг типов обращений на воронки/стадии Bitrix
APPEAL_TYPE_MAPPING = {
    "DEBTOR": {
        "category_id": "1",  # ID категории в Bitrix для дебиторки
        "stage_id": "NEW",   # Начальная стадия
        "title_prefix": "Дебиторская задолженность: "
    },
    "GENERAL": {
        "category_id": "0",  # ID категории в Bitrix для общих вопросов
        "stage_id": "NEW",
        "title_prefix": "Общий вопрос: "
    }
}

@router.post("/create", response_model=AppealResponse)
async def create_appeal(
    appeal_data: CreateAppealData,
    token: str = Depends(get_token)
):
    """Создание нового обращения"""
    try:
        # Декодируем токен пользователя
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        
        if not contact_id:
            raise HTTPException(
                status_code=400,
                detail="У пользователя отсутствует contact_id в Bitrix24"
            )
        
        # Получаем маппинг для типа обращения
        appeal_config = APPEAL_TYPE_MAPPING.get(appeal_data.appeal_type)
        if not appeal_config:
            raise HTTPException(
                status_code=400,
                detail="Неподдерживаемый тип обращения"
            )
        
        # Формируем заголовок сделки
        deal_title = appeal_config["title_prefix"] + appeal_data.title
        
        # Подготавливаем файлы для Bitrix
        files_data = []
        if appeal_data.files:
            for file in appeal_data.files:
                files_data.append({
                    "fileData": [file.name, file.base64]
                })
        
        # Создаем сделку в Bitrix24
        deal_fields = {
            "TITLE": deal_title,
            "CONTACT_ID": contact_id,
            "STAGE_ID": appeal_config["stage_id"],
            "CATEGORY_ID": appeal_config["category_id"],
            "COMMENTS": appeal_data.comment,
            "OPPORTUNITY": "0",  # Сумма сделки пока 0
            "CURRENCY_ID": "RUB",
            "OPENED": "Y",  # Сделка открыта для клиента
        }
        
        # Если есть компания у пользователя, добавляем её
        company_id = user_data.get("company_id")
        if company_id:
            # Получаем bitrix_company_id из БД
            from database import connect_to_db
            conn = connect_to_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT bitrix_company_id FROM companies WHERE id = %s",
                (company_id,)
            )
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
        
        deal_result = response.json()
        if not deal_result.get("result"):
            raise HTTPException(
                status_code=500,
                detail="Ошибка создания сделки в Bitrix24"
            )
        
        deal_id = str(deal_result["result"])
        
        # Добавляем первоначальный комментарий как активность
        activity_fields = {
            "OWNER_TYPE_ID": 2,  # Тип: сделка
            "OWNER_ID": deal_id,
            "TYPE_ID": 4,  # Тип: комментарий
            "SUBJECT": "Создано обращение",
            "DESCRIPTION": appeal_data.comment,
            "COMPLETED": "Y",
            "AUTHOR_ID": contact_id,
        }
        
        # Если есть файлы, добавляем их к активности
        if files_data:
            activity_fields["FILES"] = files_data
        
        activity_response = requests.post(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.activity.add.json",
            json={"fields": activity_fields}
        )
        activity_response.raise_for_status()
        
        # Получаем информацию о созданной сделке
        deal_info_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.get.json",
            params={
                "id": deal_id,
                "select[]": ["ID", "TITLE", "STAGE_ID", "DATE_CREATE"]
            }
        )
        deal_info_response.raise_for_status()
        deal_info = deal_info_response.json().get("result", {})
        
        # Получаем название стадии
        stage_name = await get_stage_name(deal_info.get("STAGE_ID", ""))
        
        return AppealResponse(
            deal_id=deal_id,
            title=deal_title,
            stage_name=stage_name,
            created_at=datetime.now(),
            message="Обращение успешно создано"
        )
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка API Bitrix24: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Непредвиденная ошибка: {str(e)}"
        )

@router.get("/current", response_model=List[DealStatus])
async def get_current_deals(token: str = Depends(get_token)):
    """Получение текущих активных сделок"""
    try:
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        
        if not contact_id:
            raise HTTPException(
                status_code=400,
                detail="У пользователя отсутствует contact_id"
            )
        
        # Получаем активные сделки (не завершенные)
        deals_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
            params={
                "filter[CONTACT_ID]": contact_id,
                "filter[CLOSED]": "N",  # Только открытые сделки
                "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE"],
                "order[DATE_CREATE]": "DESC"
            }
        )
        deals_response.raise_for_status()
        
        deals = deals_response.json().get("result", [])
        
        # Получаем названия стадий
        stages_map = await get_stages_map()
        
        current_deals = []
        for deal in deals:
            stage_name = stages_map.get(deal.get("STAGE_ID", ""), "Неизвестно")
            
            current_deals.append(DealStatus(
                id=deal["ID"],
                title=deal["TITLE"],
                stage_id=deal["STAGE_ID"],
                stage_name=stage_name,
                created_at=deal["DATE_CREATE"],
                opportunity=deal.get("OPPORTUNITY", "0")
            ))
        
        return current_deals
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка API Bitrix24: {str(e)}"
        )

@router.get("/history", response_model=List[DealStatus])
async def get_deals_history(token: str = Depends(get_token)):
    """Получение истории всех сделок"""
    try:
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        
        if not contact_id:
            raise HTTPException(
                status_code=400,
                detail="У пользователя отсутствует contact_id"
            )
        
        # Получаем все сделки пользователя
        deals_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
            params={
                "filter[CONTACT_ID]": contact_id,
                "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE", "CLOSED"],
                "order[DATE_CREATE]": "DESC"
            }
        )
        deals_response.raise_for_status()
        
        deals = deals_response.json().get("result", [])
        
        # Получаем названия стадий
        stages_map = await get_stages_map()
        
        history_deals = []
        for deal in deals:
            stage_name = stages_map.get(deal.get("STAGE_ID", ""), "Неизвестно")
            
            history_deals.append(DealStatus(
                id=deal["ID"],
                title=deal["TITLE"],
                stage_id=deal["STAGE_ID"],
                stage_name=stage_name,
                created_at=deal["DATE_CREATE"],
                opportunity=deal.get("OPPORTUNITY", "0")
            ))
        
        return history_deals
        
    except requests.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка API Bitrix24: {str(e)}"
        )

# Вспомогательные функции
async def get_stage_name(stage_id: str) -> str:
    """Получение названия стадии по ID"""
    try:
        stages_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.status.list.json",
            params={"filter[ENTITY_ID]": ["DEAL_STAGE", "DEAL_STAGE_4"]}
        )
        stages_response.raise_for_status()
        
        stages = stages_response.json().get("result", [])
        for stage in stages:
            if stage.get("STATUS_ID") == stage_id:
                return stage.get("NAME", "Неизвестно")
        
        return "Неизвестно"
    except:
        return "Неизвестно"

async def get_stages_map() -> dict:
    """Получение маппинга стадий ID -> Название"""
    try:
        stages_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.status.list.json",
            params={"filter[ENTITY_ID]": ["DEAL_STAGE", "DEAL_STAGE_4"]}
        )
        stages_response.raise_for_status()
        
        stages = stages_response.json().get("result", [])
        return {
            stage["STATUS_ID"]: stage["NAME"]
            for stage in stages
            if stage.get("STATUS_ID") and stage.get("NAME")
        }
    except:
        return {}