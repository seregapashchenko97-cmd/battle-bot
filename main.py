import asyncio
import random
import io
import os
import re
import requests
import tempfile
import subprocess
import numpy as np
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    FSInputFile
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

FONT_PATH = "Anton-Regular.ttf"
CLIP_DURATION = 5
FPS = 24
W, H = 1080, 1920

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎲 Генерация вариантов")],
        [KeyboardButton(text="🎨 Сгенерировать видео")]
    ],
    resize_keyboard=True
)

VS_POOL = [
    "Love VS Money", "Burger VS Pizza", "Dog VS Cat",
    "Beach VS Mountains", "Travel VS Home", "PlayStation VS PC",
    "Coffee VS Tea", "BMW VS Mercedes", "Fame VS Peace",
    "iPhone VS Android", "Sports VS Gaming", "Night VS Day",
    "Cinema VS Books", "Football VS Basketball", "Vacation VS Career",
    "Wealth VS Love", "Mars VS Earth", "Lion VS Wolf",
    "Ferrari VS Lamborghini", "Rock VS Classical"
]

QUERY_MAP = {
    "Wealth": "money gold luxury", "Peace": "nature calm",
    "Fame": "spotlight concert", "Gaming": "game controller",
    "Cinema": "movie theater", "Classical": "piano orchestra",
    "PlayStation": "gaming console", "Mars": "space planet",
    "Vacation": "holiday resort", "Career": "office business",
    "Rock": "rock concert guitar", "Night": "city night",
    "Day": "sunrise sky",
}

user_choices = {}
variant_storage = {}


def get_session():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def parse_vs(variant):
    parts = variant.split(" VS ")
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("Left", "Right")


def fetch_unsplash_image(query):
    logger.info(f"Fetching image for: {query}")
    session = get_session()
    headers = {"Authorization": f"Client-ID {UNSPLASH_KEY}"}
    for q in [QUERY_MAP.get(query, query), query.split()[0], "nature"]:
        try:
            r = session.get("https://api.unsplash.com/photos/random",
                           params={"query": q, "orientation": "landscape"},
                           headers=headers, timeout=20)
            r.raise_for_status()
            img_url = r.json()["urls"]["small"]  # small вместо regular — быстрее
            img_r = session.get(img_url, timeout=20)
            img_r.raise_for_status()
            logger.info(f"Image fetched for: {query}")
            return Image.open(io.BytesIO(img_r.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"Failed query '{q}': {e}")
            continue
    logger.info(f"Using fallback for: {query}")
    img = Image.new("RGB", (W, H // 2), (20, 20, 20))
    return img


def fit_image(im, w, h):
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    bg = Image.new("RGB", (w, h), (15, 15, 15))
    bg.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return bg


def build_frame(left_label, right_label, left_img, right_img, countdown=None):
    HALF = H // 2
    card = Image.new("RGB", (W, H), (10, 10, 10))
    card.paste(fit_image(left_img, W, HALF), (0, 0))
    card.paste(fit_image(right_img, W, HALF), (0, HALF))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([0, HALF - 160, W, HALF + 160], fill=(0, 0, 0, 220))
    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(card)
    try:
        fvs = ImageFont.truetype(FONT_PATH, 150)
        flb = ImageFont.truetype(FONT_PATH, 72)
        ftm = ImageFont.truetype(FONT_PATH, 200)
    except Exception:
        fvs = flb = ftm = ImageFont.load_default()

    draw.line([(0, HALF), (W, HALF)], fill=(220, 30, 30), width=6)
    draw.text((W//2, HALF), "VS", font=fvs, fill=(220, 30, 30), anchor="mm",
              stroke_width=5, stroke_fill=(0, 0, 0))
    draw.text((W//2, HALF - 130), left_label.upper(), font=flb,
              fill=(255, 255, 255), anchor="mb", stroke_width=3, stroke_fill=(0, 0, 0))
    draw.text((W//2, HALF + 130), right_label.upper(), font=flb,
              fill=(255, 255, 255), anchor="mt", stroke_width=3, stroke_fill=(0, 0, 0))
    if countdown is not None:
        draw.text((W - 60, H - 60), str(countdown), font=ftm,
                  fill=(255, 50, 50), anchor="rb", stroke_width=8, stroke_fill=(0, 0, 0))
    return card


def make_beep_pcm(freq=880, sr=44100, duration=0.12):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = (0.4 * np.sin(2 * np.pi * freq * t) * np.linspace(1, 0, len(t))).astype(np.float32)
    silence = np.zeros(sr - len(wave), dtype=np.float32)
    mono = np.concatenate([wave, silence])
    stereo = np.stack([mono, mono], axis=1)
    return (stereo * 32767).astype(np.int16).tobytes()


def build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, index):
    logger.info(f"Building clip {index}: {left_label} VS {right_label}")
    out_path = os.path.join(tmp_dir, f"battle_{index:02d}.mp4")
    audio_path = os.path.join(tmp_dir, f"audio_{index}.pcm")

    frames_bytes = b""
    audio_bytes = b""

    for sec in range(CLIP_DURATION, 0, -1):
        frame = build_frame(left_label, right_label, left_img, right_img, countdown=sec)
        frame_rgb = frame.tobytes()
        for _ in range(FPS):
            frames_bytes += frame_rgb
        freq = 1200 if sec == 1 else 880
        audio_bytes += make_beep_pcm(freq=freq)

    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "pipe:0",
        "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", audio_path,
        "-vcodec", "mpeg4", "-q:v", "8",
        "-acodec", "aac",
        "-shortest", out_path
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.communicate(input=frames_bytes)
    logger.info(f"Clip {index} done")
    return out_path


def concat_with_ffmpeg(clip_paths, tmp_dir):
    logger.info("Concatenating clips")
    list_file = os.path.join(tmp_dir, "clips.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    out_path = os.path.join(tmp_dir, "final_vs.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", out_path
    ], check=True, capture_output=True)
    logger.info("Concat done")
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
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Использовать", callback_data=f"use_{i}"),
            InlineKeyboardButton(text="🔄 Заменить", callback_data=f"replace_{i}")
        ]])
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
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Использовать", callback_data=f"use_{number}"),
        InlineKeyboardButton(text="🔄 Заменить", callback_data=f"replace_{number}")
    ]])
    await callback.message.edit_text(f"Вариант {number}\n\n{new_variant}", reply_markup=kb)
    await callback.answer()


@dp.message(F.text == "🎨 Сгенерировать видео")
async def generate_video(message: Message):
    user_id = message.from_user.id
    if user_id not in user_choices or len(user_choices[user_id]) < 5:
        count = len(user_choices.get(user_id, []))
        await message.answer(f"Нужно выбрать 5 карточек. Сейчас: {count}/5")
        return

    await message.answer("🎬 Загружаю фото и генерирую видео...\n⏳ Подожди 2-3 минуты!")

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            clip_paths = []
            for idx, variant in enumerate(user_choices[user_id], start=1):
                left_label, right_label = parse_vs(variant)
                await message.answer(f"🖼 Батл {idx}/5: {left_label} VS {right_label}")
                left_img = fetch_unsplash_image(left_label)
                right_img = fetch_unsplash_image(right_label)
                clip_path = build_battle_clip(
                    left_label, right_label, left_img, right_img, tmp_dir, idx)
                clip_paths.append(clip_path)

            await message.answer("🎞 Склеиваю финальное видео...")
            final_path = concat_with_ffmpeg(clip_paths, tmp_dir)

            await message.answer_video(
                FSInputFile(final_path, filename="vs_battle.mp4"),
                caption="🔥 VS Battle — 25 секунд\n#shorts #vs #battle",
                supports_streaming=True
            )
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка:\n{e}")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
