from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from typing import List
from ..models import CreateAppealData, AppealResponse, DealStatus
from ..utils.deals_utils import get_stages_map, get_status_style, get_deals, get_deal_categories
from src.utils.jwt_handler import get_token, decode_access_token
import requests
from config import BITRIX_DOMAIN, BITRIX_TOKEN

router = APIRouter()

# ---------- Создание обращения ----------

@router.post("/create", response_model=AppealResponse)
async def create_appeal(appeal_data: CreateAppealData, token: str = Depends(get_token)):
    """Создание нового обращения с динамическим типом и стадией"""
    try:
        user_data = decode_access_token(token)
        contact_id = user_data.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Отсутствует contact_id")

        # Проверяем валидность category_id
        categories = get_deal_categories()
        category_ids = [str(category["id"]) for category in categories]
        if appeal_data.category_id not in category_ids:
            raise HTTPException(status_code=400, detail="Неверный ID категории")

        # Получаем первую доступную стадию для выбранной категории
        stages_map = get_stages_map(appeal_data.category_id)
        if not stages_map:
            raise HTTPException(status_code=400, detail="Нет доступных стадий для выбранной категории")
        
        # Берем первую стадию как начальную
        first_stage_id = list(stages_map.keys())[0]

        # Создаем сделку
        deal_fields = {
            "TITLE": appeal_data.title,
            "CONTACT_ID": contact_id,
            "STAGE_ID": first_stage_id,
            "CATEGORY_ID": appeal_data.category_id,
            "COMMENTS": appeal_data.comment,
            "OPPORTUNITY": "0",
            "CURRENCY_ID": "RUB",
            "OPENED": "Y",
        }

        response = requests.post(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.add.json",
            json={"fields": deal_fields},
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
                {"fileData": [file.name, file.base64]} for file in appeal_data.files
            ]

        requests.post(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.activity.add.json",
            json={"fields": activity_fields},
        )

        return AppealResponse(
            deal_id=deal_id,
            title=deal_fields["TITLE"],
            stage_name=stages_map[first_stage_id],
            created_at=datetime.now(),
            message="Обращение успешно создано",
        )

    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix24: {str(e)}")