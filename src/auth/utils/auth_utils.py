import requests
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