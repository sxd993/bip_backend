from fastapi import APIRouter
from .routes.create_appeals import router as create_appeals_router
from .routes.get_deals import router as get_deals_router

router = APIRouter()

# Подключаем все подмодули
router.include_router(create_appeals_router, tags=["create-appeals"])
router.include_router(get_deals_router, tags=["get-deals"])