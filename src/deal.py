"""
Модуль deal.py
==============

Этот модуль реализует API для работы с одной сделкой в Bitrix24 через FastAPI.

Функционал:
- Получение информации о конкретной сделке по её идентификатору (эндпоинт /get-deal)

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
from utils.jwt_handler import get_token, decode_access_token
from config import BITRIX_DOMAIN, BITRIX_TOKEN

router = APIRouter()


class DealById(BaseModel):
    deal_id: str


# Эндпоинт для получения одной сделки
@router.post("/get-deal")
async def get_deal(deal_data: DealById, token: str = Depends(get_token)):
    try:
        decode_access_token(token)
        if not deal_data.deal_id:
            raise HTTPException(status_code=422, detail="deal_id cannot be empty")

        # Запрос статусов для маппинга STAGE_ID -> NAME
        stages_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.status.list.json",
            params={"filter[ENTITY_ID]": ["DEAL_STAGE", "DEAL_STAGE_4"]},
        )
        stages_response.raise_for_status()
        stages = stages_response.json().get("result", [])

        # Создаем маппинг STATUS_ID -> NAME
        stage_map = {
            stage["STATUS_ID"]: stage["NAME"]
            for stage in stages
            if stage["ENTITY_ID"] in ["DEAL_STAGE", "DEAL_STAGE_4"]
        }

        # Запрос одной сделки
        deal_response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.get.json",
            params={
                "id": deal_data.deal_id,
                "select[]": [
                    "ID",
                    "TITLE",
                    "STAGE_ID",
                    "OPPORTUNITY",
                    "DATE_CREATE",
                    "COMMENTS",
                ],
            },
        )
        deal_response.raise_for_status()
        deal = deal_response.json().get("result", {})

        # Замена STAGE_ID на название из маппинга
        deal["STAGE_NAME"] = stage_map.get(deal["STAGE_ID"], deal["STAGE_ID"])

        return deal
    except requests.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Bitrix API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
