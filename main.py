import asyncio
import random
import io
import os
import re
import base64

from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE")
GEMINI_API_KEY = os.getenv("AQ.Ab8RN6LR4OekPY9fbtChzKj3GdL-98wUvUHlJTzpHbCSYWNpLg")

genai.configure(api_key=GEMINI_API_KEY)

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

FONT_PATH = "Anton-Regular.ttf"

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


def strip_emoji(text: str) -> str:
    return re.sub(r'[^\w\s\-А-Яа-яёЁA-Za-z0-9]', '', text).strip()


def parse_vs(variant: str):
    parts = variant.split(" VS ")
    if len(parts) == 2:
        return strip_emoji(parts[0]).strip(), strip_emoji(parts[1]).strip()
    return "Left", "Right"


def generate_image_via_gemini(prompt: str) -> Image.Image:
    model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")

    response = model.generate_content(
        f"Generate a high quality cinematic image: {prompt}. Dark dramatic background, no text, no watermark.",
        generation_config={"response_modalities": ["IMAGE"]}
    )

    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data and part.inline_data.mime_type.startswith("image/"):
            img_bytes = part.inline_data.data
            if isinstance(img_bytes, str):
                img_bytes = base64.b64decode(img_bytes)
            return Image.open(io.BytesIO(img_bytes)).convert("RGB")

    raise ValueError("Gemini не вернул изображение")


def fit_image(im: Image.Image, w: int, h: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    bg = Image.new("RGB", (w, h), (15, 15, 15))
    x = (w - im.width) // 2
    y = (h - im.height) // 2
    bg.paste(im, (x, y))
    return bg


def build_card(left_label: str, right_label: str,
               left_img: Image.Image, right_img: Image.Image) -> bytes:
    W, H = 1080, 1920
    HALF = H // 2

    card = Image.new("RGB", (W, H), (10, 10, 10))
    card.paste(fit_image(left_img, W, HALF), (0, 0))
    card.paste(fit_image(right_img, W, HALF), (0, HALF))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    ov.rectangle([0, 0, W, 200], fill=(0, 0, 0, 170))
    ov.rectangle([0, HALF - 120, W, HALF + 120], fill=(0, 0, 0, 210))
    ov.rectangle([0, H - 200, W, H], fill=(0, 0, 0, 170))
    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(card)

    try:
        font_vs = ImageFont.truetype(FONT_PATH, 160)
        font_label = ImageFont.truetype(FONT_PATH, 80)
    except Exception:
        font_vs = ImageFont.load_default()
        font_label = ImageFont.load_default()

    draw.line([(0, HALF), (W, HALF)], fill=(220, 30, 30), width=8)

    draw.text((W // 2, 100), left_label.upper(), font=font_label,
              fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))

    draw.text((W // 2, HALF), "VS", font=font_vs,
              fill=(220, 30, 30), anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))

    draw.text((W // 2, H - 100), right_label.upper(), font=font_label,
              fill=(255, 255, 255), anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🎲 Генератор VS запущен", reply_markup=keyboard)


@dp.message(F.text == "🎲 Генерация вариантов")
async def generate(message: Message):
    user_id = message.from_user.id
    user_choices[user_id] = []
    variants = random.sample(VS_POOL, 5)
    variant_storage[user_id] = {}

    for i, variant in enumerate(variants, start=1):
        variant_storage[user_id][str(i)] = variant

        kb = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="✅ Использовать", callback_data=f"use_{i}"),
                InlineKeyboardButton(text="🔄 Заменить", callback_data=f"replace_{i}")
            ]]
        )
        await message.answer(f"Вариант {i}\n\n{variant}", reply_markup=kb)


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
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Использовать", callback_data=f"use_{number}"),
            InlineKeyboardButton(text="🔄 Заменить", callback_data=f"replace_{number}")
        ]]
    )
    await callback.message.edit_text(f"Вариант {number}\n\n{new_variant}", reply_markup=kb)
    await callback.answer()


@dp.message(F.text == "🎨 Сгенерировать изображения")
async def generate_images(message: Message):
    user_id = message.from_user.id

    if user_id not in user_choices or len(user_choices[user_id]) < 1:
        await message.answer("Сначала выбери хотя бы 1 карточку.")
        return

    first_variant = user_choices[user_id][0]
    left_label, right_label = parse_vs(first_variant)

    await message.answer(
        f"🎨 Генерирую карточку:\n{first_variant}\n\n⏳ Подожди ~30 секунд..."
    )

    try:
        left_img = generate_image_via_gemini(left_label)
        right_img = generate_image_via_gemini(right_label)

        card_bytes = build_card(left_label, right_label, left_img, right_img)

        await message.answer_photo(
            BufferedInputFile(card_bytes, filename="vs_card.png"),
            caption=f"🔥 {first_variant}"
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка генерации:\n{e}")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
