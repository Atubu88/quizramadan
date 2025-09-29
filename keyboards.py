import asyncio
import logging
import os
from typing import Optional

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from postgrest.exceptions import APIError
from supabase import create_client

# Инициализируем клиента Supabase (убедитесь, что переменные окружения настроены)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)


logger = logging.getLogger(__name__)


def start_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Список викторин"), KeyboardButton(text="🏆 Турнирная таблица")],
            [KeyboardButton(text="🌟 Общий рейтинг"), KeyboardButton(text="📝 Тест Самооценки")],
            [KeyboardButton(text="🔥 Рамадан Квест")],
            [KeyboardButton(text="🎲 Начать викторину")]
        ],
        resize_keyboard=True
    )
    return keyboard


async def quiz_category_keyboard():
    """Клавиатура с категориями викторин."""

    def fetch_categories():
        try:
            return supabase.table("categories").select("id, title").execute()
        except APIError:
            logger.warning(
                "Не удалось получить колонку 'title' для категорий, пробуем 'name'",
                exc_info=True,
            )
            return supabase.table("categories").select("id, name").execute()

    response = await asyncio.to_thread(fetch_categories)
    categories = response.data or []

    keyboard_builder = InlineKeyboardBuilder()
    for category in categories:
        title = category.get("title") or category.get("name") or f"Категория {category['id']}"
        keyboard_builder.button(
            text=title,
            callback_data=f"category_{category['id']}"
        )

    if categories:
        keyboard_builder.adjust(1)

    return keyboard_builder.as_markup()


async def quiz_list_keyboard(category_id: Optional[int] = None):
    """Клавиатура со списком викторин. Может фильтровать по категории.

    Возвращает кортеж из клавиатуры и признака наличия викторин.
    """

    def fetch_quizzes():
        query = supabase.table("quizzes").select("id, title")
        if category_id is not None:
            query = query.eq("category_id", category_id)
        return query.execute()

    response = await asyncio.to_thread(fetch_quizzes)
    quizzes = response.data or []

    keyboard_builder = InlineKeyboardBuilder()
    for quiz in quizzes:
        keyboard_builder.button(
            text=quiz["title"],
            callback_data=f"quiz_{quiz['id']}"
        )

    if quizzes:
        keyboard_builder.adjust(1)

    if category_id is not None:
        keyboard_builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_categories")
        )

    return keyboard_builder.as_markup(), bool(quizzes)
