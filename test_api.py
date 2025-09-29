# test_api.py

import os
import httpx
from dotenv import load_dotenv
import logging
import asyncio

# Загружаем переменные из .env
load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# Конфигурация API
API_KEY ='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'
MODEL = "deepseek/deepseek-r1:free"
SITE_URL = os.getenv("SITE_URL")      # Опционально
SITE_NAME = os.getenv("SITE_NAME")    # Опционально

async def simple_test():
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # Добавляем опциональные заголовки, если они предоставлены
    if SITE_URL:
        headers["HTTP-Referer"] = SITE_URL
    if SITE_NAME:
        headers["X-Title"] = SITE_NAME

    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "What is the meaning of life?"}],
        "temperature": 0.7,
        "max_tokens": 1000,
        "top_p": 0.9,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.5
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        logger.debug(f"HTTP Response Status: {response.status_code}")
        logger.debug(f"HTTP Response Body: {response.text}")
        if response.status_code == 200:
            json_response = response.json()
            if "choices" in json_response and len(json_response["choices"]) > 0:
                content = json_response["choices"][0].get("message", {}).get("content", "").strip()
                if content:
                    print(f"Ответ модели: {content}")
                else:
                    print("Пустой ответ от модели.")
            else:
                print("Пустой ответ от модели.")
        else:
            print(f"Ошибка API: {response.status_code} - {response.text}")

# Запуск теста
if __name__ == "__main__":
    asyncio.run(simple_test())
