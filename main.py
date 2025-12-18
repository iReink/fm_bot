from aiogram import Bot, Dispatcher
import asyncio
from config import BOT_TOKEN, ADMINS
from create_event import router as create_event_router
from aiogram.fsm.storage.memory import MemoryStorage

from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

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
async def start_handler(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await message.answer("Привет, админ 👋 Выбери действие:", reply_markup=admin_menu)
    else:
        await message.answer("Привет! Это Фильмовочная 🎬")

# --- Повторное показ меню ---
@dp.message()
async def admin_message_handler(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await message.answer("Меню админа:", reply_markup=admin_menu)

# --- Подключаем модуль создания ивента ---
dp.include_router(create_event_router)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
