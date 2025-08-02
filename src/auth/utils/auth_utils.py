import requests
import re
from config import BITRIX_DOMAIN, BITRIX_TOKEN

# Вспомогательные функции
def create_bitrix_contact(data: dict) -> int | None:
    """Создание контакта в Bitrix24"""
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.contact.add.json"
    response = requests.post(url, json={"fields": data})

    if response.status_code == 200 and response.json().get("result"):
        return response.json()["result"]
    return None


def create_bitrix_company(data: dict) -> int | None:
    """Создание компании в Bitrix24"""
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.company.add.json"
    response = requests.post(url, json={"fields": data})

    if response.status_code == 200 and response.json().get("result"):
        return response.json()["result"]
    return None

    
def create_bitrix_requisite(company_id: int, inn: str, company_name: str) -> int | None:
    """Создание реквизитов компании в Bitrix24"""
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.requisite.add.json"
    data = {
        "fields": {
            "ENTITY_TYPE_ID": "4",  # Тип сущности: компания
            "ENTITY_ID": company_id,
            "PRESET_ID": "1",  # Пресет "Организация"
            "NAME": f"Реквизиты {company_name}",
            "ACTIVE": "Y",
            "RQ_INN": inn,
            "RQ_COMPANY_NAME": company_name,
            "RQ_COMPANY_FULL_NAME": company_name,
        }
    }
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        result = response.json()
        if "result" in result:
            return result["result"]
        else:
            print(f"Ошибка Bitrix24: {result.get('error', 'Неизвестная ошибка')} - {result.get('error_description', '')}")
    else:
        print(f"HTTP ошибка: {response.status_code}, {response.text}")
    return None

def normalize_phone(phone: str) -> str:
    """Оставляет только цифры из номера телефона"""
    return re.sub(r"\D", "", phone)

def find_bitrix_contact(email: str, phone: str):
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.contact.list.json"
    # Поиск по email
    params = {
        "filter": {"EMAIL": email},
        "select": ["ID"]
    }
    r = requests.post(url, json=params)
    result = r.json().get("result", [])
    if result:
        return result[0]["ID"]
    # Поиск по всем контактам и сравнение телефонов вручную
    params = {
        "select": ["ID", "PHONE"]
    }
    r = requests.post(url, json=params)
    contacts = r.json().get("result", [])
    phone_norm = normalize_phone(phone)
    for contact in contacts:
        phones = contact.get("PHONE", [])
        for ph in phones:
            if normalize_phone(ph.get("VALUE", "")) == phone_norm:
                return contact["ID"]
    return None