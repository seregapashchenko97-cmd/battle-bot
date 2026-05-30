import asyncio
import random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
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

VS_POOL = [
    "❤️ Любовь VS 💰 Деньги",
    "🍔 Бургер VS 🍕 Пицца",
    "🐶 Собака VS 🐱 Кот",
    "🏝 Море VS ⛰ Горы",
    "✈️ Путешествие VS 🏠 Дом мечты",
    "🎮 PlayStation VS 🖥 ПК",
    "☕ Кофе VS 🍵 Чай",
    "🚗 BMW VS Mercedes",
    "🎤 Слава VS 😌 Спокойствие",
    "📱 iPhone VS Android",
    "💪 Спорт VS 🎮 Игры",
    "🌙 Ночь VS ☀️ День",
    "🎬 Кино VS 📚 Книга",
    "⚽ Футбол VS 🏀 Баскетбол",
    "🏖 Отдых VS 💼 Карьера",
    "💎 Богатство VS ❤️ Любовь",
    "🚀 Марс VS 🌍 Земля",
    "🦁 Лев VS 🐺 Волк",
    "🏎 Ferrari VS Lamborghini",
    "🎸 Рок VS 🎹 Классика"
]


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎲 Генератор VS запущен",
        reply_markup=keyboard
    )


@dp.message(F.text == "🎲 Генерация вариантов")
async def generate(message: Message):
    variants = random.sample(VS_POOL, 5)

    for i, variant in enumerate(variants, start=1):
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Использовать",
                        callback_data=f"use_{i}"
                    ),
                    InlineKeyboardButton(
                        text="🔄 Заменить",
                        callback_data=f"replace_{i}"
                    )
                ]
            ]
        )

        await message.answer(
            f"Вариант {i}\n\n{variant}",
            reply_markup=kb
        )


@dp.callback_query(F.data.startswith("use_"))
async def use_variant(callback: CallbackQuery):
    await callback.answer("Выбрано ✅")
    await callback.message.edit_reply_markup(reply_markup=None)


@dp.callback_query(F.data.startswith("replace_"))
async def replace_variant(callback: CallbackQuery):
    new_variant = random.choice(VS_POOL)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Использовать",
                    callback_data=callback.data.replace("replace", "use")
                ),
                InlineKeyboardButton(
                    text="🔄 Заменить",
                    callback_data=callback.data
                )
            ]
        ]
    )

    await callback.message.edit_text(new_variant, reply_markup=kb)
    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
