import logging
import os
import asyncio
import time

from aiogram import Router, types, Bot, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
from supabase import create_client
from dotenv import load_dotenv

from keyboards import quiz_list_keyboard
from utils import build_leaderboard_message

load_dotenv()

# Подключение к Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

quiz_router = Router()
logger = logging.getLogger(__name__)


class QuizState(StatesGroup):
    waiting_for_quiz_selection = State()
    answering_questions = State()


async def get_db_user_id_by_telegram_id(telegram_id: int):
    """
    Получаем внутренний ID пользователя (db_user_id) из таблицы 'users'
    по реальному Telegram ID (telegram_id).
    Возвращает None, если пользователь не найден.
    """
    try:
        response = await asyncio.to_thread(
            supabase.table("users")
            .select("id")
            .eq("telegram_id", telegram_id)
            .single()
            .execute
        )
        return response.data["id"] if response.data else None
    except Exception as e:
        logging.error(f"Ошибка получения db_user_id: {e}")
        return None


async def get_quiz_by_id(quiz_id: int):
    """Получаем викторину по ID с вопросами."""
    try:
        response = await asyncio.to_thread(
            supabase.table("quizzes")
            .select("id, title, questions(id, text, explanation, options(text, is_correct))")
            .eq("id", quiz_id)
            .single()
            .execute
        )
        return response.data if response.data else None
    except Exception as e:
        logging.error(f"Ошибка получения викторины: {e}")
        return None


@quiz_router.callback_query(F.data.startswith("quiz_"), StateFilter(QuizState.waiting_for_quiz_selection))
async def start_quiz(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обработчик выбора викторины.
    """
    try:
        quiz_id = int(callback_query.data.split("_")[1])
        telegram_id = callback_query.from_user.id

        # Пытаемся найти пользователя в Supabase по telegram_id
        db_user_id = await get_db_user_id_by_telegram_id(telegram_id)
        if not db_user_id:
            logging.error(f"❌ Ошибка: Пользователь Telegram ID={telegram_id} не найден в Supabase.")
            await callback_query.message.answer("⚠️ Ошибка: ваш профиль не найден.\nПопробуйте заново /start или перезапустите бота.")
            return

        # Получаем викторину и сразу сохраняем её в FSM
        quiz = await get_quiz_by_id(quiz_id)
        if not quiz:
            await callback_query.message.answer("⚠️ Ошибка: викторина не найдена.")
            return

        chat_id = callback_query.message.chat.id

        await state.update_data(
            quiz_id=quiz_id,
            chat_id=chat_id,
            telegram_id=telegram_id,  # реальный Telegram ID
            db_user_id=db_user_id,    # внутренний ID из Supabase
            current_question_index=0,
            correct_answers=0,
            start_time=time.time(),
            quiz_finished=False,
            quiz=quiz  # сохраняем викторину целиком
        )
        await state.set_state(QuizState.answering_questions)

        # Отправляем первый вопрос
        await send_question(chat_id, state, callback_query.bot)

    except Exception as e:
        logger.exception(f"❌ Ошибка в start_quiz: {e}")
        await callback_query.message.answer("⚠️ Ошибка при запуске викторины. Попробуйте снова.")
        await state.clear()



@quiz_router.message(F.text == "📋 Список викторин")
async def list_quizzes(message: types.Message, state: FSMContext):
    """Отправляем список викторин пользователю."""
    try:
        keyboard = await quiz_list_keyboard()
        await message.answer("Выберите викторину:", reply_markup=keyboard)
        await state.set_state(QuizState.waiting_for_quiz_selection)
    except Exception as e:
        logging.error(f"Ошибка в list_quizzes: {e}")
        await message.answer("⚠️ Ошибка загрузки списка викторин.")


async def send_question(chat_id: int, state: FSMContext, bot: Bot):
    """Отправка вопроса викторины."""
    try:
        data = await state.get_data()
        # Используем уже сохранённую викторину
        quiz = data.get("quiz")
        if not quiz or "questions" not in quiz:
            await bot.send_message(chat_id, "⚠️ Ошибка: викторина не найдена или не содержит вопросов.")
            return

        questions = quiz["questions"]
        current_index = data.get("current_question_index", 0)

        if current_index < len(questions):
            question = questions[current_index]
            options = question["options"]

            correct_index = next((i for i, opt in enumerate(options) if opt["is_correct"]), None)

            poll_message = await bot.send_poll(
                chat_id=chat_id,
                question=question["text"],
                options=[opt["text"] for opt in options],
                type="quiz",
                correct_option_id=correct_index,
                is_anonymous=False,
            )

            await state.update_data(poll_id=poll_message.poll.id)
        else:
            await finish_quiz(chat_id, state, bot)

    except Exception as e:
        logger.error(f"Ошибка в send_question: {e}")
        await bot.send_message(chat_id, "⚠️ Ошибка отправки вопроса.")
        await state.clear()



@quiz_router.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer, state: FSMContext):
    """Обрабатывает ответ пользователя (quiz Poll)."""
    try:
        data = await state.get_data()
        chat_id = data.get("chat_id")
        quiz = data.get("quiz")  # Используем уже загруженные вопросы

        if not chat_id or not quiz or "questions" not in quiz:
            logging.warning("⚠️ Ошибка: chat_id или викторина не найдены в FSM.")
            return

        questions = quiz["questions"]
        current_question_index = data.get("current_question_index", 0)

        if current_question_index >= len(questions):
            await poll_answer.bot.send_message(chat_id, "⚠️ Вопросов больше нет.")
            return

        question = questions[current_question_index]
        options = question["options"]

        if not poll_answer.option_ids:
            await poll_answer.bot.send_message(chat_id, "⚠️ Вы не выбрали вариант.")
            return

        selected_option_id = poll_answer.option_ids[0]
        selected_option = options[selected_option_id]

        # Проверяем, верно ли отвечено
        if selected_option["is_correct"]:
            correct_answers = data.get("correct_answers", 0) + 1
            await state.update_data(correct_answers=correct_answers)
            await poll_answer.bot.send_message(chat_id, "✅ Верно!")
        else:
            await poll_answer.bot.send_message(chat_id, "❌ Неверно.")

        # Выводим пояснение (если есть)
        explanation = question.get("explanation")
        if explanation:
            await poll_answer.bot.send_message(chat_id, f"ℹ️ Пояснение: {explanation}")

        # Переходим к следующему вопросу
        await state.update_data(current_question_index=current_question_index + 1)

        if current_question_index + 1 >= len(questions):
            await finish_quiz(chat_id, state, poll_answer.bot)
        else:
            await send_question(chat_id, state, poll_answer.bot)

    except Exception as e:
        logger.error(f"Ошибка в handle_poll_answer: {e}")
        if state:
            await state.clear()
        await poll_answer.bot.send_message(poll_answer.user.id, "⚠️ Ошибка обработки ответа.")




async def finish_quiz(chat_id: int, state: FSMContext, bot: Bot):
    """🏆 Завершение викторины и показ турнирной таблицы."""
    try:
        data = await state.get_data()
        quiz_id = data["quiz_id"]
        db_user_id = data["db_user_id"]  # внутренний ID пользователя из Supabase
        correct_answers = data["correct_answers"]
        time_taken = int(time.time() - data["start_time"])

        # Проверяем, существует ли уже результат
        existing_result = await asyncio.to_thread(
            supabase.table("results")
            .select("user_id, score, time_taken")
            .eq("user_id", db_user_id)
            .eq("quiz_id", quiz_id)
            .limit(1)
            .execute
        )

        if existing_result.data:
            # Если результат уже существует, сообщаем
            await bot.send_message(chat_id, "Вы уже проходили эту викторину, ваш результат сохранён.")
        else:
            # Сохраняем новый результат
            result_data = {
                "user_id": db_user_id,
                "quiz_id": quiz_id,
                "score": correct_answers,
                "time_taken": time_taken
            }
            response = await asyncio.to_thread(
                supabase.table("results").insert(result_data).execute
            )
            if response.data is None:
                logging.error("❌ Ошибка при сохранении результата.")
                await bot.send_message(chat_id, "⚠️ Ошибка при сохранении результата.")
                return
            await bot.send_message(chat_id, "Ваш результат сохранён.")

        # Загружаем *все* результаты этой викторины
        leaderboard_response = await asyncio.to_thread(
            supabase.table("results")
            .select("user_id, score, time_taken")
            .eq("quiz_id", quiz_id)
            .order("score", desc=True)
            .order("time_taken", desc=False)
            .execute
        )
        leaderboard = leaderboard_response.data or []
        if not leaderboard:
            await bot.send_message(chat_id, "⚠️ Турнирная таблица пока пустая.")
            await state.clear()
            return

        total_participants = len(leaderboard)
        user_position = next((idx + 1 for idx, res in enumerate(leaderboard) if res["user_id"] == db_user_id), None)

        # Ваше личное сообщение о результатах
        result_message = (
            f"🏆 Викторина завершена!\n\n"
            f"🔹 Ваш результат: {correct_answers} правильных ответов\n"
            f"🕒 Время: {time_taken} сек\n"
            f"📊 Ваше место в рейтинге: {user_position}/{total_participants}"
        )
        await bot.send_message(chat_id, result_message)

        # Формируем Топ-10 и выводим через функцию
        top_results = leaderboard[:10]
        leaderboard_message = await build_leaderboard_message(top_results, supabase)
        await bot.send_message(chat_id, leaderboard_message)

        await state.clear()

    except Exception as e:
        logging.error(f"❌ Ошибка в finish_quiz: {e}")
        await bot.send_message(chat_id, "⚠️ Ошибка завершения викторины.")
        await state.clear()

