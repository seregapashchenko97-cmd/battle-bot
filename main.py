import asyncio
import random
import io
import os
import re
import requests
import tempfile
import numpy as np
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    concatenate_videoclips, VideoFileClip
)
from moviepy.audio.AudioClip import AudioArrayClip
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BufferedInputFile,
    FSInputFile
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

FONT_PATH = "Anton-Regular.ttf"
CLIP_DURATION = 5  # секунд на каждый батл
FPS = 30

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎲 Генерация вариантов")],
        [KeyboardButton(text="🎨 Сгенерировать видео")]
    ],
    resize_keyboard=True
)

VS_POOL = [
    "❤️ Love VS 💰 Money",
    "🍔 Burger VS 🍕 Pizza",
    "🐶 Dog VS 🐱 Cat",
    "🏝 Beach VS ⛰ Mountains",
    "✈️ Travel VS 🏠 Home",
    "🎮 PlayStation VS 🖥 PC",
    "☕ Coffee VS 🍵 Tea",
    "🚗 BMW VS Mercedes",
    "🎤 Fame VS 😌 Peace",
    "📱 iPhone VS Android",
    "💪 Sports VS 🎮 Gaming",
    "🌙 Night VS ☀️ Day",
    "🎬 Cinema VS 📚 Books",
    "⚽ Football VS 🏀 Basketball",
    "🏖 Vacation VS 💼 Career",
    "💎 Wealth VS ❤️ Love",
    "🚀 Mars VS 🌍 Earth",
    "🦁 Lion VS 🐺 Wolf",
    "🏎 Ferrari VS Lamborghini",
    "🎸 Rock VS 🎹 Classical"
]

user_choices = {}
variant_storage = {}


def get_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def strip_emoji(text: str) -> str:
    return re.sub(r'[^\w\s\-A-Za-z0-9]', '', text).strip()


def parse_vs(variant: str):
    parts = variant.split(" VS ")
    if len(parts) == 2:
        return strip_emoji(parts[0]).strip(), strip_emoji(parts[1]).strip()
    return "Left", "Right"


def generate_image_pollinations(prompt: str) -> Image.Image:
    safe_prompt = requests.utils.quote(
        f"{prompt}, cinematic, dramatic lighting, dark background, high quality, no text, no watermark"
    )
    url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1080&height=960&nologo=true&model=flux"
    session = get_session()
    response = session.get(url, timeout=120)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def fit_image(im: Image.Image, w: int, h: int) -> Image.Image:
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    bg = Image.new("RGB", (w, h), (15, 15, 15))
    x = (w - im.width) // 2
    y = (h - im.height) // 2
    bg.paste(im, (x, y))
    return bg


def build_card(left_label: str, right_label: str,
               left_img: Image.Image, right_img: Image.Image,
               countdown: int = None) -> np.ndarray:
    """
    left_label  — верхняя картинка, её название рисуем СНИЗУ (над VS)
    right_label — нижняя картинка, её название рисуем СВЕРХУ (под VS)
    countdown   — цифра таймера (5,4,3,2,1) или None
    """
    W, H = 1080, 1920
    HALF = H // 2

    card = Image.new("RGB", (W, H), (10, 10, 10))
    card.paste(fit_image(left_img, W, HALF), (0, 0))
    card.paste(fit_image(right_img, W, HALF), (0, HALF))

    # Оверлеи
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    # Полоса вокруг VS
    ov.rectangle([0, HALF - 160, W, HALF + 160], fill=(0, 0, 0, 220))
    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(card)

    try:
        font_vs     = ImageFont.truetype(FONT_PATH, 150)
        font_label  = ImageFont.truetype(FONT_PATH, 72)
        font_timer  = ImageFont.truetype(FONT_PATH, 200)
    except Exception:
        font_vs    = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_timer = ImageFont.load_default()

    # Красная разделительная линия
    draw.line([(0, HALF), (W, HALF)], fill=(220, 30, 30), width=6)

    # VS по центру
    draw.text((W // 2, HALF), "VS", font=font_vs,
              fill=(220, 30, 30), anchor="mm",
              stroke_width=5, stroke_fill=(0, 0, 0))

    # Название верхней картинки — СНИЗУ над VS (слева от VS)
    draw.text((W // 2, HALF - 130), left_label.upper(), font=font_label,
              fill=(255, 255, 255), anchor="mb",
              stroke_width=3, stroke_fill=(0, 0, 0))

    # Название нижней картинки — СВЕРХУ под VS (справа от VS)
    draw.text((W // 2, HALF + 130), right_label.upper(), font=font_label,
              fill=(255, 255, 255), anchor="mt",
              stroke_width=3, stroke_fill=(0, 0, 0))

    # Таймер — в правом нижнем углу
    if countdown is not None:
        draw.text((W - 60, H - 60), str(countdown), font=font_timer,
                  fill=(255, 50, 50), anchor="rb",
                  stroke_width=8, stroke_fill=(0, 0, 0))

    return np.array(card)


def make_beep(duration=0.12, freq=880, sr=44100) -> np.ndarray:
    """Короткий бип для таймера."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = 0.4 * np.sin(2 * np.pi * freq * t)
    # fade out
    fade = np.linspace(1, 0, len(wave))
    wave = wave * fade
    stereo = np.stack([wave, wave], axis=1).astype(np.float32)
    return stereo


def build_battle_clip(left_label: str, right_label: str,
                      left_img: Image.Image, right_img: Image.Image,
                      tmp_dir: str) -> str:
    """Собирает 5-секундный клип одного батла с таймером и бипами."""
    sr = 44100
    frames_per_sec = FPS
    clips = []
    audio_chunks = []

    for sec in range(CLIP_DURATION, 0, -1):
        frame = build_card(left_label, right_label, left_img, right_img, countdown=sec)
        clip = ImageClip(frame, duration=1).set_fps(FPS)
        clips.append(clip)

        # Бип в начале каждой секунды
        beep = make_beep(freq=880 if sec > 1 else 1200)
        silence_len = sr - len(beep)
        silence = np.zeros((silence_len, 2), dtype=np.float32)
        chunk = np.concatenate([beep, silence], axis=0)
        audio_chunks.append(chunk)

    video = concatenate_videoclips(clips, method="compose")

    audio_data = np.concatenate(audio_chunks, axis=0)
    audio_clip = AudioArrayClip(audio_data, fps=sr)
    video = video.set_audio(audio_clip)

    out_path = os.path.join(tmp_dir, f"battle_{left_label}_{right_label}.mp4")
    video.write_videofile(out_path, fps=FPS, codec="libx264",
                          audio_codec="aac", logger=None)
    return out_path


def concat_clips(clip_paths: list, tmp_dir: str) -> str:
    """Склеивает все клипы в итоговое 25-сек видео."""
    clips = [VideoFileClip(p) for p in clip_paths]
    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(tmp_dir, "final_vs.mp4")
    final.write_videofile(out_path, fps=FPS, codec="libx264",
                          audio_codec="aac", logger=None)
    for c in clips:
        c.close()
    return out_path


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
        result += "\n🎬 Теперь нажми:\nСгенерировать видео"
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


@dp.message(F.text == "🎨 Сгенерировать видео")
async def generate_video(message: Message):
    user_id = message.from_user.id

    if user_id not in user_choices or len(user_choices[user_id]) < 5:
        count = len(user_choices.get(user_id, []))
        await message.answer(f"Нужно выбрать 5 карточек. Сейчас выбрано: {count}/5")
        return

    await message.answer("🎬 Генерирую изображения и видео...\n⏳ Это займёт 2-4 минуты, подожди!")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            clip_paths = []

            for idx, variant in enumerate(user_choices[user_id], start=1):
                left_label, right_label = parse_vs(variant)
                await message.answer(f"🖼 Батл {idx}/5: {left_label} VS {right_label}")

                left_img = generate_image_pollinations(left_label)
                right_img = generate_image_pollinations(right_label)

                clip_path = build_battle_clip(
                    left_label, right_label,
                    left_img, right_img,
                    tmp_dir
                )
                clip_paths.append(clip_path)

            await message.answer("🎞 Склеиваю финальное видео...")
            final_path = concat_clips(clip_paths, tmp_dir)

            await message.answer_video(
                FSInputFile(final_path, filename="vs_battle.mp4"),
                caption="🔥 VS Battle — 25 секунд\n#shorts #vs #battle",
                supports_streaming=True
            )

    except Exception as e:
        await message.answer(f"❌ Ошибка:\n{e}")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
