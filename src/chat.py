"""
Модуль chat.py
==============

Этот модуль реализует API для чата по сделке в Bitrix24 через FastAPI.

Функционал:
- Получение сообщений (комментариев) по конкретной сделке Bitrix24 (эндпоинт /get-activities)
- Добавление нового сообщения (комментария) к сделке (эндпоинт /add-activity)

Каждое сообщение в чате — это комментарий, который сохраняется как активность типа "Комментарий" в Bitrix24, а также может содержать файлы.

Зависимости:
- FastAPI
- requests
- pydantic
- utils.jwt_handler (get_token, decode_access_token)
- config (BITRIX_DOMAIN, BITRIX_TOKEN)

"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import requests
from utils.jwt_handler import get_token, decode_access_token
from config import BITRIX_DOMAIN, BITRIX_TOKEN

router = APIRouter()


class DealById(BaseModel):
    deal_id: str


class AddActivity(BaseModel):
    deal_id: str
    comment: Optional[str] = None
    files: Optional[list[dict]] = None
    author_name: Optional[str] = None
    author_id: Optional[int] = None


@router.post("/get-activities")
async def get_activities(deal_data: DealById, token: str = Depends(get_token)):
    try:
        decode_access_token(token)
        if not deal_data.deal_id:
            raise HTTPException(status_code=422, detail="deal_id не может быть пустым")

        response = requests.get(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.activity.list.json",
            params={
                "filter[OWNER_TYPE_ID]": 2,
                "filter[OWNER_ID]": deal_data.deal_id,
                "select[]": [
                    "ID",
                    "SUBJECT",
                    "COMMUNICATIONS",
                    "DESCRIPTION",
                    "FILES",
                    "CREATED",
                    "AUTHOR_ID",
                    "STORAGE_ELEMENT_IDS",
                ],
            },
        )
        response.raise_for_status()
        activities = response.json().get("result", [])

        for activity in activities:
            if activity.get("COMMUNICATIONS") and activity["COMMUNICATIONS"]:
                activity["TEXT"] = activity["COMMUNICATIONS"][0].get("VALUE", "")
            else:
                activity["TEXT"] = activity.get("DESCRIPTION", "")

            if activity.get("FILES"):
                for file in activity["FILES"]:
                    file_name = file.get("NAME", f"file_{file.get('id', 'unknown')}")
                    file_url = file.get("url", file.get("URL", ""))
                    file_id = file.get("id")
                    if file_id:
                        try:
                            file_response = requests.get(
                                f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/disk.file.get.json",
                                params={"id": file_id},
                            )
                            file_response.raise_for_status()
                            file_data = file_response.json().get("result", {})
                            file_name = file_data.get("NAME", file_name)
                            file_url = file_data.get("DOWNLOAD_URL", file_url)
                        except requests.HTTPError as e:
                            pass
                    file["NAME"] = file_name
                    file["URL"] = file_url
                    if not file.get("ID"):
                        file["ID"] = f"temp_{hash(file_name)}"
        return activities
    except requests.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")


@router.post("/add-activity")
async def add_activity(activity_data: AddActivity, token: str = Depends(get_token)):
    try:
        decoded_token = decode_access_token(token)
        if not activity_data.deal_id:
            raise HTTPException(status_code=422, detail="deal_id не может быть пустым")
        if not activity_data.comment and not activity_data.files:
            raise HTTPException(
                status_code=422, detail="Необходимо указать комментарий или файлы"
            )

        files = []
        if activity_data.files:
            for file in activity_data.files:
                files.append(
                    {
                        "fileData": [file["name"], file["base64"]],
                        "fileName": file["name"],
                    }
                )

        comment = activity_data.comment or ""
        subject = activity_data.author_name or "Комментарий клиента"
        author_id = activity_data.author_id or decoded_token.get("contact_id", "")

        response = requests.post(
            f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.activity.add.json",
            json={
                "fields": {
                    "OWNER_TYPE_ID": 2,
                    "OWNER_ID": activity_data.deal_id,
                    "TYPE_ID": 4,
                    "SUBJECT": subject,
                    "COMMUNICATIONS": [{"VALUE": comment, "ENTITY_TYPE_ID": 2}],
                    "FILES": files if files else None,
                    "COMPLETED": "Y",
                    "AUTHOR_ID": author_id,
                }
            },
        )
        response.raise_for_status()
        activity_id = response.json().get("result")

        if files:
            file_updates = [
                {
                    "ID": str(index + 1),
                    "NAME": f["fileData"][0],
                    "fileName": f["fileData"][0],
                }
                for index, f in enumerate(files)
            ]
            update_response = requests.post(
                f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.activity.update.json",
                json={
                    "id": activity_id,
                    "fields": {"FILES": file_updates},
                },
            )
            update_response.raise_for_status()

        return {"success": True}
    except requests.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Bitrix API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")
