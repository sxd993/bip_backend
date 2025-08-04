"""
Модуль main.py
==============

Функционал:
    - Это основной исполняемый файл для запуска API.
    - Определяет основные маршруты и настройки API.
    - Обрабатывает CORS запросы.
    - Запускает приложение через uvicorn.

"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.auth.routes.authentication import router as auth_router
from src.personal_account.routes.personal_account import router as personal_account_router
from src.transactions.routes.transactions import router as transactions_router
from src.user.routes.user import router as user_router
from src.deals.routes.deals import router as deals_router

from config import CORS_ORIGINS


app = FastAPI(
    title="BIP API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Admin-Request"],
)

# Маршруты
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(personal_account_router, prefix="/personal_account", tags=["Personal Account"])
app.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])
app.include_router(user_router, prefix="/user", tags=["User"])
app.include_router(deals_router, prefix="/deals", tags=["Deals"])



@app.get("/api", tags=["Root"])
async def root():
    return {
        "message": "BIP API is running",
        "version": app.version,
        "status": "healthy",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
