import asyncio
import html
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

import edge_tts
import requests
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from gtts import gTTS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
VOICE = os.getenv("VOICE", "en-US-BrianNeural")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").lower()
VOICE_SPEED = float(os.getenv("VOICE_SPEED", "0.92"))
EDGE_RATE = os.getenv("EDGE_RATE", "-12%")
EDGE_PITCH = os.getenv("EDGE_PITCH", "-5Hz")
ALLOW_GTTS_FALLBACK = os.getenv("ALLOW_GTTS_FALLBACK", "true").lower() == "true"
VIDEO_SPEED = float(os.getenv("VIDEO_SPEED", "1.35"))
SUBTITLE_WORDS = int(os.getenv("SUBTITLE_WORDS", "3"))
VIDEO_SECONDS = int(os.getenv("VIDEO_SECONDS", "45"))
STORY_TARGET_WORDS = int(os.getenv("STORY_TARGET_WORDS", "115"))
MIN_AUDIO_SECONDS = float(os.getenv("MIN_AUDIO_SECONDS", "42"))
MAX_PARALLEL_GENERATIONS = int(os.getenv("MAX_PARALLEL_GENERATIONS", "1"))
AUTOPILOT_ENABLED = os.getenv("AUTOPILOT_ENABLED", "false").lower() == "true"
AUTOPILOT_USER_ID = int(os.getenv("AUTOPILOT_USER_ID", "0"))
AUTOPILOT_TOPICS = [x.strip() for x in os.getenv("AUTOPILOT_TOPICS", "").split(",") if x.strip()]

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")

YOUTUBE_UPLOAD_ENABLED = os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").lower() == "true"
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "24")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

# Layout: "split" = gameplay bottom half + subtitles top half
#         "overlay" = gameplay fullscreen + subtitles center
LAYOUT_MODE = os.getenv("LAYOUT_MODE", "split").lower()

# Comma-separated YouTube URLs for gameplay footage
# Defaults: popular long Minecraft + Subway Surfers gameplay videos
_default_gameplay = ",".join([
    "https://www.youtube.com/watch?v=n8X9_MgEdCg",  # Minecraft parkour 1h
    "https://www.youtube.com/watch?v=mUBmEJRJDhA",  # Subway Surfers 1h
    "https://www.youtube.com/watch?v=Hc6J4kDFB6o",  # Minecraft satisfying 1h
    "https://www.youtube.com/watch?v=tCnvbGBDsq4",  # Subway Surfers 2h
])
GAMEPLAY_URLS_RAW = os.getenv("GAMEPLAY_URLS", _default_gameplay)
GAMEPLAY_URLS = [u.strip() for u in GAMEPLAY_URLS_RAW.split(",") if u.strip()]

# Local cache dir for downloaded gameplay (persists between generations)
GAMEPLAY_CACHE_DIR = Path(os.getenv("GAMEPLAY_CACHE_DIR", "/tmp/gameplay_cache"))
GAMEPLAY_CACHE_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
FPS = 30

AUTOPILOT_SCHEDULE_UTC = [13, 19, 0]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

bot = Bot(BOT_TOKEN, request_timeout=300)
dp = Dispatcher()
active_users: set[int] = set()
last_generated: dict[int, dict] = {}
autopilot_fired: dict[str, set[int]] = {}


# ── VIRAL STORIES ─────────────────────────────────────────────────────────────

STRONG_CONFESSIONS = [
    {
        "label": "cheating wife",
        "hook": "My wife asked me to fix her laptop. The browser history destroyed our marriage.",
        "beats": [
            "She said it was running slow.",
            "I opened the browser.",
            "The first tab was a hotel booking confirmation.",
            "The second tab was a text conversation screenshot saved as a photo.",
            "I recognized the name immediately.",
            "It was my best friend.",
            "I checked the date on the hotel receipt.",
            "It was our anniversary weekend.",
            "She had told me she was visiting her sick mother.",
        ],
        "twist": "When I confronted her, she said at least he made her feel something.",
        "closer": "I closed the laptop, called a lawyer, and never mentioned the hotel.",
    },
    {
        "label": "cheating husband",
        "hook": "I found a receipt for a diamond necklace my husband never gave me.",
        "beats": [
            "It fell out of his coat pocket.",
            "Same store I always hinted about.",
            "Same style I saved on my phone.",
            "I waited three months.",
            "No necklace ever appeared.",
            "Then his coworker posted a photo at their office Christmas party.",
            "She was wearing it.",
            "My husband was standing right next to her.",
            "His hand was on her back.",
        ],
        "twist": "He had already told her I knew nothing and we were basically separated.",
        "closer": "I wore the receipt to the next office party. Around my neck. Framed.",
    },
    {
        "label": "best friend betrayal",
        "hook": "My best friend gave a speech at my wedding. I found out two years later what he left out.",
        "beats": [
            "Everyone cried.",
            "He talked about loyalty and love.",
            "He hugged me at the altar.",
            "Two years later my wife filed for divorce.",
            "I asked her why.",
            "She handed me her phone.",
            "There were 847 messages between them.",
            "Starting the week before our wedding.",
            "The last message was from the morning of.",
        ],
        "twist": "He wrote, after today you belong to someone else, but not really.",
        "closer": "The speech is still on YouTube. I report it every year on our anniversary.",
    },
    {
        "label": "work affair",
        "hook": "My husband said his coworker was just a friend. Then I got her accidentally sent text.",
        "beats": [
            "It came to my number at 11pm.",
            "It said, I can still smell your shirt.",
            "She realized immediately and sent three question marks.",
            "I replied, wrong number.",
            "Then I forwarded it to my husband.",
            "He called me in four seconds.",
            "He said it was completely innocent.",
            "I asked what shirt.",
            "He went silent for eleven seconds.",
        ],
        "twist": "She had been to our house for dinner six times.",
        "closer": "Now I understand why she always complimented my cooking so hard.",
    },
    {
        "label": "secret apartment",
        "hook": "My husband of eight years had a second apartment. My sister helped him pay for it.",
        "beats": [
            "I found the lease inside a folder labeled car insurance.",
            "Different address.",
            "Same city.",
            "I drove there at 7am on a Tuesday.",
            "His car was in the lot.",
            "I sat outside for two hours.",
            "A woman came out in his college sweatshirt.",
            "I recognized it.",
            "I gave him that sweatshirt for his birthday seven years ago.",
        ],
        "twist": "My sister had been transferring him money every month labeled as a loan.",
        "closer": "He never paid it back. Neither did she, when I asked for an explanation.",
    },
    {
        "label": "family secret",
        "hook": "My dad died and left everything to a woman none of us had ever heard of.",
        "beats": [
            "Her name was in the will twice.",
            "My mom thought it was a mistake.",
            "The lawyer said it was not.",
            "My brother drove to her address.",
            "A teenage boy answered the door.",
            "He had my dad's eyes.",
            "Same jawline.",
            "Same way of standing with one hand in his pocket.",
            "He asked if we were there about the money.",
        ],
        "twist": "Dad had been paying for his school, his clothes, and his birthday every year since birth.",
        "closer": "My mom said she always knew something was missing. Now she knows what it was.",
    },
    {
        "label": "inheritance trap",
        "hook": "My grandmother left me one sentence in her will. My aunts laughed until the lawyer kept reading.",
        "beats": [
            "The sentence said, for the only one who visited.",
            "My aunts looked confused.",
            "The lawyer flipped to the next page.",
            "It listed a storage unit address.",
            "And a safety deposit box number.",
            "And a property I had never heard of.",
            "My aunts had been managing her finances for years.",
            "They thought they knew every account.",
            "Grandma opened a separate one in 1987 that nobody touched.",
        ],
        "twist": "The storage unit had forty years of rental income she never spent.",
        "closer": "She told me once that greedy people always look at the table, not the person sitting at it.",
    },
    {
        "label": "stolen identity",
        "hook": "My brother used my identity to buy a house. I found out when the bank called about missed payments.",
        "beats": [
            "I thought it was a scam call.",
            "Then they sent documents to my address.",
            "My signature was on every page.",
            "I had never signed anything.",
            "My brother had our mother's notary stamp.",
            "She worked at a law firm for twenty years.",
            "I called her first.",
            "She already knew.",
            "She said he needed the help and I would have said no.",
        ],
        "twist": "The house was in my name. The debt was in my name. The tenants were paying him.",
        "closer": "I pressed charges against both of them. My mother has not spoken to me since.",
    },
    {
        "label": "mother in law",
        "hook": "My mother-in-law told me I was too good for her son the day before our wedding.",
        "beats": [
            "I thought it was a compliment.",
            "Then she handed me a folder.",
            "Bank statements going back three years.",
            "His accounts.",
            "Transfers to a woman I did not recognize.",
            "Every month.",
            "Same amount.",
            "She said she had tried to tell him to stop.",
            "He told her it was none of her business.",
        ],
        "twist": "The woman was not a girlfriend. She was his first wife. They were never divorced.",
        "closer": "My mother-in-law drove me to the courthouse herself the next morning.",
    },
    {
        "label": "perfect revenge",
        "hook": "My boss fired me by text while I was in the hospital with my newborn.",
        "beats": [
            "The message said, we are restructuring, today is your last day.",
            "No call.",
            "No warning.",
            "My wife had just given birth four hours earlier.",
            "I had worked there eleven years.",
            "I had trained his current assistant.",
            "I had built the client database from scratch.",
            "I had the admin password to the entire system.",
            "He forgot that when he sent the text.",
        ],
        "twist": "I exported every client contact and sent them a personal farewell email before midnight.",
        "closer": "Six clients followed me. He called to negotiate a week later. I let it go to voicemail.",
    },
    {
        "label": "credit theft",
        "hook": "My manager presented my project to the board and never mentioned my name once.",
        "beats": [
            "I watched through the glass door.",
            "Every slide was mine.",
            "The fonts I chose.",
            "The data I spent three weeks pulling.",
            "The executive summary I wrote at midnight.",
            "He got a standing ovation.",
            "He shook hands with the CEO.",
            "He smiled at me in the hallway and said great support work.",
            "I had saved every version with timestamps.",
        ],
        "twist": "I sent the version history directly to the board chair with one line: I built this.",
        "closer": "He was asked to explain himself at the next meeting. There was no next meeting after that.",
    },
    {
        "label": "wrong house",
        "hook": "A woman moved into my house while I was on vacation and changed all the locks.",
        "beats": [
            "I came home to a different deadbolt.",
            "My key did not work.",
            "I knocked.",
            "A woman I had never seen answered.",
            "She said this was her house.",
            "She had a lease.",
            "Signed by someone using my name.",
            "With a fake ID.",
            "She had already forwarded her mail there.",
        ],
        "twist": "My landlord had rented my apartment to two people at the same time and disappeared with both deposits.",
        "closer": "She and I both filed police reports together. We split the lawyer fees. We won.",
    },
    {
        "label": "fake funeral",
        "hook": "My uncle faked his death to escape debt. He showed up at his own funeral.",
        "beats": [
            "We flew in from three states.",
            "My aunt was devastated.",
            "The casket was closed.",
            "The priest gave a speech.",
            "My cousin read a poem.",
            "My grandmother cried for the first time in twenty years.",
            "Then someone opened the back door.",
            "He walked in wearing sunglasses.",
            "He said he needed everyone to know he was sorry.",
        ],
        "twist": "The creditors had hired a private investigator who was sitting in the third row.",
        "closer": "He was arrested before the reception. My aunt ate the cake alone.",
    },
    {
        "label": "twin secret",
        "hook": "I met a woman at the airport who had my face. We were not related. Then we were.",
        "beats": [
            "She stopped walking when she saw me.",
            "I stopped too.",
            "Same nose.",
            "Same left ear that folds slightly.",
            "Same birthmark above the collarbone.",
            "I thought I was dreaming.",
            "She asked my birthday.",
            "I told her.",
            "She sat down on the floor right there.",
        ],
        "twist": "We were twins separated at birth and adopted by families who never knew the other existed.",
        "closer": "Our biological mother had told both families the other baby did not survive.",
    },
    {
        "label": "hidden camera airbnb",
        "hook": "My Airbnb host watched me sleep for three nights before I found the camera.",
        "beats": [
            "It was inside a charging dock.",
            "Facing the bed.",
            "I only found it because the Wi-Fi was slow and I reset the router.",
            "The router showed a device named bedroom cam.",
            "I checked the host profile.",
            "Forty-seven five-star reviews.",
            "I scrolled to the oldest ones.",
            "One said, felt like I was being watched.",
            "Another said, host seemed to know too much about our schedule.",
        ],
        "twist": "When police searched the property they found footage going back two years.",
        "closer": "Every five-star review was from someone who never knew.",
    },
    {
        "label": "lottery secret",
        "hook": "My dad won the lottery and told no one in the family for six months.",
        "beats": [
            "He kept going to work.",
            "He kept complaining about gas prices.",
            "He kept asking my mom to buy the store-brand cereal.",
            "He drove the same rusted truck.",
            "He watched the same thirteen TV channels.",
            "He did not buy a single new thing.",
            "Then my parents financial advisor called my mother by mistake.",
            "He mentioned the new account.",
            "She asked what account.",
        ],
        "twist": "My dad had been quietly paying off every family member's debt without telling anyone how.",
        "closer": "My mom was furious for about ten minutes. Then she saw the spreadsheet.",
    },
    {
        "label": "catfish parent",
        "hook": "I made a fake profile to check who my daughter was talking to online. The account she liked most was my husband.",
        "beats": [
            "I created a fake profile.",
            "Same age as her, same school.",
            "She accepted the request in four minutes.",
            "I scrolled her following list.",
            "One account had no photo.",
            "Just a username.",
            "She had replied to every single post.",
            "I recognized the writing style immediately.",
            "Same words he used in arguments.",
        ],
        "twist": "He was not talking to her romantically. He was spying on her the exact same way I was.",
        "closer": "We both came clean at dinner. She has not forgiven either of us. That seems fair.",
    },
    {
        "label": "stolen child",
        "hook": "My sister raised a daughter for six years before a DNA test revealed the hospital switched the babies.",
        "beats": [
            "The other family found out first.",
            "They called the hospital.",
            "The hospital called my sister.",
            "She did not believe it.",
            "She took the test three times.",
            "Same result every time.",
            "The other girl looked exactly like my sister.",
            "Her daughter looked exactly like strangers.",
            "Six years of memories that suddenly had a different shape.",
        ],
        "twist": "The hospital had internal records of the mistake and chose not to disclose it.",
        "closer": "Both families are in court now. Both girls know. Neither wanted to be moved.",
    },
    {
        "label": "neighbor revenge",
        "hook": "My neighbor filed code violations against me for three years. Then I found out he was an inspector.",
        "beats": [
            "He reported my fence height.",
            "He reported my driveway crack.",
            "He filed a noise complaint about wind chimes.",
            "Every report cost me money to fix.",
            "I spent two weeks researching his property.",
            "The deck he built in 2019 had no permit.",
            "The garage conversion had no inspection.",
            "The rental unit he had was not zoned.",
            "I filed everything on a Tuesday morning.",
        ],
        "twist": "He had to demolish the deck, evict his tenant, and pay back fines for four years.",
        "closer": "He moved six months later. I replanted my garden the same weekend.",
    },
    {
        "label": "witness protection",
        "hook": "My neighbor of twelve years disappeared overnight and I found out she was never her real name.",
        "beats": [
            "Her house was empty by 6am.",
            "No moving truck.",
            "No boxes.",
            "Just gone.",
            "I called the number I had for her.",
            "Disconnected.",
            "The landlord said a government agency handled the lease termination.",
            "I looked up her name online.",
            "No results. Not one.",
        ],
        "twist": "A detective came by a week later and asked what I knew about her previous life.",
        "closer": "I knew her favorite coffee order and that she cried during dog food commercials. That was all.",
    },
]

FRESH_CONFESSIONS = STRONG_CONFESSIONS.copy()
RECENT_HOOKS: list[str] = []

ESCALATION_LINES = [
    "I did not react at first because I needed to be sure.",
    "So I kept watching and said nothing.",
    "The longer I stayed quiet, the more they revealed.",
    "Everyone in the room knew something I was not supposed to find out.",
    "That was when my stomach dropped completely.",
    "It was not just one lie. It was a system.",
    "Someone had planned this carefully.",
    "I asked one simple question and nobody could answer it.",
    "The silence told me everything the words refused to.",
    "Then I noticed the one detail nobody expected me to catch.",
    "I pulled out my phone and started recording everything.",
    "The confident expression disappeared in real time.",
    "Someone told me I was overreacting.",
    "People only say that when they are afraid you found the truth.",
    "I needed to hear the rest before I moved.",
    "The next thing I saw changed the entire story.",
]

FRESH_TOPIC_NAME = "Fresh drama"

BTN_START = "🏠 Старт"
BTN_GENERATE = "🎬 Генерировать видео"
BTN_RANDOM = "🎲 Random story"
BTN_REGENERATE = "🔄 Сгенерировать заново"
BTN_PUBLISH_YT = "📤 Опубликовать на YouTube"


def keyboard_main() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_START)],
            [KeyboardButton(text=BTN_GENERATE)],
            [KeyboardButton(text=BTN_RANDOM)],
        ],
        resize_keyboard=True,
    )


def keyboard_after_generation() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_START)],
        [KeyboardButton(text=BTN_REGENERATE)],
    ]
    if YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN:
        rows.append([KeyboardButton(text=BTN_PUBLISH_YT)])
    rows.append([KeyboardButton(text=BTN_GENERATE)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def get_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def clean_filename(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")[:50] or "video"


def clean_caption_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("/", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def choose_fresh_confession() -> dict:
    global RECENT_HOOKS
    candidates = [item for item in FRESH_CONFESSIONS if item["hook"] not in RECENT_HOOKS]
    if not candidates:
        RECENT_HOOKS = []
        candidates = FRESH_CONFESSIONS.copy()
    confession = random.choice(candidates)
    RECENT_HOOKS.append(confession["hook"])
    RECENT_HOOKS = RECENT_HOOKS[-8:]
    return confession


def make_tts_script(parts: list[dict]) -> str:
    sentences = [clean_caption_text(part["text"]).rstrip(".!?") for part in parts]
    return ". ".join(sentences) + "."


def count_part_words(parts: list[dict]) -> int:
    return sum(len(clean_caption_text(part["text"]).split()) for part in parts)


def extend_story_parts(parts: list[dict], topic_label: str) -> None:
    used = {part["text"] for part in parts}
    lines = ESCALATION_LINES.copy()
    random.shuffle(lines)
    insert_at = next(
        (i for i, part in enumerate(parts) if part["kind"] == "twist"),
        max(1, len(parts) - 2)
    )
    for line in lines:
        if count_part_words(parts) >= STORY_TARGET_WORDS:
            break
        if line in used:
            continue
        parts.insert(insert_at, {"kind": "story", "label": topic_label, "text": line})
        insert_at += 1
        used.add(line)


def build_script(topic_name: str) -> tuple[str, list[dict]]:
    confession = choose_fresh_confession()
    topic_label = confession["label"]
    parts = [{"kind": "hook", "label": topic_label, "text": confession["hook"]}]
    for beat in confession["beats"]:
        parts.append({"kind": "story", "label": topic_label, "text": beat})
    parts.append({"kind": "twist", "label": "wait for it", "text": confession["twist"]})
    parts.append({"kind": "outro", "label": "comment", "text": confession["closer"]})
    parts.append({"kind": "outro", "label": "comment", "text": "What would you do in this situation?"})
    extend_story_parts(parts, topic_label)
    narration = "\n".join(part["text"] for part in parts)
    return narration, parts


# ── TTS ───────────────────────────────────────────────────────────────────────

async def make_voiceover(text: str, out_path: Path) -> None:
    raw_path = out_path.with_name(f"{out_path.stem}_raw.mp3")
    if TTS_PROVIDER == "gtts":
        await asyncio.to_thread(make_voiceover_gtts, text, raw_path)
    elif TTS_PROVIDER == "edge":
        await make_voiceover_edge(text, raw_path)
    elif TTS_PROVIDER == "elevenlabs":
        await asyncio.to_thread(make_voiceover_elevenlabs, text, raw_path)
    else:
        try:
            if ELEVENLABS_API_KEY:
                await asyncio.to_thread(make_voiceover_elevenlabs, text, raw_path)
            else:
                await make_voiceover_edge(text, raw_path)
        except Exception as e:
            if not ALLOW_GTTS_FALLBACK:
                raise
            logger.warning("Primary TTS failed, falling back to gTTS: %s", e)
            await asyncio.to_thread(make_voiceover_gtts, text, raw_path)
    await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)


async def make_voiceover_edge(text: str, out_path: Path) -> None:
    voice = VOICE.strip().rstrip(".")
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=EDGE_RATE, pitch=EDGE_PITCH)
            await communicate.save(str(out_path))
            return
        except Exception as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("edge-tts attempt %d/3 failed: %s", attempt + 1, e)
            await asyncio.sleep(wait)
    if ALLOW_GTTS_FALLBACK:
        await asyncio.to_thread(make_voiceover_gtts, text, out_path)
    else:
        raise last_error


def make_voiceover_gtts(text: str, out_path: Path) -> None:
    tts = gTTS(text=text, lang="en", tld="com", slow=False)
    tts.save(str(out_path))


def make_voiceover_elevenlabs(text: str, out_path: Path) -> None:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is missing")
    response = get_session().post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2",
              "voice_settings": {"stability": 0.34, "similarity_boost": 0.82, "style": 0.45, "use_speaker_boost": True}},
        timeout=90,
    )
    response.raise_for_status()
    out_path.write_bytes(response.content)


def speed_audio(input_path: Path, out_path: Path, speed: float) -> None:
    if abs(speed - 1.0) < 0.01:
        shutil.copyfile(input_path, out_path)
        return
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.3f}")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-filter:a", ",".join(filters), "-vn", str(out_path)],
        check=True, capture_output=True,
    )


def ensure_min_audio_duration(audio_path: Path, tmp_dir: Path) -> None:
    duration = ffprobe_duration(audio_path)
    if duration >= MIN_AUDIO_SECONDS:
        return
    speed = max(0.35, duration / MIN_AUDIO_SECONDS)
    stretched = tmp_dir / "voice_stretched.mp3"
    speed_audio(audio_path, stretched, speed)
    shutil.copyfile(stretched, audio_path)


# ── СУБТИТРЫ — ЖЁЛТЫЕ ────────────────────────────────────────────────────────

def chunk_subtitle_text(text: str, max_words: int = 3) -> list[str]:
    words = re.findall(r"[A-Za-z0-9']+|[!?.,]", clean_caption_text(text))
    chunks: list[str] = []
    current: list[str] = []
    for token in words:
        if re.fullmatch(r"[!?.,]", token):
            if current:
                current[-1] += token
            continue
        current.append(token)
        if len(current) >= max(2, min(3, max_words)):
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def estimate_subtitle_timings(parts: list[dict], total_seconds: float) -> list[dict]:
    weights = [max(3, len(clean_caption_text(part["text"]).split())) for part in parts]
    usable = max(8, total_seconds - 0.45)
    cursor = 0.12
    events: list[dict] = []
    for part, weight in zip(parts, weights):
        part_duration = usable * weight / sum(weights)
        chunks = chunk_subtitle_text(part["text"], SUBTITLE_WORDS)
        chunk_duration = max(0.42, part_duration / max(1, len(chunks)))
        part_start = cursor
        part_end = min(total_seconds - 0.12, cursor + part_duration)
        events.append({
            "start": part_start,
            "end": min(part_end, part_start + 2.7),
            "text": part["label"].upper(),
            "kind": "label",
        })
        for chunk in chunks:
            start = cursor
            end = min(total_seconds - 0.1, cursor + chunk_duration)
            events.append({"start": start, "end": end, "text": chunk, "kind": part["kind"]})
            cursor = end
    return events


def ass_time(seconds: float) -> str:
    seconds = max(0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    text = clean_caption_text(text)
    text = text.replace("\\", "")
    text = text.replace("{", "(").replace("}", ")")
    return text


def write_ass_subtitles(parts: list[dict], audio_seconds: float, out_path: Path, layout: str = "split") -> None:
    events = estimate_subtitle_timings(parts, audio_seconds)
    YELLOW  = "&H0000FFFF"
    BLACK_O = "&H00000000"
    DARK_BG = "&HAA000000"

    # In split mode subtitles sit in the top half (MarginV pushes up from center)
    # In overlay mode subtitles sit in the center of full screen
    if layout == "split":
        # Top half of 1920 = roughly top 960px. Alignment=8 = top-center.
        # MarginV from top edge
        sub_align = 8
        margin_v = 40
        font_default = 108
        font_hook = 124
        font_twist = 128
    else:
        sub_align = 5   # center
        margin_v = 0
        font_default = 132
        font_hook = 148
        font_twist = 152

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font_default},{YELLOW},&H000000FF,{BLACK_O},{DARK_BG},1,0,0,0,100,100,0,0,1,9,4,{sub_align},64,64,{margin_v},1\n"
        f"Style: Hook,Arial,{font_hook},{YELLOW},&H000000FF,{BLACK_O},{DARK_BG},1,0,0,0,100,100,0,0,1,11,4,{sub_align},58,58,{margin_v},1\n"
        f"Style: Twist,Arial,{font_twist},{YELLOW},&H000000FF,{BLACK_O},{DARK_BG},1,0,0,0,100,100,0,0,1,11,4,{sub_align},58,58,{margin_v},1\n"
        f"Style: Label,Arial,52,{YELLOW},&H000000FF,{BLACK_O},&HCC000000,1,0,0,0,100,100,0,0,3,18,0,8,90,90,142,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lines = [header]
    for item in events:
        text = ass_escape(item["text"])
        if item["kind"] == "label":
            style = "Label"
        elif item["kind"] == "hook":
            style = "Hook"
        elif item["kind"] == "twist":
            style = "Twist"
        else:
            style = "Default"
        lines.append(
            f"Dialogue: 0,{ass_time(item['start'])},{ass_time(item['end'])},"
            f"{style},,0,0,0,,{text}\n"
        )
    out_path.write_text("".join(lines), encoding="utf-8")


def ffprobe_duration(path: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(proc.stdout.strip())


# ── GAMEPLAY DOWNLOAD via yt-dlp ──────────────────────────────────────────────

def get_cached_gameplay_path(url: str) -> Path:
    """Return the cached path for a given URL (may not exist yet)."""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", url)[:60]
    return GAMEPLAY_CACHE_DIR / f"{safe}.mp4"


def download_gameplay(url: str) -> Path:
    """Download gameplay video with yt-dlp, cache locally, return path."""
    cached = get_cached_gameplay_path(url)
    if cached.exists() and cached.stat().st_size > 10 * 1024 * 1024:
        logger.info("Gameplay cache hit: %s", cached.name)
        return cached

    logger.info("Downloading gameplay: %s", url)
    # Download best mp4 up to 720p to save space, prefer shorter videos
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "--merge-output-format", "mp4",
        "-o", str(cached),
        "--no-warnings",
        "--quiet",
        url,
    ]
    subprocess.run(cmd, check=True, timeout=300)
    logger.info("Downloaded gameplay to %s (%.1f MB)", cached.name, cached.stat().st_size / 1024 / 1024)
    return cached


def get_gameplay_clip(url: str, tmp_dir: Path, target_seconds: float) -> Path:
    """
    Extract a random segment from cached gameplay.
    Returns path to extracted clip.
    """
    source = download_gameplay(url)
    src_duration = ffprobe_duration(source)

    max_start = max(0, src_duration - target_seconds - 5)
    seek = random.uniform(30, max_start) if max_start > 30 else random.uniform(0, max(0, max_start))

    out = tmp_dir / "gameplay_raw.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{seek:.2f}",
        "-i", str(source),
        "-t", f"{target_seconds + 2:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-an",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return out


def prepare_gameplay_for_layout(raw_clip: Path, tmp_dir: Path, layout: str, audio_seconds: float) -> Path:
    """
    Resize and crop gameplay for the chosen layout.
    split:   gameplay fills bottom half (1080x960), story/subs in top half (1080x960)
    overlay: gameplay fills full 1080x1920 with dark overlay
    """
    out = tmp_dir / "gameplay_prepared.mp4"

    if layout == "split":
        # Bottom half: 1080 x 960
        vf = (
            f"scale=1080:960:force_original_aspect_ratio=increase,"
            f"crop=1080:960,"
            f"setpts=PTS/{VIDEO_SPEED},fps={FPS},setsar=1"
        )
    else:
        # Full screen with dark semi-transparent overlay for readability
        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"colorlevels=romin=0:gomin=0:bomin=0:romax=0.55:gomax=0.55:bomax=0.55,"
            f"setpts=PTS/{VIDEO_SPEED},fps={FPS},setsar=1"
        )

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(raw_clip),
        "-t", f"{audio_seconds:.2f}",
        "-vf", vf,
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    return out


def make_black_top_half(tmp_dir: Path, audio_seconds: float) -> Path:
    """Create a solid black 1080x960 clip for the top half (text area) in split mode."""
    out = tmp_dir / "black_top.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:size=1080x960:rate={FPS}",
        "-t", f"{audio_seconds:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return out


def stack_split_layout(top: Path, bottom: Path, tmp_dir: Path, audio_seconds: float) -> Path:
    """Stack top (black/text area) and bottom (gameplay) into 1080x1920."""
    out = tmp_dir / "base.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(top),
        "-i", str(bottom),
        "-filter_complex",
        f"[0:v][1:v]vstack=inputs=2[v]",
        "-map", "[v]",
        "-t", f"{audio_seconds:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    return out


def burn_subtitles_and_audio(base_video: Path, voiceover: Path, subtitles: Path, out_path: Path, duration: float) -> None:
    sub_path = subtitles.as_posix().replace(":", r"\:").replace("'", r"\'")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(base_video), "-i", str(voiceover),
         "-t", f"{duration:.2f}",
         "-vf", f"subtitles='{sub_path}',scale=720:1280",
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
         "-maxrate", "2M", "-bufsize", "4M",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(out_path)],
        check=True, capture_output=True,
    )


# ── MAIN VIDEO GENERATION ─────────────────────────────────────────────────────

async def generate_story_video(topic_name: str) -> tuple[Path, str]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="storybot_"))
    narration, parts = build_script(topic_name)
    voiceover = tmp_dir / "voice.mp3"
    subtitles = tmp_dir / "subs.ass"
    out_path = tmp_dir / f"{clean_filename(topic_name)}.mp4"

    # TTS
    await make_voiceover(make_tts_script(parts), voiceover)
    await asyncio.to_thread(ensure_min_audio_duration, voiceover, tmp_dir)
    audio_seconds = min(VIDEO_SECONDS, ffprobe_duration(voiceover))

    # Subtitles
    write_ass_subtitles(parts, audio_seconds, subtitles, layout=LAYOUT_MODE)

    # Pick random gameplay URL
    gameplay_url = random.choice(GAMEPLAY_URLS)
    logger.info("Using gameplay URL: %s", gameplay_url)

    # Download/cache gameplay and extract segment
    raw_clip = await asyncio.to_thread(get_gameplay_clip, gameplay_url, tmp_dir, audio_seconds + 5)

    if LAYOUT_MODE == "split":
        gameplay_prepared = await asyncio.to_thread(
            prepare_gameplay_for_layout, raw_clip, tmp_dir, "split", audio_seconds
        )
        black_top = await asyncio.to_thread(make_black_top_half, tmp_dir, audio_seconds)
        base_video = await asyncio.to_thread(stack_split_layout, black_top, gameplay_prepared, tmp_dir, audio_seconds)
    else:
        base_video = await asyncio.to_thread(
            prepare_gameplay_for_layout, raw_clip, tmp_dir, "overlay", audio_seconds
        )

    await asyncio.to_thread(burn_subtitles_and_audio, base_video, voiceover, subtitles, out_path, audio_seconds)

    # Compress if too large for Telegram
    size_mb = out_path.stat().st_size / (1024 * 1024)
    if size_mb > 45:
        compressed = tmp_dir / "compressed.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(out_path),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "32",
             "-maxrate", "1.5M", "-bufsize", "3M",
             "-c:a", "aac", "-b:a", "96k", str(compressed)],
            check=True, capture_output=True,
        )
        out_path = compressed

    return out_path, narration


# ── YOUTUBE ───────────────────────────────────────────────────────────────────

def make_youtube_metadata(topic_name: str, narration: str) -> tuple[str, str, list[str]]:
    lines = [l for l in narration.splitlines() if l.strip()]
    hook = clean_caption_text(lines[0]) if lines else "You won't believe what happened"
    title = hook[:88].rstrip(" .,!?:;")
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"
    hashtags = "#shorts #storytime #drama #confession #redditstories #fyp #viral #truestory #familydrama #cheating"
    description = f"{hook}\n\nAnonymous story with a twist. Would you believe this happened?\n\n{hashtags}"
    tags = ["shorts", "storytime", "reddit stories", "drama", "confession",
            "family drama", "cheating story", "true story", "fyp", "viral"]
    return title, description, tags


def upload_to_youtube(video_path: Path, topic_name: str, narration: str) -> str:
    if not (YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN):
        raise RuntimeError("YouTube credentials missing")
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        token=None, refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID, client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    title, description, tags = make_youtube_metadata(topic_name, narration)
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(
        part="snippet,status",
        body={"snippet": {"title": title, "description": description, "tags": tags, "categoryId": YOUTUBE_CATEGORY_ID},
              "status": {"privacyStatus": YOUTUBE_PRIVACY_STATUS, "selfDeclaredMadeForKids": False}},
        media_body=media,
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return f"https://www.youtube.com/watch?v={response['id']}"


# ── AUTOPILOT ─────────────────────────────────────────────────────────────────

def seconds_until_next_slot() -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    today_key = now.strftime("%Y-%m-%d")
    fired_today = autopilot_fired.get(today_key, set())
    for hour in sorted(AUTOPILOT_SCHEDULE_UTC):
        if hour not in fired_today:
            target = now.replace(hour=hour, minute=random.randint(0, 14),
                                 second=random.randint(0, 59), microsecond=0)
            if target > now:
                return int((target - now).total_seconds()), hour
    tomorrow = (now + timedelta(days=1)).replace(
        hour=AUTOPILOT_SCHEDULE_UTC[0], minute=random.randint(0, 14), second=0, microsecond=0)
    return int((tomorrow - now).total_seconds()), AUTOPILOT_SCHEDULE_UTC[0]


async def autopilot_loop() -> None:
    if not AUTOPILOT_ENABLED:
        return
    if not (YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN):
        logger.warning("Autopilot: YouTube credentials missing.")
        return
    logger.info("Autopilot started. UTC slots: %s", AUTOPILOT_SCHEDULE_UTC)

    while True:
        wait_seconds, target_hour = seconds_until_next_slot()
        h, m = divmod(wait_seconds, 3600)
        logger.info("Autopilot: next UTC %02d:xx in %dh %dm", target_hour, h, m // 60)

        if AUTOPILOT_USER_ID:
            et_hour = (target_hour - 4) % 24
            await bot.send_message(
                AUTOPILOT_USER_ID,
                f"🕐 Автопилот: публикация через {h}ч {m//60}мин\n"
                f"UTC {target_hour:02d}:xx = ET {et_hour:02d}:xx"
            )

        await asyncio.sleep(wait_seconds)
        today_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        autopilot_fired.setdefault(today_key, set()).add(target_hour)

        try:
            video_path, narration = await generate_story_video(FRESH_TOPIC_NAME)
            title, description, _ = make_youtube_metadata(FRESH_TOPIC_NAME, narration)
            youtube_url = await asyncio.to_thread(upload_to_youtube, video_path, FRESH_TOPIC_NAME, narration)
            logger.info("Autopilot uploaded: %s", youtube_url)
            if AUTOPILOT_USER_ID:
                await bot.send_video(
                    AUTOPILOT_USER_ID,
                    FSInputFile(video_path, filename="auto_short.mp4"),
                    caption=(f"✅ <b>Автопилот опубликовал</b>\n\n🔗 {youtube_url}\n\n"
                             f"<b>Название:</b> {title}\n\n<b>Описание:</b>\n{description}"),
                    parse_mode="HTML", supports_streaming=True, request_timeout=300,
                )
                await bot.send_message(AUTOPILOT_USER_ID,
                                       f"📝 <b>Озвучка:</b>\n\n{narration}", parse_mode="HTML")
        except Exception as e:
            logger.error("Autopilot failed: %s", e, exc_info=True)
            if AUTOPILOT_USER_ID:
                try:
                    await bot.send_message(AUTOPILOT_USER_ID, f"❌ Автопилот ошибка: {e}")
                except Exception:
                    pass

        await asyncio.sleep(60)


# ── BOT HANDLERS ──────────────────────────────────────────────────────────────

async def start_generation(message: Message, topic_name: str) -> None:
    user_id = message.from_user.id
    if len(active_users) >= MAX_PARALLEL_GENERATIONS and user_id not in active_users:
        await message.answer("Сейчас идёт генерация. Попробуй через пару минут.")
        return
    if user_id in active_users:
        await message.answer("Твоё видео уже генерируется.")
        return
    active_users.add(user_id)
    last_generated.setdefault(user_id, {})["last_topic"] = topic_name
    await message.answer("⏳ Генерирую видео...\nЗаймёт 1–3 минуты.", reply_markup=keyboard_main())
    asyncio.create_task(run_generation(message, topic_name))


async def run_generation(message: Message, topic_name: str) -> None:
    user_id = message.from_user.id
    try:
        video_path, narration = await generate_story_video(topic_name)
        title, description, _ = make_youtube_metadata(topic_name, narration)
        last_generated[user_id] = {"path": video_path, "topic": topic_name,
                                   "narration": narration, "last_topic": topic_name}
        await message.answer_video(
            FSInputFile(video_path, filename="story_short.mp4"),
            caption=f"✅ <b>Готово!</b>\n\n<b>Название:</b> {title}\n\n<b>Описание:</b>\n{description}",
            parse_mode="HTML", supports_streaming=True, request_timeout=300,
        )
        await message.answer(
            f"📝 <b>Текст озвучки:</b>\n\n{narration}\n\nВыбери действие 👇",
            parse_mode="HTML", reply_markup=keyboard_after_generation(),
        )
    except Exception as e:
        logger.error("Generation failed: %s", e, exc_info=True)
        await message.answer(f"❌ Ошибка: {e}", reply_markup=keyboard_main())
    finally:
        active_users.discard(user_id)


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 <b>Story Bot</b>\n\n"
        "Нажми <b>Генерировать видео</b> — получи готовый Short.\n\n"
        "🤖 Автопилот: 3 публикации в день\n"
        "9:00 • 15:00 • 20:00 US Eastern Time",
        parse_mode="HTML", reply_markup=keyboard_main(),
    )


@dp.message(F.text == BTN_START)
async def handle_start_button(message: Message) -> None:
    await message.answer("👋 Главное меню.", reply_markup=keyboard_main())


@dp.message(F.text.in_({BTN_GENERATE, BTN_RANDOM}))
async def handle_generate(message: Message) -> None:
    await start_generation(message, FRESH_TOPIC_NAME)


@dp.message(F.text == BTN_REGENERATE)
async def handle_regenerate(message: Message) -> None:
    user_id = message.from_user.id
    data = last_generated.get(user_id)
    topic = data.get("last_topic", FRESH_TOPIC_NAME) if data else FRESH_TOPIC_NAME
    await start_generation(message, topic)


@dp.message(F.text == BTN_PUBLISH_YT)
async def publish_now(message: Message) -> None:
    user_id = message.from_user.id
    data = last_generated.get(user_id)
    if not data or "path" not in data:
        await message.answer("Нет готового видео.")
        return
    if not (YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN):
        await message.answer("YouTube не настроен. Добавь переменные в Railway.")
        return
    await message.answer("⏳ Публикую...", reply_markup=keyboard_main())
    try:
        url = await asyncio.to_thread(upload_to_youtube, data["path"], data["topic"], data["narration"])
        title, desc, _ = make_youtube_metadata(data["topic"], data["narration"])
        await message.answer(
            f"✅ <b>Опубликовано!</b>\n\n🔗 {url}\n\n<b>Название:</b> {title}\n\n<b>Описание:</b>\n{desc}",
            parse_mode="HTML", reply_markup=keyboard_main()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=keyboard_main())


@dp.message()
async def fallback(message: Message) -> None:
    await message.answer("Нажми кнопку 👇", reply_markup=keyboard_main())


async def main() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required")
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp is required — add it to Dockerfile or nixPkgs")
    await bot.delete_webhook(drop_pending_updates=True)
    if AUTOPILOT_ENABLED:
        asyncio.create_task(autopilot_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
