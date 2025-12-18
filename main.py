import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN, ADMINS


async def start_handler(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer("Привет, админ 👋")
    else:
        await message.answer("Привет! Это Фильмовочная 🎬")


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(start_handler, CommandStart())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
