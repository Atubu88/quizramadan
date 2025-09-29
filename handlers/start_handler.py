import logging
import os
import asyncio
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
import asyncpg  # Если нужна обработка специфических ошибок PostgreSQL
from supabase import create_client

# Создаём роутер
start_router = Router()

# Путь до приветственной картинки (если есть)
MEDIA_PATH = os.path.join(os.getcwd(), "media", "welcome1.png")

# Подключаемся к Supabase через переменные окружения
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)


async def upsert_user_supabase(user_data: dict):
    """
    Пишем (upsert) пользователя в таблицу "users" Supabase
    по полю "telegram_id". Предполагаем, что telegram_id UNIQUE.
    """
    try:
        # Выполняем upsert, указывая on_conflict="telegram_id"
        response = await asyncio.to_thread(
            supabase.table("users")
            .upsert(user_data, on_conflict="telegram_id")
            .execute
        )
        # Проверяем, нет ли ошибки
        if response.data is None:
            # Если data=None, значит что-то пошло не так
            logging.error(
                f"Ошибка upsert_user_supabase: status_code={response.status_code}, "
                f"error_message={response.error_message}"
            )
        else:
            logging.info(
                f"✅ Пользователь {user_data['telegram_id']} ({user_data['username']}) "
                "успешно upsert в Supabase."
            )
    except Exception as e:
        logging.error(f"⚠️ Ошибка в upsert_user_supabase: {e}")
        # Здесь можно добавить retry‑логику, если необходимо


@start_router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start: сохраняем/обновляем пользователя в Supabase,
    отправляем приветственное сообщение с кнопками.
    """
    user = message.from_user
    logging.info(f"🔹 /start от {user.id}")

    # Готовим словарь для записи в Supabase
    user_data = {
        "telegram_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or ""
    }

    # Асинхронно (в фоновом режиме) делаем upsert в Supabase
    asyncio.create_task(upsert_user_supabase(user_data))

    # Собираем клавиатуру
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Список викторин"), KeyboardButton(text="🏆 Турнирная таблица")],
            [KeyboardButton(text="🌟 Общий рейтинг"),  KeyboardButton(text="📝 Тест Самооценки")],
            [KeyboardButton(text="🔥 Рамадан Квест")]
        ],
        resize_keyboard=True
    )

    # Отправляем приветственное сообщение (с фото, если есть)
    try:
        if os.path.exists(MEDIA_PATH):
            photo = FSInputFile(MEDIA_PATH)
            await message.answer_photo(
                photo,
                caption="Добро пожаловать! 🎉\nВыбери викторину и начинай играть! 🎮",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                "Добро пожаловать! Выбери викторину из меню 🎮",
                reply_markup=keyboard
            )
    except Exception as e:
        logging.warning(f"⚠️ Ошибка отправки фото: {e}")
        await message.answer(
            "Добро пожаловать! Выбери викторину из меню 🎮",
            reply_markup=keyboard
        )


@start_router.message(Command("reset"))
async def cmd_reset(message: types.Message, state: FSMContext):
    """
    Сброс состояния FSM командой /reset.
    """
    await state.clear()
    await message.answer("✅ Состояние бота сброшено. Попробуйте снова /start")
