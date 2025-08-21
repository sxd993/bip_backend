import requests
from config import BITRIX_DOMAIN, BITRIX_TOKEN
from typing import List, Dict

# ---------- Работа с категориями и стадиями ----------

def get_deal_categories() -> List[Dict]:
    """Получает все категории (воронки) сделок из Bitrix24 через crm.category.list"""
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.category.list.json"
    params = {"entityTypeId": 2}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("result", {}).get("categories", [])

def get_pipelines() -> Dict:
    """Получает все воронки и стадии сделок из Bitrix24"""
    categories = get_deal_categories()
    pipelines = {}
    for category in categories:
        category_id = str(category["id"])
        pipelines[category_id] = {
            "NAME": category["name"],
            "STAGES": get_stages_for_category(category_id)
        }
    return pipelines

def get_stages_for_category(category_id: str) -> Dict:
    """Получает стадии для конкретной категории"""
    url = f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.status.list.json"
    params = {"filter[ENTITY_ID]": f"DEAL_STAGE_{category_id}"}
    response = requests.get(url, params=params)
    response.raise_for_status()
    stages = {}
    for stage in response.json().get("result", []):
        stages[stage["STATUS_ID"]] = {"NAME": stage["NAME"]}
    return stages

def get_stages_map(pipeline_id: str) -> Dict[str, str]:
    """Возвращает словарь stage_id -> stage_name для конкретного пайплайна"""
    pipelines = get_pipelines()
    stages_map = {}
    pipeline = pipelines.get(pipeline_id)
    if not pipeline:
        return stages_map
    for stage_id, stage_data in pipeline.get("STAGES", {}).items():
        stages_map[stage_id] = stage_data.get("NAME", "Неизвестно")
    return stages_map

# ---------- Статусы сделок (цвета/иконки) ----------

def get_status_style(stage_name: str) -> tuple[str, str]:
    """Определяет цвет и иконку для статуса"""
    stage_name_lower = stage_name.lower()
    if any(word in stage_name_lower for word in ["нов", "создан"]):
        return "bg-blue-50 text-blue-700 border-blue-200", "📝"
    elif any(word in stage_name_lower for word in ["подготовк", "планирован"]):
        return "bg-yellow-50 text-yellow-700 border-yellow-200", "⚙️"
    elif any(word in stage_name_lower for word in ["оплат", "счет"]):
        return "bg-orange-50 text-orange-700 border-orange-200", "💰"
    elif any(word in stage_name_lower for word in ["выполнен", "в работе"]):
        return "bg-indigo-50 text-indigo-700 border-indigo-200", "🚀"
    elif any(word in stage_name_lower for word in ["завершен", "выигран"]):
        return "bg-green-50 text-green-700 border-green-200", "✅"
    elif any(word in stage_name_lower for word in ["проигран", "отклонен"]):
        return "bg-red-50 text-red-700 border-red-200", "❌"
    else:
        return "bg-gray-50 text-gray-700 border-gray-200", "📝"

# ---------- Сделки пользователя ----------

def get_deals(contact_id: str, closed_filter: str = None) -> List[Dict]:
    """Возвращает сделки конкретного контакта"""
    params = {
        "filter[CONTACT_ID]": contact_id,
        "select[]": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "DATE_CREATE", "CATEGORY_ID"],
        "order[DATE_CREATE]": "DESC",
    }
    if closed_filter:
        params["filter[CLOSED]"] = closed_filter

    response = requests.get(
        f"https://{BITRIX_DOMAIN}/rest/1/{BITRIX_TOKEN}/crm.deal.list.json",
        params=params,
    )
    response.raise_for_status()
    return response.json().get("result", [])