import asyncio
import time
import os
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
from supabase import create_client
from keyboards import start_keyboard

# Подключение к Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

# Создаём роутер для викторины с опросами
quiz_with_polls_router = Router()
sessions = {}

# Пример структуры вопроса с вариантами ответов
quiz_questions = [
    {
        "question": "1. Ты читаешь Коран 10 страниц в час. Ты уделил 3 часа, но в последний час скорость увеличилась в 1.5 раза. Сколько страниц ты прочитал?",
        "options": ["30", "35", "40"],
        "answer": "35",
        "explanation": "Ты правильно посчитал! Пророк (ﷺ) сказал: «Кто читает одну букву из Книги Аллаха, тому записывается награда, а награда умножается в 10 раз» (ат-Тирмизи). Представь, сколько награды ты получил за 35 страниц!"
    },
    # ... другие вопросы ...
]

async def send_question_poll(chat_id: int, question_data: dict, bot):
    """Отправка вопроса в виде опроса."""
    options = question_data["options"]
    correct_option_id = options.index(question_data["answer"])

    poll_message = await bot.send_poll(
        chat_id=chat_id,
        question=question_data["question"],
        options=options,
        type="quiz",
        correct_option_id=correct_option_id,
        is_anonymous=False,
    )
    return poll_message

@quiz_with_polls_router.message(F.text == "🎲 Начать викторину")
async def start_quiz_with_polls(message: Message):
    user_id = message.from_user.id
    if user_id in sessions and sessions[user_id]["active"]:
        await message.answer("⚠️ Вы уже играете! Завершите текущую игру перед началом новой.")
        return

    sessions[user_id] = {
        "lives": 3,
        "question_index": 0,
        "score": 0,
        "waiting_future": None,
        "active": True,
        "start_time": time.time()  # Запоминаем время начала игры
    }

    await message.answer("🎮 Игра началась! У вас 3 🔋. Отвечайте правильно, чтобы пройти уровень.")
    await quiz_game_loop(message)

async def quiz_game_loop(message: Message):
    user_id = message.from_user.id

    while user_id in sessions and sessions[user_id]["active"]:
        session = sessions.get(user_id)
        if not session:
            return

        if session["question_index"] >= len(quiz_questions):
            await message.answer("🎉 Поздравляем! Вы прошли все уровни!")
            break

        current_question = quiz_questions[session["question_index"]]
        energy = "🔋" * session["lives"]

        # Отправляем вопрос в виде опроса
        poll_message = await send_question_poll(message.chat.id, current_question, message.bot)

        # Сохраняем ID опроса
        session["poll_id"] = poll_message.poll.id

        # Ждём ответа (либо таймаут)
        try:
            user_answer = await asyncio.wait_for(session["waiting_future"], timeout=44)
        except asyncio.TimeoutError:
            user_answer = None

        # Проверяем ответ
        correct_answer = current_question["answer"].strip().lower()
        if user_answer is None:
            session["lives"] -= 1
            if session["lives"] <= 0:
                await message.answer("⏳ Время вышло, и у тебя не осталось энергии.")
                break
            else:
                await message.answer("⏳ Время вышло! Попробуйте ещё раз.")
        else:
            if user_answer.strip().lower() == correct_answer:
                await message.answer(
                    f"✅ Уровень пройден!\n\n"
                    f"{current_question['explanation']}"
                )
                session["score"] += 1
                session["question_index"] += 1
            else:
                session["lives"] -= 1
                if session["lives"] <= 0:
                    await message.answer("❌ Неверно! К сожалению, энергия закончилась.")
                    break
                else:
                    await message.answer("❌ Неверно! Попробуйте ещё раз.")

    # Подсчёт времени игры
    elapsed_time = time.time() - sessions[user_id]["start_time"]
    minutes, seconds = divmod(int(elapsed_time), 60)

    # Получаем данные пользователя
    first_name = message.from_user.first_name if message.from_user.first_name else ""
    username = message.from_user.username if message.from_user.username else ""
    display_name = first_name if first_name else (username if username else "Аноним")

    score = session["score"]
    time_spent = int(elapsed_time)

    # Проверяем, есть ли запись для пользователя
    existing_record = supabase.table("quiz_results").select("id", "score", "time_spent").eq("user_id",
                                                                                                user_id).execute()

    if existing_record.data:
        # Если запись есть, обновляем её
        supabase.table("quiz_results").update({
            "score": score,
            "time_spent": time_spent
        }).eq("user_id", user_id).execute()
    else:
        # Если записи нет, создаём новую
        supabase.table("quiz_results").insert({
            "user_id": user_id,
            "username": display_name,
            "score": score,
            "time_spent": time_spent
        }).execute()

    # Получаем рейтинг
    result = supabase.table("quiz_results").select("user_id", "score").order("score", desc=True).execute()
    all_results = result.data
    total_players = len(all_results)
    position = next((i + 1 for i, res in enumerate(all_results) if res["user_id"] == user_id), "N/A")

    # Отправляем пользователю результат
    await message.answer(
        f"🏁 Игра завершена! 📊\n"
        f"✅ Пройденных уровней: {score}\n"
        f"⏱ Время игры: {minutes} мин {seconds} сек.\n"
        f"🏆 Ты занял *{position}-е место* из {total_players} участников!"
    )

    sessions.pop(user_id, None)

@quiz_with_polls_router.message()
async def handle_poll_answers(message: Message):
    user_id = message.from_user.id
    session = sessions.get(user_id)
    if session and session.get("waiting_future") and not session["waiting_future"].done():
        session["waiting_future"].set_result(message.text) 