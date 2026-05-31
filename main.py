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
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

from aiogram.client.default import DefaultBotProperties
bot = Bot(BOT_TOKEN, request_timeout=120)
dp = Dispatcher()

FONT_PATH = "Anton-Regular.ttf"
CLIP_DURATION = 5
FPS = 20
W, H = 720, 1280

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎲 Генерация вариантов")],
        [KeyboardButton(text="🎨 Сгенерировать видео")]
    ],
    resize_keyboard=True
)

VS_POOL = [
    "Money VS Love",
    "Fame VS Happiness",
    "Loyalty VS Ambition",
    "Revenge VS Forgiveness",
    "Power VS Freedom",
    "Hustle VS Balance",
    "Alpha VS Sigma",
    "Truth VS Kindness",
    "Passion VS Reason",
    "Silence VS Reaction",
    "Respected VS Loved",
    "Rich Alone VS Poor Together",
    "Short Pleasure VS Long Success",
    "Fake Smile VS Real Pain",
    "Hard Truth VS Sweet Lie",
    "One Real Friend VS Thousand Fans",
    "Safe Life VS Wild Life",
    "Street Smart VS Book Smart",
    "Work Hard VS Work Smart",
    "Live Now VS Plan Forever",
    "Ferrari VS Lamborghini",
    "iPhone VS Android",
    "Nike VS Adidas",
    "Rolls Royce VS Bugatti",
    "Las Vegas VS Dubai",
    "Gym VS Couch",
    "Billionaire VS Rock Star",
    "Love At First Sight VS Deep Connection",
    "Die Famous VS Live Unknown",
    "Leader VS Lone Wolf",
]

QUERY_MAP = {
    "Money": "cash money luxury",
    "Love": "couple romance",
    "Fame": "spotlight celebrity crowd",
    "Privacy": "alone solitude peaceful",
    "Risk": "extreme sport danger",
    "Safety": "protection secure calm",
    "Hustle": "work hard grind",
    "Balance": "yoga zen nature",
    "Loyalty": "friendship trust",
    "Ambition": "success businessman",
    "Truth": "light clarity",
    "Kindness": "help charity",
    "Freedom": "open road travel sky",
    "Security": "home safe family",
    "Passion": "fire energy dance",
    "Stability": "house family stability",
    "Revenge": "dark angry storm",
    "Forgiveness": "peace white light",
    "Logic": "chess math science",
    "Intuition": "meditation spiritual",
    "Power": "strength muscle leader",
    "Wisdom": "books elder nature",
    "Success": "trophy winner podium",
    "Happiness": "smile laugh friends",
    "Alpha": "lion strong leader",
    "Sigma": "lone wolf solitary",
    "Ferrari": "red ferrari sports car",
    "Lamborghini": "lamborghini supercar",
    "iPhone": "apple iphone smartphone",
    "Android": "samsung android phone",
    "Nike": "nike shoes sport",
    "Adidas": "adidas sneakers",
    "Batman": "dark night city",
    "Spider-Man": "city rooftop hero",
    "Ocean": "ocean waves blue",
    "Mountains": "mountain peak snow",
    "Coffee": "coffee cup morning",
    "Energy Drink": "energy drink neon",
    "Leader": "leadership team business",
    "Billionaire": "yacht luxury mansion",
    "Growth": "plant growing success",
    "Night Owl": "night city dark",
    "Day Person": "sunrise morning fresh",
}

user_choices = {}
variant_storage = {}
used_variants = {}  # отслеживаем использованные темы


def get_session():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def parse_vs(variant):
    parts = variant.split(" VS ")
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("Left", "Right")


def fetch_image(query):
    logger.info(f"Fetching image for: {query}")
    session = get_session()
    headers = {
        "Authorization": PEXELS_API_KEY
    }
    # Используем маппинг для лучших результатов
    search_query = QUERY_MAP.get(query, query)
    
    for q in [search_query, query.split()[0], "dark dramatic"]:
        try:
            r = session.get(
                "https://api.pexels.com/v1/search",
                params={"query": q, "per_page": 15, "orientation": "landscape"},
                headers=headers,
                timeout=20
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if photos:
                # Берём случайное фото из результатов
                photo = random.choice(photos)
                img_url = photo["src"]["large"]
                img_r = session.get(img_url, timeout=20)
                img_r.raise_for_status()
                logger.info(f"Image fetched for: {query}")
                return Image.open(io.BytesIO(img_r.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"Pexels failed for '{q}': {e}")
            continue
    
    # Тёмная заглушка
    img = Image.new("RGB", (W, H // 2), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 60)
    except Exception:
        font = ImageFont.load_default()
    draw.text((W//2, H//4), query.upper(), font=font, fill=(80, 80, 80), anchor="mm")
    return img


def fit_image(im, w, h):
    """Растягиваем картинку чтобы заполнить всю область (crop по центру)."""
    im = im.copy()
    # Масштабируем так чтобы заполнить весь прямоугольник
    ratio_w = w / im.width
    ratio_h = h / im.height
    ratio = max(ratio_w, ratio_h)
    new_w = int(im.width * ratio)
    new_h = int(im.height * ratio)
    im = im.resize((new_w, new_h), Image.LANCZOS)
    # Обрезаем по центру
    x = (new_w - w) // 2
    y = (new_h - h) // 2
    im = im.crop((x, y, x + w, y + h))
    return im


def build_frame(left_label, right_label, left_img, right_img, countdown=None):
    HALF = H // 2
    card = Image.new("RGB", (W, H), (0, 0, 0))

    # Картинки заполняют всё пространство до красной линии
    top = fit_image(left_img, W, HALF)
    bot = fit_image(right_img, W, HALF)
    card.paste(top, (0, 0))
    card.paste(bot, (0, HALF))

    draw = ImageDraw.Draw(card)

    try:
        fvs = ImageFont.truetype(FONT_PATH, 120)
        flb = ImageFont.truetype(FONT_PATH, 55)
        ftm = ImageFont.truetype(FONT_PATH, 160)
    except Exception:
        fvs = flb = ftm = ImageFont.load_default()

    # Тёмная полоса только под текст у линии
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([0, HALF - 120, W, HALF + 120], fill=(0, 0, 0, 200))
    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(card)

    # Красная линия
    draw.line([(0, HALF), (W, HALF)], fill=(220, 30, 30), width=8)

    # VS
    draw.text((W//2, HALF), "VS", font=fvs, fill=(220, 30, 30), anchor="mm",
              stroke_width=4, stroke_fill=(0, 0, 0))

    # Названия
    draw.text((W//2, HALF - 100), left_label.upper(), font=flb,
              fill=(255, 255, 255), anchor="mb", stroke_width=3, stroke_fill=(0, 0, 0))
    draw.text((W//2, HALF + 100), right_label.upper(), font=flb,
              fill=(255, 255, 255), anchor="mt", stroke_width=3, stroke_fill=(0, 0, 0))

    # Таймер левый верхний угол
    if countdown is not None:
        draw.text((50, 50), str(countdown), font=ftm,
                  fill=(255, 50, 50), anchor="lt", stroke_width=6, stroke_fill=(0, 0, 0))
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


def download_music(tmp_dir):
    """Скачиваем бесплатный драматичный трек."""
    music_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    music_path = os.path.join(tmp_dir, "music.mp3")
    try:
        session = get_session()
        r = session.get(music_url, timeout=30)
        r.raise_for_status()
        with open(music_path, "wb") as f:
            f.write(r.content)
        return music_path
    except Exception as e:
        logger.warning(f"Music download failed: {e}")
        return None


def concat_with_ffmpeg(clip_paths, tmp_dir):
    logger.info("Concatenating clips")
    list_file = os.path.join(tmp_dir, "clips.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    merged_path = os.path.join(tmp_dir, "merged.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", merged_path
    ], check=True, capture_output=True)

    # Добавляем музыку
    music_path = download_music(tmp_dir)
    out_path = os.path.join(tmp_dir, "final_vs.mp4")

    if music_path:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", merged_path,
            "-i", music_path,
            "-filter_complex", "[1:a]volume=0.3[music];[0:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            out_path
        ], check=True, capture_output=True)
    else:
        os.rename(merged_path, out_path)

    logger.info("Concat done")
    return out_path


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🎲 Генератор VS запущен", reply_markup=keyboard)


@dp.message(F.text == "🎲 Генерация вариантов")
async def generate(message: Message):
    user_id = message.from_user.id
    user_choices[user_id] = []
    variant_storage[user_id] = {}

    # Избегаем повторов — исключаем уже использованные темы
    if user_id not in used_variants:
        used_variants[user_id] = set()

    available = [v for v in VS_POOL if v not in used_variants[user_id]]
    if len(available) < 5:
        used_variants[user_id] = set()  # сбрасываем если закончились
        available = VS_POOL.copy()

    variants = random.sample(available, 5)
    for v in variants:
        used_variants[user_id].add(v)
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

    if user_id not in variant_storage or number not in variant_storage.get(user_id, {}):
        await callback.answer("Устарело, генерируй заново")
        return

    variant = variant_storage[user_id][number]
    if variant not in user_choices[user_id]:
        user_choices[user_id].append(variant)

    count = len(user_choices[user_id])
    await callback.answer(f"Выбрано {count}/5")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

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
                left_img = fetch_image(left_label)
                right_img = fetch_image(right_label)
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
