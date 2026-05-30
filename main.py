import asyncio
import os
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)
 
BOT_TOKEN = "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE"
GEMINI_API_KEY = "AQ.Ab8RN6Lb9ggtfZD1T6vKrmxXhYZ1QtjNPa427Fx_VScy9pcrhw"
 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")
 
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
    await message.answer("⏳ Генерирую варианты...")
    prompt = """
Придумай 5 вирусных сравнений для формата VS.
Примеры:
Любовь VS Деньги
Бургер VS Билет на концерт
Собака VS Кот
 
Требования:
* Ровно 5 вариантов
* Каждый вариант с новой строки
* Без нумерации
* Короткие и понятные темы
* Темы должны быть разными
* Формат строго: X VS Y
    """
    try:
        response = model.generate_content(prompt)
        await message.answer(
            "🔥 Варианты:\n\n" + response.text
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка Gemini:\n{e}"
        )
 
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
 
if __name__ == "__main__":
    asyncio.run(main())
 
