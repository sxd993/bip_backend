"""
Модуль database.py
==================

Этот модуль предоставляет функцию для подключения к базе данных MySQL.

Зависимости:
- mysql.connector
- fastapi
"""

import mysql.connector
from fastapi import HTTPException
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


def connect_to_db():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        return conn
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500, detail=f"Database connection error: {str(e)}"
        )
