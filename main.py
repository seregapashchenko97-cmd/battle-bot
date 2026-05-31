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
import datetime
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
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCPq1H-SmJ_N7UxImtFHrdeQ")

bot = Bot(BOT_TOKEN, request_timeout=120)
dp = Dispatcher()

FONT_PATH = "Anton-Regular.ttf"
CLIP_DURATION = 5
FPS = 20
W, H = 720, 1280

# Слоты публикации в EST (час)
QUEUE_SLOTS = [9, 15, 21]

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Собрать видео")],
        [KeyboardButton(text="🎲 Выбрать темы вручную")]
    ],
    resize_keyboard=True
)

VS_POOL = [
    "Money VS Love", "Fame VS Happiness", "Loyalty VS Ambition",
    "Revenge VS Forgiveness", "Power VS Freedom", "Hustle VS Balance",
    "Alpha VS Sigma", "Truth VS Kindness", "Passion VS Reason",
    "Silence VS Reaction", "Respected VS Loved", "Rich Alone VS Poor Together",
    "Short Pleasure VS Long Success", "Fake Smile VS Real Pain",
    "Hard Truth VS Sweet Lie", "One Real Friend VS Thousand Fans",
    "Safe Life VS Wild Life", "Street Smart VS Book Smart",
    "Work Hard VS Work Smart", "Live Now VS Plan Forever",
    "Ferrari VS Lamborghini", "iPhone VS Android", "Nike VS Adidas",
    "Rolls Royce VS Bugatti", "Las Vegas VS Dubai", "Gym VS Couch",
    "Billionaire VS Rock Star", "Love At First Sight VS Deep Connection",
    "Die Famous VS Live Unknown", "Leader VS Lone Wolf",
]

QUERY_MAP = {
    "Money": "cash money luxury", "Love": "couple romance",
    "Fame": "spotlight celebrity", "Happiness": "smile joy",
    "Loyalty": "friendship trust", "Ambition": "success business",
    "Revenge": "dark storm", "Forgiveness": "peace calm light",
    "Power": "strength leader", "Freedom": "open road sky",
    "Hustle": "work hard office", "Balance": "yoga zen nature",
    "Alpha": "confident leader", "Sigma": "lone wolf solitary",
    "Truth": "light clarity", "Kindness": "help charity",
    "Passion": "fire energy", "Reason": "chess logic",
    "Silence": "quiet empty", "Reaction": "crowd surprise",
    "Respected": "leader award", "Loved": "couple family",
    "Rich": "luxury mansion", "Poor": "community together",
    "Ferrari": "red ferrari sports car", "Lamborghini": "lamborghini supercar",
    "iPhone": "apple iphone", "Android": "samsung android",
    "Nike": "nike shoes sport", "Adidas": "adidas sneakers",
    "Rolls Royce": "rolls royce luxury", "Bugatti": "bugatti supercar",
    "Las Vegas": "las vegas night", "Dubai": "dubai skyline",
    "Gym": "gym workout fitness", "Couch": "relax home sofa",
    "Billionaire": "billionaire yacht", "Rock Star": "rock concert stage",
    "Leader": "leadership business", "Lone Wolf": "alone forest dark",
    "Fake Smile": "smile mask fake", "Real Pain": "sad alone dark",
    "Hard Truth": "truth mirror honest", "Sweet Lie": "lie sugar candy",
    "Safe Life": "comfortable home safe", "Wild Life": "adventure extreme sport",
    "Short Pleasure": "party fun night", "Long Success": "trophy winner success",
    "Live Now": "party enjoy present", "Plan Forever": "calendar plan future",
    "Die Famous": "celebrity spotlight famous", "Live Unknown": "alone quiet peaceful",
}

# Хранилища
used_variants = {}
pending_videos = {}
publish_queue = {}  # user_id -> список запланированных слотов


def get_session():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def parse_vs(variant):
    parts = variant.split(" VS ")
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("Left", "Right")


def fetch_image(query):
    logger.info(f"Fetching: {query}")
    session = get_session()
    headers = {"Authorization": PEXELS_API_KEY}
    search_query = QUERY_MAP.get(query, query)
    for q in [search_query, query.split()[0], "dramatic dark"]:
        try:
            r = session.get("https://api.pexels.com/v1/search",
                           params={"query": q, "per_page": 15, "orientation": "landscape"},
                           headers=headers, timeout=20)
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if photos:
                img_url = random.choice(photos)["src"]["large"]
                img_r = session.get(img_url, timeout=20)
                img_r.raise_for_status()
                return Image.open(io.BytesIO(img_r.content)).convert("RGB")
        except Exception as e:
            logger.warning(f"Pexels failed '{q}': {e}")
    return Image.new("RGB", (W, H // 2), (20, 20, 20))


def fit_image(im, w, h):
    im = im.copy()
    ratio = max(w / im.width, h / im.height)
    new_w, new_h = int(im.width * ratio), int(im.height * ratio)
    im = im.resize((new_w, new_h), Image.LANCZOS)
    x, y = (new_w - w) // 2, (new_h - h) // 2
    return im.crop((x, y, x + w, y + h))


def build_frame(left_label, right_label, left_img, right_img,
                countdown=None, show_result=False, left_pct=None, right_pct=None):
    HALF = H // 2
    card = Image.new("RGB", (W, H), (0, 0, 0))
    card.paste(fit_image(left_img, W, HALF), (0, 0))
    card.paste(fit_image(right_img, W, HALF), (0, HALF))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ov = ImageDraw.Draw(overlay)
    ov.rectangle([0, HALF - 130, W, HALF + 130], fill=(0, 0, 0, 210))

    if show_result and left_pct is not None:
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
        font_pct   = ImageFont.truetype(FONT_PATH, 64)
        font_cta   = ImageFont.truetype(FONT_PATH, 36)
    except Exception:
        font_vs = font_label = font_timer = font_pct = font_cta = ImageFont.load_default()

    draw.line([(0, HALF), (W, HALF)], fill=(220, 30, 30), width=6)
    draw.text((W//2, HALF), "VS", font=font_vs, fill=(220, 30, 30), anchor="mm",
              stroke_width=4, stroke_fill=(0, 0, 0))

    if show_result and left_pct is not None:
        left_color = (0, 220, 0) if left_pct >= right_pct else (255, 255, 255)
        right_color = (0, 220, 0) if right_pct > left_pct else (255, 255, 255)
        draw.text((W//2, HALF - 75), f"{left_label.upper()}  {left_pct}%",
                  font=font_pct, fill=left_color, anchor="mb",
                  stroke_width=3, stroke_fill=(0, 0, 0))
        draw.text((W//2, HALF + 75), f"{right_pct}%  {right_label.upper()}",
                  font=font_pct, fill=right_color, anchor="mt",
                  stroke_width=3, stroke_fill=(0, 0, 0))
    else:
        draw.text((W//2, HALF - 75), left_label.upper(), font=font_label,
                  fill=(255, 255, 255), anchor="mb",
                  stroke_width=3, stroke_fill=(0, 0, 0))
        draw.text((W//2, HALF + 75), right_label.upper(), font=font_label,
                  fill=(255, 255, 255), anchor="mt",
                  stroke_width=3, stroke_fill=(0, 0, 0))

    if not show_result:
        draw.text((20, HALF - 145), "[ LIKE ]", font=font_cta,
                  fill=(255, 255, 0), anchor="lt",
                  stroke_width=2, stroke_fill=(0, 0, 0))
        draw.text((20, HALF + 145), "[ COMMENT ]", font=font_cta,
                  fill=(255, 255, 0), anchor="lb",
                  stroke_width=2, stroke_fill=(0, 0, 0))

    if countdown is not None and not show_result:
        draw.text((50, 50), str(countdown), font=font_timer,
                  fill=(255, 50, 50), anchor="lt",
                  stroke_width=6, stroke_fill=(0, 0, 0))

    return card


def build_hook_frame(left_label, right_label):
    """Первый фрейм — крючок на весь экран."""
    card = Image.new("RGB", (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(card)

    try:
        font_big = ImageFont.truetype(FONT_PATH, 90)
        font_vs   = ImageFont.truetype(FONT_PATH, 130)
        font_sub  = ImageFont.truetype(FONT_PATH, 55)
    except Exception:
        font_big = font_vs = font_sub = ImageFont.load_default()

    # Красная линия посередине
    draw.line([(0, H//2), (W, H//2)], fill=(220, 30, 30), width=8)

    # WHICH WOULD YOU CHOOSE?
    draw.text((W//2, 120), "WHICH WOULD", font=font_big,
              fill=(255, 255, 255), anchor="mt",
              stroke_width=4, stroke_fill=(0, 0, 0))
    draw.text((W//2, 230), "YOU CHOOSE?", font=font_big,
              fill=(255, 50, 50), anchor="mt",
              stroke_width=4, stroke_fill=(0, 0, 0))

    # Верхний вариант
    draw.text((W//2, H//2 - 100), "TOP:", font=font_sub,
              fill=(255, 255, 100), anchor="mb",
              stroke_width=2, stroke_fill=(0, 0, 0))
    draw.text((W//2, H//2 - 60), left_label.upper(), font=font_sub,
              fill=(255, 255, 255), anchor="mb",
              stroke_width=3, stroke_fill=(0, 0, 0))

    # VS
    draw.text((W//2, H//2), "VS", font=font_vs,
              fill=(220, 30, 30), anchor="mm",
              stroke_width=5, stroke_fill=(0, 0, 0))

    # Нижний вариант
    draw.text((W//2, H//2 + 60), right_label.upper(), font=font_sub,
              fill=(255, 255, 255), anchor="mt",
              stroke_width=3, stroke_fill=(0, 0, 0))
    draw.text((W//2, H//2 + 100), "BOTTOM:", font=font_sub,
              fill=(255, 255, 100), anchor="mt",
              stroke_width=2, stroke_fill=(0, 0, 0))

    # Снизу призыв
    draw.text((W//2, H - 120), "COMMENT YOUR CHOICE", font=font_sub,
              fill=(255, 255, 100), anchor="mb",
              stroke_width=3, stroke_fill=(0, 0, 0))

    return card


def make_beep_pcm(freq=880, sr=44100, duration=0.12):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = (0.4 * np.sin(2 * np.pi * freq * t) * np.linspace(1, 0, len(t))).astype(np.float32)
    silence = np.zeros(sr - len(wave), dtype=np.float32)
    mono = np.concatenate([wave, silence])
    return (np.stack([mono, mono], axis=1) * 32767).astype(np.int16).tobytes()


def build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, index):
    logger.info(f"Building clip {index}")
    out_path = os.path.join(tmp_dir, f"battle_{index:02d}.mp4")
    audio_path = os.path.join(tmp_dir, f"audio_{index}.pcm")

    left_pct = random.randint(30, 70)
    right_pct = 100 - left_pct

    frames_bytes = b""
    audio_bytes = b""

    # Хук — первые 1.5 секунды (30 фреймов)
    hook_frame = build_hook_frame(left_label, right_label)
    hook_bytes = hook_frame.tobytes()
    hook_frames = int(FPS * 1.5)
    for _ in range(hook_frames):
        frames_bytes += hook_bytes
    # Тихий звук для хука
    hook_silence = np.zeros(int(44100 * 1.5) * 2, dtype=np.int16)
    audio_bytes += hook_silence.tobytes()

    for sec in range(CLIP_DURATION, 0, -1):
        frame = build_frame(left_label, right_label, left_img, right_img, countdown=sec)
        for _ in range(FPS):
            frames_bytes += frame.tobytes()
        audio_bytes += make_beep_pcm(freq=1200 if sec == 1 else 880)

    # Результат — 0
    result_frame = build_frame(left_label, right_label, left_img, right_img,
                               countdown=0, show_result=True,
                               left_pct=left_pct, right_pct=right_pct)
    for _ in range(FPS):
        frames_bytes += result_frame.tobytes()
    audio_bytes += make_beep_pcm(freq=1500, duration=0.3)
    audio_bytes += (np.zeros((44100 - int(44100 * 0.3)) * 2, dtype=np.int16)).tobytes()

    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "pipe:0",
        "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", audio_path,
        "-vcodec", "mpeg4", "-q:v", "8", "-acodec", "aac",
        "-shortest", out_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.communicate(input=frames_bytes)
    logger.info(f"Clip {index} done")
    return out_path


def download_music(tmp_dir):
    try:
        r = get_session().get("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", timeout=30)
        r.raise_for_status()
        path = os.path.join(tmp_dir, "music.mp3")
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        logger.warning(f"Music failed: {e}")
        return None


def concat_with_ffmpeg(clip_paths, tmp_dir):
    list_file = os.path.join(tmp_dir, "clips.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")

    merged = os.path.join(tmp_dir, "merged.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", list_file, "-c", "copy", merged],
                   check=True, capture_output=True)

    music = download_music(tmp_dir)
    out = os.path.join(tmp_dir, "final_vs.mp4")

    if music:
        subprocess.run([
            "ffmpeg", "-y", "-i", merged, "-i", music,
            "-filter_complex", "[1:a]volume=0.25[m];[0:a][m]amix=inputs=2:duration=first[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
            "-shortest", out
        ], check=True, capture_output=True)
    else:
        os.rename(merged, out)
    return out


def generate_metadata(variants):
    title = f"{variants[0]} — Which Side Are You On? #shorts"
    desc = "Every day we put two choices head-to-head — YOU decide the winner!\n\n"
    desc += "Today's battles:\n"
    for v in variants:
        desc += f"* {v}\n"
    desc += "\nLIKE for the top | COMMENT for the bottom\n"
    desc += "Watch till the end to see results!\n\n"
    desc += "Subscribe for daily battles @BattleVoteUSA\n\n"
    desc += "#shorts #vs #battle #wouldyourather #pickone #chooseside #viral #battlevote"
    return title, desc


def get_youtube_token():
    data = urllib.parse.urlencode({
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


def upload_to_youtube(video_path, title, description):
    token = get_youtube_token()
    metadata = {
        "snippet": {
            "title": title, "description": description,
            "tags": ["shorts", "vs", "battle", "wouldyourather", "viral", "battlevote"],
            "categoryId": "22",
            "channelId": YOUTUBE_CHANNEL_ID
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    boundary = "bv_boundary_xyz"
    meta_bytes = json.dumps(metadata).encode()
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
    ).encode() + meta_bytes + (
        f"\r\n--{boundary}\r\nContent-Type: video/mp4\r\n\r\n"
    ).encode() + video_bytes + f"\r\n--{boundary}--".encode()

    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Content-Length": str(len(body))
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        vid_id = json.loads(resp.read()).get("id", "unknown")
        return f"https://www.youtube.com/shorts/{vid_id}"


def get_next_slot(user_id):
    """Находим следующий свободный слот по расписанию."""
    now_utc = datetime.datetime.utcnow()
    is_dst = 3 <= now_utc.month <= 11
    utc_offset = 4 if is_dst else 5

    if user_id not in publish_queue:
        publish_queue[user_id] = []

    # Убираем прошедшие слоты
    publish_queue[user_id] = [s for s in publish_queue[user_id] if s["target_utc"] > now_utc]

    busy = [s["hour_est"] for s in publish_queue[user_id] if s["day"] == now_utc.date()]

    # Ищем свободный слот сегодня
    for slot in QUEUE_SLOTS:
        if slot not in busy:
            target_hour_utc = (slot + utc_offset) % 24
            target = now_utc.replace(hour=target_hour_utc, minute=0, second=0, microsecond=0)
            if target > now_utc:
                return slot, target, now_utc.date()

    # Все сегодняшние заняты — берём завтра
    tomorrow = now_utc.date() + datetime.timedelta(days=1)
    busy_tomorrow = [s["hour_est"] for s in publish_queue[user_id] if s["day"] == tomorrow]

    for slot in QUEUE_SLOTS:
        if slot not in busy_tomorrow:
            target_hour_utc = (slot + utc_offset) % 24
            target = datetime.datetime.combine(tomorrow, datetime.time(target_hour_utc, 0))
            return slot, target, tomorrow

    return QUEUE_SLOTS[0], now_utc + datetime.timedelta(days=2), now_utc.date() + datetime.timedelta(days=2)


async def delayed_publish(user_id, slot_id, video_data, target_utc, message):
    now_utc = datetime.datetime.utcnow()
    delay = max(0, (target_utc - now_utc).total_seconds())
    await asyncio.sleep(delay)
    try:
        url = upload_to_youtube(video_data["path"], video_data["title"], video_data["description"])
        publish_queue[user_id] = [s for s in publish_queue.get(user_id, []) if s["id"] != slot_id]
        await message.answer(f"Published! {url}")
    except Exception as e:
        logger.error(f"Scheduled upload error: {e}", exc_info=True)
        await message.answer(f"Publish error: {e}")


async def build_video_for_user(user_id, variants, message):
    """Основная функция сборки видео."""
    try:
        tmp_dir = tempfile.mkdtemp()
        clip_paths = []

        for idx, variant in enumerate(variants, start=1):
            left_label, right_label = parse_vs(variant)
            await message.answer(f"Battle {idx}/5: {left_label} VS {right_label}")
            left_img = fetch_image(left_label)
            right_img = fetch_image(right_label)
            clip_path = build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, idx)
            clip_paths.append(clip_path)

        await message.answer("Merging final video...")
        final_path = concat_with_ffmpeg(clip_paths, tmp_dir)
        title, description = generate_metadata(variants)

        pending_videos[user_id] = {
            "path": final_path,
            "tmp_dir": tmp_dir,
            "title": title,
            "description": description
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📅 Добавить в очередь", callback_data="add_to_queue"),
            InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data="publish_now"),
        ]])

        await message.answer_video(
            FSInputFile(final_path, filename="vs_battle.mp4"),
            caption=f"Ready! Title: {title}",
            supports_streaming=True
        )
        await message.answer("Publish to YouTube?", reply_markup=kb)

    except Exception as e:
        logger.error(f"Build error: {e}", exc_info=True)
        await message.answer(f"Error: {e}")


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("BattleVote Bot ready!", reply_markup=keyboard)


@dp.message(F.text == "🎬 Собрать видео")
async def auto_build(message: Message):
    user_id = message.from_user.id

    if user_id not in used_variants:
        used_variants[user_id] = set()

    available = [v for v in VS_POOL if v not in used_variants[user_id]]
    if len(available) < 5:
        used_variants[user_id] = set()
        available = VS_POOL.copy()

    variants = random.sample(available, 5)
    for v in variants:
        used_variants[user_id].add(v)

    await message.answer(f"Generating video with:\n" + "\n".join(f"* {v}" for v in variants))
    await build_video_for_user(user_id, variants, message)


@dp.message(F.text == "🎲 Выбрать темы вручную")
async def manual_select(message: Message):
    user_id = message.from_user.id
    user_choices_manual = {}

    if user_id not in used_variants:
        used_variants[user_id] = set()

    available = [v for v in VS_POOL if v not in used_variants[user_id]]
    if len(available) < 5:
        used_variants[user_id] = set()
        available = VS_POOL.copy()

    variants = random.sample(available, 5)

    # Сохраняем варианты
    if not hasattr(dp, '_manual_variants'):
        dp._manual_variants = {}
    dp._manual_variants[user_id] = {"options": variants, "selected": []}

    for i, v in enumerate(variants, 1):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Use", callback_data=f"manual_use_{i}"),
            InlineKeyboardButton(text="Skip", callback_data=f"manual_skip_{i}")
        ]])
        await message.answer(f"{i}. {v}", reply_markup=kb)


@dp.callback_query(F.data.startswith("manual_use_"))
async def manual_use(callback: CallbackQuery):
    user_id = callback.from_user.id
    idx = int(callback.data.split("_")[2]) - 1

    if not hasattr(dp, '_manual_variants') or user_id not in dp._manual_variants:
        await callback.answer("Expired")
        return

    data = dp._manual_variants[user_id]
    variant = data["options"][idx]
    if variant not in data["selected"]:
        data["selected"].append(variant)

    count = len(data["selected"])
    await callback.answer(f"Added {count}/5")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    if count == 5:
        await callback.message.answer("5 selected! Building video...")
        await build_video_for_user(user_id, data["selected"], callback.message)
        del dp._manual_variants[user_id]


@dp.callback_query(F.data.startswith("manual_skip_"))
async def manual_skip(callback: CallbackQuery):
    await callback.answer("Skipped")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@dp.callback_query(F.data == "add_to_queue")
async def add_to_queue(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in pending_videos:
        await callback.answer("Video not found.")
        return

    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    video_data = pending_videos.pop(user_id)
    slot_hour, target_utc, target_day = get_next_slot(user_id)
    slot_id = f"{target_day}_{slot_hour}"

    if user_id not in publish_queue:
        publish_queue[user_id] = []

    publish_queue[user_id].append({
        "id": slot_id,
        "hour_est": slot_hour,
        "day": target_day,
        "target_utc": target_utc
    })

    is_dst = 3 <= datetime.datetime.utcnow().month <= 11
    day_str = "Today" if target_day == datetime.datetime.utcnow().date() else "Tomorrow"

    queue_text = f"Added to queue!\n{day_str} at {slot_hour}:00 EST\n\nFull queue:\n"
    for i, s in enumerate(publish_queue[user_id], 1):
        d = "Today" if s["day"] == datetime.datetime.utcnow().date() else "Tomorrow"
        queue_text += f"{i}. {d} {s['hour_est']}:00 EST\n"

    await callback.message.answer(queue_text)

    asyncio.create_task(
        delayed_publish(user_id, slot_id, video_data, target_utc, callback.message)
    )


@dp.callback_query(F.data == "publish_now")
async def publish_now(callback: CallbackQuery):
    user_id = callback.from_user.id

    if user_id not in pending_videos:
        await callback.answer("Video not found.")
        return

    await callback.answer("Publishing...")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await callback.message.answer("Uploading to YouTube...")

    try:
        video_data = pending_videos.pop(user_id)
        url = upload_to_youtube(video_data["path"], video_data["title"], video_data["description"])
        await callback.message.answer(f"Published!\n{url}")
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        await callback.message.answer(f"Error: {e}")


AUTOPILOT_USER_ID = int(os.getenv("AUTOPILOT_USER_ID", "0"))  # твой Telegram user_id
AUTOPILOT_ENABLED = os.getenv("AUTOPILOT_ENABLED", "false").lower() == "true"


async def autopilot():
    """Автопилот — генерирует и публикует 3 видео в день по расписанию EST."""
    if not AUTOPILOT_ENABLED or not AUTOPILOT_USER_ID:
        return

    logger.info("Autopilot started")

    while True:
        now_utc = datetime.datetime.utcnow()
        is_dst = 3 <= now_utc.month <= 11
        utc_offset = 4 if is_dst else 5

        # Ближайший слот
        next_target = None
        next_slot = None

        for slot in QUEUE_SLOTS:
            target_hour_utc = (slot + utc_offset) % 24
            target = now_utc.replace(hour=target_hour_utc, minute=0, second=0, microsecond=0)
            if target <= now_utc:
                target += datetime.timedelta(days=1)
            if next_target is None or target < next_target:
                next_target = target
                next_slot = slot

        delay = (next_target - now_utc).total_seconds()
        hours = int(delay // 3600)
        mins = int((delay % 3600) // 60)
        logger.info(f"Autopilot: next publish at {next_slot}:00 EST (in {hours}h {mins}m)")

        await asyncio.sleep(delay)

        # Генерируем видео
        try:
            user_id = AUTOPILOT_USER_ID

            if user_id not in used_variants:
                used_variants[user_id] = set()

            available = [v for v in VS_POOL if v not in used_variants[user_id]]
            if len(available) < 5:
                used_variants[user_id] = set()
                available = VS_POOL.copy()

            variants = random.sample(available, 5)
            for v in variants:
                used_variants[user_id].add(v)

            logger.info(f"Autopilot generating: {variants}")
            await bot.send_message(user_id, f"Autopilot: generating {next_slot}:00 EST video...")

            tmp_dir = tempfile.mkdtemp()
            clip_paths = []

            for idx, variant in enumerate(variants, start=1):
                left_label, right_label = parse_vs(variant)
                left_img = fetch_image(left_label)
                right_img = fetch_image(right_label)
                clip_path = build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, idx)
                clip_paths.append(clip_path)

            final_path = concat_with_ffmpeg(clip_paths, tmp_dir)
            title, description = generate_metadata(variants)

            url = upload_to_youtube(final_path, title, description)
            await bot.send_message(user_id, f"Autopilot published!\n{url}")
            logger.info(f"Autopilot published: {url}")

        except Exception as e:
            logger.error(f"Autopilot error: {e}", exc_info=True)
            try:
                await bot.send_message(AUTOPILOT_USER_ID, f"Autopilot error: {e}")
            except Exception:
                pass

        await asyncio.sleep(60)  # небольшая пауза чтобы не попасть в тот же слот


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    if AUTOPILOT_ENABLED:
        asyncio.create_task(autopilot())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
