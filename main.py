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
        [KeyboardButton(text="🎲 Генерация вариантов")],
        [KeyboardButton(text="🎨 Сгенерировать изображения")]
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

user_choices = {}
variant_storage = {}


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🎲 Генератор VS запущен",
        reply_markup=keyboard
    )


@dp.message(F.text == "🎲 Генерация вариантов")
async def generate(message: Message):
    user_id = message.from_user.id
    user_choices[user_id] = []
    variants = random.sample(VS_POOL, 5)
    variant_storage[user_id] = {}

    for i, variant in enumerate(variants, start=1):
        variant_storage[user_id][str(i)] = variant

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
    user_id = callback.from_user.id
    number = callback.data.split("_")[1]
    variant = variant_storage[user_id][number]

    if variant not in user_choices[user_id]:
        user_choices[user_id].append(variant)

    count = len(user_choices[user_id])

    await callback.answer(f"Выбрано {count}/5")
    await callback.message.edit_reply_markup(reply_markup=None)

    if count == 5:
        result = "✅ Выбрано 5 карточек\n\n"
        for i, item in enumerate(user_choices[user_id], start=1):
            result += f"{i}. {item}\n"
        result += "\n🎨 Теперь нажми кнопку:\nСгенерировать изображения"
        await callback.message.answer(result)


@dp.callback_query(F.data.startswith("replace_"))
async def replace_variant(callback: CallbackQuery):
    user_id = callback.from_user.id
    number = callback.data.split("_")[1]
    new_variant = random.choice(VS_POOL)
    variant_storage[user_id][number] = new_variant

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Использовать",
                    callback_data=f"use_{number}"
                ),
                InlineKeyboardButton(
                    text="🔄 Заменить",
                    callback_data=f"replace_{number}"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        f"Вариант {number}\n\n{new_variant}",
        reply_markup=kb
    )
    await callback.answer()


@dp.message(F.text == "🎨 Сгенерировать изображения")
async def generate_images(message: Message):
    user_id = message.from_user.id

    if user_id not in user_choices:
        await message.answer("Сначала выбери 5 карточек.")
        return

    if len(user_choices[user_id]) < 5:
        await message.answer(
            f"Пока выбрано только {len(user_choices[user_id])}/5 карточек."
        )
        return

    await message.answer("🎨 Этап генерации изображений будет следующим шагом.")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
