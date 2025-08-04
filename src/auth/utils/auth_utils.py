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

def format_phone_with_plus(phone: str) -> str:
    """Форматирует номер телефона с добавлением '+'"""
    normalized = normalize_phone(phone)
    return f"+{normalized}"

def find_bitrix_contact(email: str, phone: str) -> str | None:
    """Проверяет существование контакта в Bitrix24 по email и телефону"""
    phone_with_plus = format_phone_with_plus(phone)
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.contact.list.json"
    params = {
        "filter[PHONE]": phone_with_plus,
        "filter[EMAIL]": email,
        "select[]": ["ID", "PHONE", "EMAIL"]
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        contacts = response.json().get("result", [])

        if not contacts:
            return None

        for contact in contacts:
            contact_id = contact.get("ID")
            emails = contact.get("EMAIL", [])
            phones = contact.get("PHONE", [])

            email_match = any(e.get("VALUE", "").lower() == email.lower() for e in emails)
            phone_match = any(p.get("VALUE", "") == phone_with_plus for p in phones)

            if email_match and phone_match:
                return contact_id

            elif email_match or phone_match:
                return contact_id

        return None

    except requests.RequestException as e:
        return None
