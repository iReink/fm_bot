import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMINS
from create_event import router as create_event_router, start_new_event

# --- Логирование ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Инициализация ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

# --- Админское меню ---
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новый ивент")],
        [KeyboardButton(text="Посмотреть все будущие ивенты")]
    ],
    resize_keyboard=True
)

# --- Хендлер /start ---
@dp.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("Привет, админ 👋 Выбери действие:", reply_markup=admin_menu)
    else:
        await message.answer("Привет! Это Фильмовочная 🎬")

# --- Хендлер меню админа (ловит только кнопки) ---
@dp.message(lambda msg: msg.text in ["Новый ивент", "Посмотреть все будущие ивенты"])
async def admin_menu_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return

    if message.text == "Новый ивент":
        await start_new_event(message, state)
    elif message.text == "Посмотреть все будущие ивенты":
        await message.answer("📋 Здесь будет список будущих ивентов.")

# --- Подключаем модуль создания ивента ---
dp.include_router(create_event_router)

async def main():
    logging.info("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
