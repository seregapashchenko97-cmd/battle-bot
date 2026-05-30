import os
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

BOT_TOKEN = os.getenv("8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎲 Генератор VS запущен"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
