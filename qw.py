import asyncpg
import os

# Загружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DB_URI")

async def test_connection():
    conn = await asyncpg.connect(DATABASE_URL)
    print("Подключение установлено!")
    await conn.close()

import asyncio
asyncio.run(test_connection())
