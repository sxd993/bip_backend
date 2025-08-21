"""
Модуль deals.py
===============

Этот модуль реализует API для работы со списком сделок в Bitrix24 через FastAPI.

Функционал:
- Получение списка сделок по идентификатору контакта (эндпоинты /get-deals, /current)
- Получение списка воронок и стадий (эндпоинт /stages)
- Создание новых обращений (эндпоинт /create)
- Управление текущими и историческими сделками

Зависимости:
- FastAPI
- requests
- pydantic
- utils.jwt_handler (get_token, decode_access_token)
- config (BITRIX_DOMAIN, BITRIX_TOKEN)

"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import requests
from src.utils.jwt_handler import get_token, decode_access_token
from ..utils.deals_utils import get_deal_categories, get_stages_map
from config import BITRIX_DOMAIN, BITRIX_TOKEN

class DealFilter(BaseModel):
    contact_id: str

router = APIRouter()

# Подключаем маршруты создания обращений
from .create_appeals import router as create_router
router.include_router(create_router)

@router.get("/get-deals")
async def get_deals(token: str = Depends(get_token)):
    """Получение сделок пользователя (legacy endpoint)"""
    try:
        decoded_token = decode_access_token(token)
        contact_id = decoded_token.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=422, detail="contact_id missing in token")

        deals_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
            params={
                "filter[CONTACT_ID]": contact_id,
                "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE", "CATEGORY_ID"],
            },
        )
        deals_response.raise_for_status()
        deals = deals_response.json().get("result", [])

        for deal in deals:
            stages_map = get_stages_map(deal["CATEGORY_ID"])
            deal["STAGE_NAME"] = stages_map.get(deal["STAGE_ID"], deal["STAGE_ID"])

        return deals

    except requests.RequestException:
        raise HTTPException(status_code=500, detail="Bitrix24 request error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@router.get("/stages")
async def get_deal_stages():
    """Получение списка воронок и их стадий"""
    try:
        categories = get_deal_categories()
        funnels = []
        for category in categories:
            category_id = str(category["id"])
            stages_map = get_stages_map(category_id)
            funnels.append({
                "id": category_id,
                "name": category["name"],
                "stages": [{"id": stage_id, "name": stage_name} for stage_id, stage_name in stages_map.items()]
            })
        return funnels
    except requests.RequestException:
        raise HTTPException(status_code=500, detail="Bitrix24 request error")

@router.get("/current")
async def get_current_deals(token: str = Depends(get_token)):
    """Получение текущих (открытых) сделок пользователя"""
    try:
        decoded_token = decode_access_token(token)
        contact_id = decoded_token.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=422, detail="contact_id missing in token")

        # Получаем категории для маппинга названий воронок
        categories = get_deal_categories()
        category_map = {str(category["id"]): category["name"] for category in categories}

        # Запрашиваем текущие сделки (CLOSED="N")
        deals_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
            params={
                "filter[CONTACT_ID]": contact_id,
                "filter[CLOSED]": "N",
                "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE", "CATEGORY_ID"],
                "order[DATE_CREATE]": "DESC",
            },
        )
        deals_response.raise_for_status()
        deals = deals_response.json().get("result", [])

        # Формируем ответ с названиями воронок и стадий
        result = []
        for deal in deals:
            category_id = deal.get("CATEGORY_ID", "0")
            stages_map = get_stages_map(category_id)
            result.append({
                "id": deal["ID"],
                "title": deal["TITLE"],
                "category_id": category_id,
                "category_name": category_map.get(category_id, "Неизвестная воронка"),
                "stage_id": deal["STAGE_ID"],
                "stage_name": stages_map.get(deal["STAGE_ID"], deal["STAGE_ID"]),
                "opportunity": deal.get("OPPORTUNITY", "0"),
                "created_at": deal["DATE_CREATE"],
            })

        return result

    except requests.RequestException:
        raise HTTPException(status_code=500, detail="Bitrix24 request error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")