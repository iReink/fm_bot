import asyncio
import logging
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from config import ADMINS, BOT_TOKEN
from create_event import router as create_event_router, start_new_event
from participant_events import (
    router as participant_router,
    send_nearest_event,
    reminder_loop,
)
from view_event_admin import router as view_event_router, show_future_events

# --- Логирование ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Инициализация ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

DB_PATH = Path(__file__).resolve().parent / "data.db"

# --- Админское меню ---
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новый ивент")],
        [KeyboardButton(text="Посмотреть все будущие ивенты")]
    ],
    resize_keyboard=True
)


def upsert_user(user_id: int, username: str, nickname: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (user_id, username, nickname, active, notification_on)
        VALUES (?, ?, ?, 1, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            nickname = excluded.nickname,
            active = 1
        """,
        (user_id, username, nickname),
    )
    conn.commit()
    conn.close()


# --- Хендлер /start ---
@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("Привет, админ 👋 Выбери действие:", reply_markup=admin_menu)
    else:
        upsert_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.full_name,
        )
        await message.answer("Привет! Это Фильмовочная 🎬")
        await send_nearest_event(message)


# --- Хендлер меню админа (ловит только кнопки) ---
@dp.message(lambda msg: msg.text in ["Новый ивент", "Посмотреть все будущие ивенты"])
async def admin_menu_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return

    if message.text == "Новый ивент":
        await start_new_event(message, state)
    elif message.text == "Посмотреть все будущие ивенты":
        await show_future_events(message)


# --- Подключаем модуль создания ивента ---
dp.include_router(create_event_router)
dp.include_router(view_event_router)
dp.include_router(participant_router)


async def main():
    logging.info("Бот запущен")
    asyncio.create_task(reminder_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
