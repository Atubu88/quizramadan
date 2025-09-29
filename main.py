import os
import logging
import asyncio
import sentry_sdk
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
# Удаляем: from database import close_db

# 🔹 Настройка логирования перед инициализацией Sentry
logging.basicConfig(
    level=logging.INFO,  # Выводим все логи, включая DEBUG
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN")
print(f"🔍 SENTRY_DSN: {SENTRY_DSN}")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=True,
        traces_sample_rate=1.0,
        ignore_errors=[KeyboardInterrupt]
    )
    logging.info("✅ Sentry успешно подключён!")
else:
    logging.warning("⚠️ SENTRY_DSN не найден! Логирование в Sentry отключено.")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

from handlers.start_handler import start_router
from handlers.quiz_handler import quiz_router
from handlers.leaderboard_handler import leaderboard_router
from handlers.admin import admin_router
from handlers.self_report_test_handler import test_router
from deepseek_handler import deepseek_router
from handlers.competition_router import competition_router
from handlers.survival import survival_router
from handlers.quiz_with_polls import quiz_with_polls_router

dp.include_router(start_router)
dp.include_router(quiz_router)
dp.include_router(leaderboard_router)
dp.include_router(admin_router)
dp.include_router(test_router)
dp.include_router(deepseek_router)
dp.include_router(competition_router)
dp.include_router(survival_router)
dp.include_router(quiz_with_polls_router)

async def on_startup():
    logging.info("✅ Бот запущен")
    sentry_sdk.capture_message("🚀 Бот успешно запущен и подключён к Sentry!")

async def on_shutdown():
    logging.info("🛑 Остановка бота...")
    await bot.session.close()
    # Вызов close_db() удалён, так как он не нужен

async def main():
    await on_startup()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Ошибка при работе бота: {e}")
        sentry_sdk.capture_exception(e)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())
