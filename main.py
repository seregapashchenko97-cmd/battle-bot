import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)

BOT_TOKEN = "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎲 Генерация вариантов")]
    ],
    resize_keyboard=True
)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎲 Генератор VS запущен",
        reply_markup=keyboard
    )


@dp.message(F.text == "🎲 Генерация вариантов")
async def generate(message: Message):

    variants = [
        "❤️ Любовь VS 💰 Деньги",
        "🍔 Бургер VS 🎫 Билет на концерт",
        "🏝 Отдых VS 🚗 Новая машина",
        "🐶 Собака VS 🐱 Кот",
        "✈️ Путешествие VS 🏠 Дом мечты"
    ]

    text = "🔥 Варианты:\n\n"

    for i, item in enumerate(variants, start=1):
        text += f"{i}. {item}\n"

    await message.answer(text)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
