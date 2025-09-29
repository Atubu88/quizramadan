import logging
import asyncio
import os
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_API_KEY)

admin_router = Router()
ADMIN_IDS = ['732402669', '7919126514']  # Список администраторов

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS




# Команда /admin для открытия админ-панели
@admin_router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if is_admin(message.from_user.id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='➕ Добавить викторину', callback_data='add_quiz')],
            [InlineKeyboardButton(text='🗑 Удалить викторину', callback_data='delete_quiz')],
            [InlineKeyboardButton(text='🔄 Сбросить турнирную таблицу и общий рейтинг', callback_data='reset_tournament')]
        ])
        await message.answer("Добро пожаловать в админ-панель. Выберите действие:", reply_markup=keyboard)
    else:
        await message.answer("У вас нет прав для доступа к этой команде.")

# Обработка сброса турнирной таблицы (и общего рейтинга)
@admin_router.callback_query(F.data == 'reset_tournament')
async def reset_tournament_table(callback_query: types.CallbackQuery):
    if is_admin(callback_query.from_user.id):
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✅ Подтвердить сброс', callback_data='confirm_reset_tournament')],
            [InlineKeyboardButton(text='❌ Отменить', callback_data='cancel')]
        ])
        await callback_query.message.answer("Вы уверены, что хотите сбросить турнирную таблицу и общий рейтинг?",
                                             reply_markup=confirm_keyboard)
    else:
        await callback_query.message.answer("У вас нет прав для этого действия.")

# Подтверждение сброса турнирной таблицы
@admin_router.callback_query(F.data == 'confirm_reset_tournament')
async def confirm_reset_tournament(callback_query: types.CallbackQuery):
    if is_admin(callback_query.from_user.id):
        await asyncio.to_thread(supabase.table("results").delete().execute)
        await callback_query.message.answer("Турнирная таблица и общий рейтинг успешно сброшены.")
    else:
        await callback_query.message.answer("У вас нет прав для этого действия.")

# Обработка отмены действия
@admin_router.callback_query(F.data == 'cancel')
async def cancel_action(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Действие отменено.")

# Переключение состояния таймера


# Обработка команды "Добавить викторину" – запрос текстового формата викторины
@admin_router.callback_query(F.data == 'add_quiz')
async def request_quiz_text(callback_query: types.CallbackQuery):
    if is_admin(callback_query.from_user.id):
        await callback_query.message.answer(
            "Отправьте викторину в текстовом формате. Важно соблюдать формат:\n"
            "1. Пустая строка после темы и между вопросами.\n"
            "2. Варианты ответов начинаются с '-'.\n"
            "3. Указывайте номер правильного ответа и пояснение (необязательно)."
        )
        await callback_query.message.answer(
            "Пример формата:\n"
            "Тема: Законы Вселенной\n\n"
            "1. Какой закон утверждает сохранение энергии?\n"
            "- Закон сохранения энергии\n"
            "- Закон притяжения\n"
            "- Закон кармы\n"
            "- Закон равновесия\n"
            "Ответ: 1\n"
            "Пояснение: Энергия может только переходить из одной формы в другую.\n"
        )
    else:
        await callback_query.message.answer("У вас нет прав для выполнения этой команды.")

# Обработка текстового формата викторины (начинается с "Тема:" или "TEMA:")
@admin_router.message(lambda message: message.text.startswith(("Тема:", "TEMA:")))
async def handle_text_quiz(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав для выполнения этой команды.")
        return
    try:
        lines = message.text.splitlines()
        if lines[0].startswith("TEMA:"):
            language_keys = {"topic": "TEMA:", "answer": "Svar:", "explanation": "Förklaring:"}
        elif lines[0].startswith("Тема:"):
            language_keys = {"topic": "Тема:", "answer": "Ответ:", "explanation": "Пояснение:"}
        else:
            raise ValueError("Неизвестный язык или неверный формат викторины.")
        title = lines[0].replace(language_keys["topic"], "").strip()
        questions = []
        current_question = None
        for line in lines[1:]:
            if line.strip() == "":
                continue
            if line[0].isdigit():
                if current_question:
                    if not current_question["options"]:
                        raise ValueError(f"У вопроса '{current_question['question']}' нет вариантов ответа.")
                    if current_question["correct"] is None:
                        raise ValueError(f"У вопроса '{current_question['question']}' не указан правильный ответ.")
                    questions.append(current_question)
                parts = line.split(". ", 1)
                if len(parts) < 2:
                    raise ValueError("Неверный формат вопроса.")
                current_question = {
                    "question": parts[1].strip(),
                    "options": [],
                    "correct": None,
                    "explanation": None,
                }
            elif line.startswith(language_keys["answer"]):
                if not current_question or not current_question["options"]:
                    raise ValueError("Нельзя указать правильный ответ для вопроса без вариантов.")
                correct_option_id = int(line.replace(language_keys["answer"], "").strip()) - 1
                if correct_option_id < 0 or correct_option_id >= len(current_question["options"]):
                    raise ValueError(f"Неверный индекс правильного ответа для вопроса: {current_question['question']}")
                current_question["correct"] = correct_option_id
            elif line.startswith(language_keys["explanation"]):
                current_question["explanation"] = line.replace(language_keys["explanation"], "").strip()
            elif line.strip().startswith("-"):
                current_question["options"].append(line.strip().replace("-", "").strip())
            else:
                raise ValueError(f"Неверный формат строки: '{line}'")
        if current_question:
            if not current_question["options"]:
                raise ValueError(f"У вопроса '{current_question['question']}' нет вариантов ответа.")
            if current_question["correct"] is None:
                raise ValueError(f"У вопроса '{current_question['question']}' не указан правильный ответ.")
            questions.append(current_question)
        # Добавление викторины в Supabase
        quiz_response = await asyncio.to_thread(
            supabase.table("quizzes").insert({"title": title}).execute
        )
        if not quiz_response.data:
            raise ValueError("Ошибка добавления викторины.")
        quiz_id = quiz_response.data[0]["id"]
        for q in questions:
            question_response = await asyncio.to_thread(
                supabase.table("questions").insert({
                    "text": q["question"],
                    "quiz_id": quiz_id,
                    "explanation": q.get("explanation")
                }).execute
            )
            if not question_response.data:
                raise ValueError("Ошибка добавления вопроса.")
            question_id = question_response.data[0]["id"]
            options_data = []
            for idx, option_text in enumerate(q["options"]):
                options_data.append({
                    "text": option_text,
                    "is_correct": (idx == q["correct"]),
                    "question_id": question_id
                })
            options_response = await asyncio.to_thread(
                supabase.table("options").insert(options_data).execute
            )
            if not options_response.data:
                raise ValueError("Ошибка добавления вариантов ответа.")
        await message.answer(f"Викторина '{title}' успешно добавлена!")
    except ValueError as e:
        await message.answer(f"Ошибка в данных: {str(e)}")
    except Exception as e:
        await message.answer(f"Неизвестная ошибка: {str(e)}")

# Удаление викторины – сначала отображаем список викторин для удаления
@admin_router.callback_query(F.data == 'delete_quiz')
async def choose_quiz_to_delete(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.message.answer("У вас нет прав для этого действия.")
        return
    quizzes_response = await asyncio.to_thread(
        supabase.table("quizzes").select("id, title").execute
    )
    quizzes = quizzes_response.data
    if not quizzes:
        await callback_query.message.answer("На данный момент нет сохранённых викторин.")
        return
    buttons = []
    for quiz in quizzes:
        buttons.append([
            InlineKeyboardButton(
                text=f"Удалить: {quiz['title']} (ID: {quiz['id']})",
                callback_data=f"delete_quiz_id_{quiz['id']}"
            )
        ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback_query.message.answer("Выберите викторину, которую хотите удалить:", reply_markup=keyboard)

# Подтверждение удаления викторины
@admin_router.callback_query(F.data.startswith('delete_quiz_id_'))
async def confirm_quiz_deletion(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.message.answer("У вас нет прав для этого действия.")
        return
    quiz_id_str = callback_query.data.replace('delete_quiz_id_', '')
    try:
        quiz_id = int(quiz_id_str)
    except ValueError:
        await callback_query.message.answer("Некорректный ID викторины.")
        return
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Подтвердить удаление', callback_data=f'confirm_delete_{quiz_id}')],
        [InlineKeyboardButton(text='❌ Отменить', callback_data='cancel')]
    ])
    await callback_query.message.answer(
        f"Вы действительно хотите удалить викторину с ID {quiz_id}? Это действие необратимо.",
        reply_markup=confirm_keyboard
    )

# Финальное удаление викторины
@admin_router.callback_query(F.data.startswith('confirm_delete_'))
async def delete_quiz(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.message.answer("У вас нет прав для этого действия.")
        return

    quiz_id_str = callback_query.data.replace('confirm_delete_', '')
    try:
        quiz_id = int(quiz_id_str)
    except ValueError:
        await callback_query.message.answer("Некорректный ID викторины.")
        return

    # Сначала удаляем все результаты, связанные с викториной
    await asyncio.to_thread(
        supabase.table("results").delete().eq("quiz_id", quiz_id).execute
    )

    # Теперь можно удалить саму викторину
    quiz_response = await asyncio.to_thread(
        supabase.table("quizzes").delete().eq("id", quiz_id).execute
    )

    if quiz_response.data is None:
        await callback_query.message.answer(f"Викторина с ID {quiz_id} не найдена или произошла ошибка.")
        return

    try:
        await callback_query.message.edit_text(
            text=f"✅ Викторина успешно удалена!",
            reply_markup=None
        )
    except Exception:
        await callback_query.message.answer("✅ Викторина успешно удалена!")
