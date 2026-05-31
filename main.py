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
import json
import urllib.request
import urllib.parse
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
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

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
    "Happiness": "smile joy celebration",
    "Loyalty": "friendship trust handshake",
    "Ambition": "success businessman skyscraper",
    "Revenge": "dark storm angry",
    "Forgiveness": "peace light calm",
    "Power": "strength leader crowd",
    "Freedom": "open road sky travel",
    "Hustle": "work hard grind office",
    "Balance": "yoga zen nature",
    "Alpha": "confident leader strong",
    "Sigma": "lone wolf solitary dark",
    "Truth": "light clarity mirror",
    "Kindness": "help charity hands",
    "Passion": "fire energy dance",
    "Reason": "chess logic science",
    "Silence": "quiet empty room",
    "Reaction": "crowd reaction surprise",
    "Respected": "leader podium award",
    "Loved": "couple hug family",
    "Rich": "luxury mansion yacht",
    "Poor": "friendship community together",
    "Ferrari": "red ferrari sports car",
    "Lamborghini": "lamborghini supercar",
    "iPhone": "apple iphone smartphone",
    "Android": "samsung android phone",
    "Nike": "nike shoes sport",
    "Adidas": "adidas sneakers",
    "Rolls Royce": "rolls royce luxury car",
    "Bugatti": "bugatti supercar",
    "Las Vegas": "las vegas night lights",
    "Dubai": "dubai skyline luxury",
    "Gym": "gym workout fitness",
    "Couch": "relax home sofa",
    "Billionaire": "billionaire yacht mansion",
    "Rock Star": "rock concert stage",
    "Leader": "leadership team business",
    "Lone Wolf": "alone dark forest",
}

user_choices = {}
variant_storage = {}
used_variants = {}
pending_videos = {}  # хранит пути к видео ожидающим публикации


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
    headers = {"Authorization": PEXELS_API_KEY}
    search_query = QUERY_MAP.get(query, query)

    for q in [search_query, query.split()[0], "dark dramatic"]:
        try:
            r = session.get(
                "https://api.pexels.com/v1/search",
                params={"query": q, "per_page": 15, "orientation": "landscape"},
                headers=headers, timeout=20
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if photos:
                photo = random.choice(photos)
                img_url = photo["src"]["large"]
                img_r = session.get(img_url, timeout=20)
                img_r.raise_for_status()
                logger.info(f"Image fetched for: {query}")
                return Image.open(io.BytesIO(img_r.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"Pexels failed for '{q}': {e}")
            continue

    img = Image.new("RGB", (W, H // 2), (20, 20, 20))
    return img


def fit_image(im, w, h):
    im = im.copy()
    ratio_w = w / im.width
    ratio_h = h / im.height
    ratio = max(ratio_w, ratio_h)
    new_w = int(im.width * ratio)
    new_h = int(im.height * ratio)
    im = im.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - w) // 2
    y = (new_h - h) // 2
    return im.crop((x, y, x + w, y + h))


def draw_emoji_text(draw, text, x, y, font, fill, anchor="mm", stroke_width=0, stroke_fill=None):
    """Рисует текст с поддержкой базовых символов."""
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor,
              stroke_width=stroke_width, stroke_fill=stroke_fill)


def build_frame(left_label, right_label, left_img, right_img,
                countdown=None, show_result=False,
                left_pct=None, right_pct=None):
    HALF = H // 2
    card = Image.new("RGB", (W, H), (0, 0, 0))
    card.paste(fit_image(left_img, W, HALF), (0, 0))
    card.paste(fit_image(right_img, W, HALF), (0, HALF))

    # Оверлей вокруг VS зоны
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    ov.rectangle([0, HALF - 130, W, HALF + 130], fill=(0, 0, 0, 210))

    # Если результат — подсвечиваем победителя
    if show_result and left_pct is not None and right_pct is not None:
        if left_pct >= right_pct:
            ov.rectangle([0, 0, W, HALF - 130], fill=(0, 180, 0, 60))
        else:
            ov.rectangle([0, HALF + 130, W, H], fill=(0, 180, 0, 60))

    card = Image.alpha_composite(card.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(card)

    try:
        font_vs    = ImageFont.truetype(FONT_PATH, 100)
        font_label = ImageFont.truetype(FONT_PATH, 48)
        font_timer = ImageFont.truetype(FONT_PATH, 140)
        font_pct   = ImageFont.truetype(FONT_PATH, 72)
        font_cta   = ImageFont.truetype(FONT_PATH, 32)
        font_icon  = ImageFont.truetype(FONT_PATH, 56)
    except Exception:
        font_vs = font_label = font_timer = font_pct = font_cta = font_icon = ImageFont.load_default()

    # Красная линия
    draw.line([(0, HALF), (W, HALF)], fill=(220, 30, 30), width=6)

    # VS
    draw.text((W//2, HALF), "VS", font=font_vs, fill=(220, 30, 30), anchor="mm",
              stroke_width=4, stroke_fill=(0, 0, 0))

    if show_result and left_pct is not None:
        # Показываем проценты
        left_color = (0, 220, 0) if left_pct >= right_pct else (255, 255, 255)
        right_color = (0, 220, 0) if right_pct > left_pct else (255, 255, 255)

        draw.text((W//2, HALF - 80), f"{left_label.upper()}  {left_pct}%",
                  font=font_pct, fill=left_color, anchor="mb",
                  stroke_width=3, stroke_fill=(0, 0, 0))
        draw.text((W//2, HALF + 80), f"{right_pct}%  {right_label.upper()}",
                  font=font_pct, fill=right_color, anchor="mt",
                  stroke_width=3, stroke_fill=(0, 0, 0))
    else:
        # Обычные названия
        draw.text((W//2, HALF - 80), left_label.upper(), font=font_label,
                  fill=(255, 255, 255), anchor="mb",
                  stroke_width=3, stroke_fill=(0, 0, 0))
        draw.text((W//2, HALF + 80), right_label.upper(), font=font_label,
                  fill=(255, 255, 255), anchor="mt",
                  stroke_width=3, stroke_fill=(0, 0, 0))

    # Призыв к действию
    if not show_result:
        # Лайк для верхней
        draw.text((W//2, 40), "👍 LIKE", font=font_cta,
                  fill=(255, 255, 100), anchor="mt",
                  stroke_width=2, stroke_fill=(0, 0, 0))
        # Комент для нижней
        draw.text((W//2, H - 40), "💬 COMMENT", font=font_cta,
                  fill=(255, 255, 100), anchor="mb",
                  stroke_width=2, stroke_fill=(0, 0, 0))

    # Таймер — левый верхний угол
    if countdown is not None and not show_result:
        draw.text((50, 50), str(countdown), font=font_timer,
                  fill=(255, 50, 50), anchor="lt",
                  stroke_width=6, stroke_fill=(0, 0, 0))

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

    # Рандомные проценты
    left_pct = random.randint(30, 70)
    right_pct = 100 - left_pct

    frames_bytes = b""
    audio_bytes = b""

    # 5 → 1 с таймером
    for sec in range(CLIP_DURATION, 0, -1):
        frame = build_frame(left_label, right_label, left_img, right_img, countdown=sec)
        frame_rgb = frame.tobytes()
        for _ in range(FPS):
            frames_bytes += frame_rgb
        freq = 1200 if sec == 1 else 880
        audio_bytes += make_beep_pcm(freq=freq)

    # 0 — результат (1 секунда)
    result_frame = build_frame(left_label, right_label, left_img, right_img,
                               countdown=0, show_result=True,
                               left_pct=left_pct, right_pct=right_pct)
    result_rgb = result_frame.tobytes()
    for _ in range(FPS):
        frames_bytes += result_rgb
    # Финальный бип — высокий
    audio_bytes += make_beep_pcm(freq=1500, duration=0.3)
    silence_len = 44100 - int(44100 * 0.3)
    audio_bytes += (np.zeros(silence_len * 2, dtype=np.int16)).tobytes()

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

    music_path = download_music(tmp_dir)
    out_path = os.path.join(tmp_dir, "final_vs.mp4")

    if music_path:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", merged_path,
            "-i", music_path,
            "-filter_complex", "[1:a]volume=0.25[music];[0:a][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest", out_path
        ], check=True, capture_output=True)
    else:
        os.rename(merged_path, out_path)

    logger.info("Concat done")
    return out_path


def get_youtube_access_token():
    """Получаем access token через refresh token."""
    data = urllib.parse.urlencode({
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        return result["access_token"]


def generate_video_metadata(variants):
    """Генерируем название и описание для YouTube."""
    topics = " | ".join([f"{v.split(' VS ')[0]} VS {v.split(' VS ')[1]}" for v in variants[:3]])
    title = f"🔥 {variants[0]} — Which Side Are You On? #shorts"
    description = f"""Every day we put two choices head-to-head — and YOU decide the winner!

Today's battles:
{chr(10).join([f'⚡ {v}' for v in variants])}

👍 LIKE for the top option
💬 COMMENT for the bottom option

Watch till the end to see the results!

🔔 Subscribe for daily battles → @BattleVoteUSA

#shorts #vs #battle #wouldyourather #pickone #chooseside #viral #trending #battlevote #versus #dailybattle #pickside"""

    return title, description


def upload_to_youtube(video_path, title, description):
    """Загружаем видео на YouTube."""
    logger.info("Getting YouTube access token")
    access_token = get_youtube_access_token()

    # Метаданные видео
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["shorts", "vs", "battle", "wouldyourather", "pickone", "viral", "trending", "battlevote"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    # Multipart upload
    boundary = "batch_boundary_xyz"
    metadata_json = json.dumps(metadata).encode()
    with open(video_path, "rb") as f:
        video_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode() + metadata_json + (
        f"\r\n--{boundary}\r\n"
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + video_data + f"\r\n--{boundary}--".encode()

    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Content-Length": str(len(body))
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())
        video_id = result.get("id", "unknown")
        logger.info(f"Uploaded to YouTube: {video_id}")
        return f"https://www.youtube.com/shorts/{video_id}"


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("🎲 Генератор VS запущен", reply_markup=keyboard)


@dp.message(F.text == "🎲 Генерация вариантов")
async def generate(message: Message):
    user_id = message.from_user.id
    user_choices[user_id] = []
    variant_storage[user_id] = {}

    if user_id not in used_variants:
        used_variants[user_id] = set()

    available = [v for v in VS_POOL if v not in used_variants[user_id]]
    if len(available) < 5:
        used_variants[user_id] = set()
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
        tmp_dir = tempfile.mkdtemp()
        clip_paths = []
        variants = user_choices[user_id]

        for idx, variant in enumerate(variants, start=1):
            left_label, right_label = parse_vs(variant)
            await message.answer(f"🖼 Батл {idx}/5: {left_label} VS {right_label}")
            left_img = fetch_image(left_label)
            right_img = fetch_image(right_label)
            clip_path = build_battle_clip(
                left_label, right_label, left_img, right_img, tmp_dir, idx)
            clip_paths.append(clip_path)

        await message.answer("🎞 Склеиваю финальное видео...")
        final_path = concat_with_ffmpeg(clip_paths, tmp_dir)

        # Генерируем метаданные
        title, description = generate_video_metadata(variants)

        # Сохраняем для публикации
        pending_videos[user_id] = {
            "path": final_path,
            "tmp_dir": tmp_dir,
            "title": title,
            "description": description
        }

        # Отправляем превью в Telegram
        await message.answer_video(
            FSInputFile(final_path, filename="vs_battle.mp4"),
            caption=f"🎬 Готово! Проверь видео.\n\n📝 Название:\n{title}\n\n📄 Описание будет добавлено автоматически.",
            supports_streaming=True
        )

        # Кнопки публикации с планировщиком
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Сейчас", callback_data="publish_now"),
                InlineKeyboardButton(text="⏰ Запланировать", callback_data="publish_schedule"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_publish")
            ]
        ])
        await message.answer(
            "Когда публиковать на YouTube?",
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка:\n{e}")


@dp.callback_query(F.data == "publish_now")
async def publish_now(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in pending_videos:
        await callback.answer("Видео не найдено. Сгенерируй заново.")
        return

    await callback.answer("Публикую...")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("🚀 Загружаю на YouTube...")

    try:
        video_data = pending_videos[user_id]
        url = upload_to_youtube(
            video_data["path"],
            video_data["title"],
            video_data["description"]
        )
        del pending_videos[user_id]
        await callback.message.answer(f"✅ Опубликовано!\n\n{url}")
    except Exception as e:
        logger.error(f"YouTube upload error: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка публикации:\n{e}")


@dp.callback_query(F.data == "publish_schedule")
async def publish_schedule(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in pending_videos:
        await callback.answer("Видео не найдено.")
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    # Предлагаем время публикации (EST — американское время)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌅 9:00 AM EST", callback_data="sched_9"),
            InlineKeyboardButton(text="☀️ 12:00 PM EST", callback_data="sched_12"),
        ],
        [
            InlineKeyboardButton(text="🌆 3:00 PM EST", callback_data="sched_15"),
            InlineKeyboardButton(text="🌇 6:00 PM EST", callback_data="sched_18"),
        ],
        [
            InlineKeyboardButton(text="🌙 9:00 PM EST", callback_data="sched_21"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_publish"),
        ]
    ])
    await callback.message.answer(
        "⏰ Выбери время публикации (EST — США):

"
        "Лучшее время для американской аудитории: 3:00 PM или 6:00 PM EST",
        reply_markup=kb
    )


@dp.callback_query(F.data.startswith("sched_"))
async def schedule_publish(callback: CallbackQuery):
    import datetime
    user_id = callback.from_user.id
    hour_est = int(callback.data.split("_")[1])

    if user_id not in pending_videos:
        await callback.answer("Видео не найдено.")
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    # EST = UTC-5 (зима) / UTC-4 (лето)
    now_utc = datetime.datetime.utcnow()
    # Определяем DST приблизительно
    is_dst = 3 <= now_utc.month <= 11
    utc_offset = 4 if is_dst else 5
    target_hour_utc = (hour_est + utc_offset) % 24

    # Ближайшее время публикации
    target = now_utc.replace(hour=target_hour_utc, minute=0, second=0, microsecond=0)
    if target <= now_utc:
        target += datetime.timedelta(days=1)

    delay_seconds = (target - now_utc).total_seconds()
    delay_minutes = int(delay_seconds / 60)
    delay_hours = delay_minutes // 60
    delay_mins = delay_minutes % 60

    await callback.message.answer(
        f"⏰ Видео будет опубликовано в {hour_est}:00 EST
"
        f"Осталось: {delay_hours}ч {delay_mins}мин

"
        f"Не выключай бота!"
    )

    # Ждём и публикуем
    await asyncio.sleep(delay_seconds)

    try:
        if user_id in pending_videos:
            video_data = pending_videos[user_id]
            url = upload_to_youtube(
                video_data["path"],
                video_data["title"],
                video_data["description"]
            )
            del pending_videos[user_id]
            await callback.message.answer(f"✅ Опубликовано по расписанию!\n\n{url}")
    except Exception as e:
        logger.error(f"Scheduled upload error: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка публикации по расписанию:\n{e}")


@dp.callback_query(F.data == "cancel_publish")
async def cancel_publish(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_videos:
        del pending_videos[user_id]
    await callback.answer("Отменено")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Публикация отменена.")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
