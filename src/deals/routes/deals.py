"""
Модуль deals.py
===============

Этот модуль реализует API для работы со списком сделок в Bitrix24 через FastAPI.

Функционал:
- Получение списка сделок по идентификатору контакта (эндпоинт /get-deals)
- Получение и расшифровка статусов сделок

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
from config import BITRIX_DOMAIN, BITRIX_TOKEN


class DealFilter(BaseModel):
    contact_id: str


router = APIRouter()


@router.get("/get-deals")
async def get_deals(token: str = Depends(get_token)):
    try:
        decoded_token = decode_access_token(token)
        contact_id = decoded_token.get("contact_id")
        if not contact_id:
            raise HTTPException(status_code=422, detail="contact_id missing in token")

        stages_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.status.list.json",
            params={"filter[ENTITY_ID]": ["DEAL_STAGE", "DEAL_STAGE_4"]},
        )
        stages_response.raise_for_status()
        stages = stages_response.json().get("result", [])

        stage_map = {
            stage["STATUS_ID"]: stage["NAME"]
            for stage in stages
            if stage["ENTITY_ID"] in ["DEAL_STAGE", "DEAL_STAGE_4"]
        }

        deals_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
            params={
                "filter[CONTACT_ID]": contact_id,
                "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE"],
            },
        )
        deals_response.raise_for_status()
        deals = deals_response.json().get("result", [])

        for deal in deals:
            deal["STAGE_NAME"] = stage_map.get(deal["STAGE_ID"], deal["STAGE_ID"])

        return deals

    except requests.RequestException:
        raise HTTPException(status_code=500, detail="Bitrix24 request error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")