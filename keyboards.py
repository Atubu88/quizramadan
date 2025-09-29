from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import os
from supabase import create_client
from typing import Optional

# Инициализируем клиента Supabase (убедитесь, что переменные окружения настроены)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)


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
        return supabase.table("categories").select("id, title").execute()

    response = await asyncio.to_thread(fetch_categories)
    categories = response.data or []

    keyboard_builder = InlineKeyboardBuilder()
    for category in categories:
        keyboard_builder.button(
            text=category["title"],
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
