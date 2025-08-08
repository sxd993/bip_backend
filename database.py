"""
Модуль database.py
==================

Этот модуль предоставляет функцию для подключения к базе данных MySQL с SSL.

Зависимости:
- mysql.connector
- fastapi
- os (для работы с путями)
"""

import os
import mysql.connector
from fastapi import HTTPException
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME


def connect_to_db():
    """
    Подключение к базе данных MySQL с SSL сертификатом.
    
    Returns:
        mysql.connector.connection.MySQLConnection: Объект подключения к БД
        
    Raises:
        HTTPException: При ошибке подключения к базе данных
    """
    try:
        # Получаем путь к корневой директории проекта
        root_dir = os.path.dirname(os.path.abspath(__file__))
        ca_cert_path = os.path.join(root_dir, 'ca.crt')
        
        # Проверяем существование сертификата
        if not os.path.exists(ca_cert_path):
            raise FileNotFoundError(f"SSL сертификат не найден: {ca_cert_path}")
        
        # SSL конфигурация
        ssl_config = {
            'ca': ca_cert_path,
            'verify_cert': True,
            'verify_identity': True,
        }
        
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            ssl_disabled=False,
            ssl_ca=ca_cert_path, 
            ssl_verify_cert=True,  
            ssl_verify_identity=True,  
        )
        
        # Проверяем, что соединение действительно использует SSL
        if conn.is_connected():
            cursor = conn.cursor()
            cursor.execute("SHOW STATUS LIKE 'Ssl_cipher'")
            ssl_status = cursor.fetchone()
            cursor.close()
            
            if ssl_status and ssl_status[1]:
                print(f"SSL подключение установлено. Cipher: {ssl_status[1]}")
            else:
                raise mysql.connector.Error("SSL соединение не установлено")
        
        return conn
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"SSL certificate error: {str(e)}"
        )
    except mysql.connector.Error as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Database connection error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error: {str(e)}"
        )
