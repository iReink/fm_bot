from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
import asyncio
from config import BOT_TOKEN, ADMINS

# --- Клавиатура админа ---
admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новый ивент")],
        [KeyboardButton(text="Посмотреть все будущие ивенты")]
    ],
    resize_keyboard=True
)

# --- Хендлер команды /start ---
async def start_handler(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer(
            "Привет, админ 👋 Выбери действие:",
            reply_markup=admin_menu
        )
    else:
        await message.answer("Привет! Это Фильмовочная 🎬")

# --- Хендлер для всех сообщений админа ---
async def admin_message_handler(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer(
            "Меню админа:",
            reply_markup=admin_menu
        )

# --- Основная функция ---
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(start_handler, CommandStart())
    dp.message.register(admin_message_handler)  # любое сообщение от админа

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
