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

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
USE_WHISPER = os.getenv("USE_WHISPER", "true").lower() == "true"

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

YOUTUBE_UPLOAD_ENABLED = os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").lower() == "true"
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "24")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

LAYOUT_MODE = os.getenv("LAYOUT_MODE", "overlay").lower()

GAMEPLAY_CACHE_DIR = Path(os.getenv("GAMEPLAY_CACHE_DIR", "/data/gameplay"))
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


# ── LIFE DRAMA STORIES ────────────────────────────────────────────────────────
# Real, relatable, everyday situations. Strong hook = specific detail that
# instantly makes you think "wait, what?" — no gore, no crime, no horror.

STRONG_CONFESSIONS = [
    {
        "label": "boss at party",
        "hook": "My boss texted me at 1am after the office party. My husband saw it first.",
        "beats": [
            "We had been at the same table all evening.",
            "He kept refilling my glass.",
            "I thought nothing of it.",
            "The text said he had a great time talking to me.",
            "It said he wanted to continue the conversation privately.",
            "My husband handed me the phone without a word.",
            "I read it three times.",
            "Then I looked at my husband's face.",
            "He asked me one question.",
        ],
        "twist": "He asked if this was the first time. And I realized I had no idea how to answer.",
        "closer": "I reported it to HR Monday morning. My boss resigned by Friday.",
    },
    {
        "label": "mother in law secret",
        "hook": "My mother-in-law called me the wrong name for two years. I just found out it was intentional.",
        "beats": [
            "She called me Sarah.",
            "My name is not Sarah.",
            "My husband corrected her every time.",
            "She always said she forgot.",
            "Then her sister visited.",
            "She introduced me correctly without hesitating.",
            "Her sister looked confused.",
            "She said, you know her name?",
            "The silence lasted about four seconds.",
        ],
        "twist": "Sarah was the name of the woman she wanted her son to marry instead of me.",
        "closer": "My husband finally understood why I had been uncomfortable for two years.",
    },
    {
        "label": "coworker steals idea",
        "hook": "My coworker sent my exact report to management with her name on it. I had the timestamps.",
        "beats": [
            "I worked on it for three weeks.",
            "She asked to review it as a favor.",
            "I trusted her.",
            "The next morning she forwarded it to our director.",
            "Subject line said, my proposal for Q3.",
            "I opened the attachment.",
            "Every word was mine.",
            "Same structure.",
            "Same data I had pulled.",
        ],
        "twist": "I forwarded the original draft with timestamps to the director and CC'd HR.",
        "closer": "She got a written warning. I got the project lead role.",
    },
    {
        "label": "forgot anniversary",
        "hook": "My husband forgot our anniversary. What he did to cover it up was worse than forgetting.",
        "beats": [
            "He came home with flowers.",
            "I was happy at first.",
            "Then I noticed the gas station sticker on the wrapper.",
            "He had bought them ten minutes ago.",
            "I asked what day it was.",
            "He said Tuesday.",
            "I told him our anniversary was Tuesday.",
            "He said he absolutely knew that.",
            "Then his phone buzzed and I saw the reminder he had just set.",
        ],
        "twist": "The reminder said, find out what you did wrong.",
        "closer": "We laughed about it eventually. But not that night.",
    },
    {
        "label": "friend copies life",
        "hook": "My best friend applied for the same job, the same apartment, and the same man I told her about.",
        "beats": [
            "I told her about the job opening on Monday.",
            "She applied Tuesday.",
            "I told her about the apartment on Wednesday.",
            "She toured it Thursday.",
            "I told her about the guy I liked on Friday.",
            "She texted him that weekend.",
            "She used details I had told her about him.",
            "He mentioned she seemed to already know a lot about him.",
            "He sent me the screenshots.",
        ],
        "twist": "She told him I was unstable and had made up a connection between us.",
        "closer": "He believed me. She lost both the friendship and the guy.",
    },
    {
        "label": "bad reference",
        "hook": "I found out my old manager had been giving me a terrible reference for three years.",
        "beats": [
            "I could not understand why I kept not getting jobs.",
            "I had good interviews.",
            "Strong experience.",
            "A recruiter finally told me off the record.",
            "She said my reference had flagged concerns about reliability.",
            "I had never missed a deadline in five years.",
            "I called the reference line myself using a different name.",
            "He picked up.",
            "He said I had left the company under difficult circumstances.",
        ],
        "twist": "I had left because he had taken credit for my work and I had reported it.",
        "closer": "I sent a legal letter. He agreed in writing to give neutral references only.",
    },
    {
        "label": "wedding speech",
        "hook": "My maid of honor used my wedding speech to confess she was in love with my husband.",
        "beats": [
            "She started normally.",
            "She talked about how long we had been friends.",
            "Then the tone changed.",
            "She said she had always admired him.",
            "That she used to imagine what it would be like.",
            "The room went completely quiet.",
            "My husband stopped smiling.",
            "My mother put down her glass.",
            "She finished by wishing us happiness.",
        ],
        "twist": "She later said it was meant as a compliment to my taste.",
        "closer": "She was not invited to the reception dinner.",
    },
    {
        "label": "salary discovery",
        "hook": "I found out the man hired after me with less experience makes thirty percent more.",
        "beats": [
            "He mentioned it casually at lunch.",
            "He thought I already knew.",
            "I did not react.",
            "I went back to my desk.",
            "I pulled up my contract.",
            "I pulled up the job posting.",
            "Same title.",
            "Same responsibilities.",
            "I had three more years of experience.",
        ],
        "twist": "When I asked HR, they said my salary reflected what I had negotiated at the start.",
        "closer": "I negotiated again. I got a twenty-two percent raise in one conversation.",
    },
    {
        "label": "parking spot revenge",
        "hook": "My neighbor stole my parking spot for six months. I solved it in one afternoon.",
        "beats": [
            "I asked him politely twice.",
            "He said he did not realize it was assigned.",
            "He kept doing it.",
            "I documented it for two weeks.",
            "Dates, times, photos.",
            "I sent it to the building manager.",
            "The manager did nothing.",
            "So I sent it to the landlord directly.",
            "With a copy of my lease highlighting the assigned parking clause.",
        ],
        "twist": "It turned out he had been subletting his apartment illegally and the parking complaint triggered an inspection.",
        "closer": "He moved out within a month. I have used my spot every day since.",
    },
    {
        "label": "group chat mistake",
        "hook": "My coworker meant to complain about me in a private chat. She sent it to the whole team.",
        "beats": [
            "I was in a meeting.",
            "My phone buzzed.",
            "Then again.",
            "Then several times.",
            "I checked it after.",
            "There was a message from her describing me as difficult.",
            "And attention-seeking.",
            "And saying the team would be better without me.",
            "Then a message that just said, wrong chat.",
        ],
        "twist": "Seven people had already read it. Two of them replied to the group defending me.",
        "closer": "She apologized in person. I accepted it. We have not had lunch together since.",
    },
    {
        "label": "gym instructor",
        "hook": "My gym instructor told every new client I was proof that effort does not always work.",
        "beats": [
            "A friend joined the gym and mentioned my name.",
            "The instructor used me as an example.",
            "She said some people just do not respond to training.",
            "My friend came home and told me.",
            "I had been coming three times a week for a year.",
            "I had lost fourteen kilos.",
            "I had hit every goal she set.",
            "She had never told me anything except good job.",
            "I asked to see the session records.",
        ],
        "twist": "The records showed she had marked half my sessions as low effort without telling me.",
        "closer": "I asked for a full refund and left a review. The gym called me within two days.",
    },
    {
        "label": "landlord enters flat",
        "hook": "My landlord let himself into my apartment while I was home. He did not know I was there.",
        "beats": [
            "I heard the key in the lock.",
            "I assumed it was my roommate.",
            "I walked out of the bathroom.",
            "It was not my roommate.",
            "He was standing in my kitchen.",
            "Looking through the counter.",
            "He said he was checking something.",
            "He had not called.",
            "He had not knocked.",
        ],
        "twist": "When I checked the camera I had installed at the door, it was the third time that month.",
        "closer": "I sent the footage to a tenant rights lawyer. I got three months free rent.",
    },
    {
        "label": "sister borrows money",
        "hook": "My sister asked to borrow money for rent. I found out she spent it on a vacation.",
        "beats": [
            "She said she was two months behind.",
            "I gave her what she asked without hesitating.",
            "She thanked me and said she would pay it back in three weeks.",
            "Two weeks later she posted photos from another country.",
            "Beach.",
            "Restaurant dinners.",
            "A hotel room with a view.",
            "I called her.",
            "She said she needed a break and the rent situation had worked itself out.",
        ],
        "twist": "It had worked itself out because she had asked three other family members the same week.",
        "closer": "We no longer have a money conversation without a written agreement.",
    },
    {
        "label": "promotion given away",
        "hook": "I trained my replacement for six weeks before anyone told me I did not get the promotion.",
        "beats": [
            "My manager said the new hire needed onboarding.",
            "I spent six weeks teaching her everything.",
            "My systems.",
            "My client relationships.",
            "My reporting process.",
            "On week seven she moved into the senior role.",
            "I was told the decision had been made before the training started.",
            "No one had thought to tell me.",
            "I found out when I saw her new job title in a company email.",
        ],
        "twist": "My manager said I should see it as a leadership opportunity.",
        "closer": "I updated my resume that afternoon. I had a new job in five weeks.",
    },
    {
        "label": "wedding venue",
        "hook": "My mother-in-law booked a different venue for our wedding without telling us.",
        "beats": [
            "We had already put down a deposit.",
            "We had already sent save-the-dates.",
            "She said our venue was too small.",
            "She cancelled our booking.",
            "She booked a venue twice the size.",
            "She did not ask.",
            "She told us as a surprise.",
            "Over dinner.",
            "In front of her side of the family.",
        ],
        "twist": "The new venue was owned by her friend and she had already invited forty extra people from her side.",
        "closer": "We cancelled her venue, rebooked ours, and reduced the guest list by forty.",
    },
    {
        "label": "doctor dismissal",
        "hook": "My doctor told me I was fine for two years. A second opinion changed everything.",
        "beats": [
            "I had been tired for two years.",
            "Constant headaches.",
            "Difficulty concentrating.",
            "He said it was stress.",
            "He said it was lifestyle.",
            "He said some people just feel that way.",
            "I finally saw someone else.",
            "She ordered a blood panel in the first appointment.",
            "The results came back the next day.",
        ],
        "twist": "I had a thyroid condition that had been treatable from the beginning.",
        "closer": "Three months of medication later, I felt like a different person.",
    },
    {
        "label": "fake sick day",
        "hook": "I called in sick and ran into my manager at the mall. What happened next was not what I expected.",
        "beats": [
            "I needed a day off.",
            "I said I had a stomach issue.",
            "I went to return a jacket.",
            "I turned a corner.",
            "She was standing right there.",
            "We made eye contact.",
            "I had nowhere to go.",
            "She looked at me.",
            "Then she looked at the bag I was carrying.",
        ],
        "twist": "She said, good, you deserved a day. You have not taken one in eight months.",
        "closer": "She approved two more personal days the following week without me asking.",
    },
    {
        "label": "neighbor noise complaint",
        "hook": "My neighbor filed a noise complaint against me. I had not been home in four days.",
        "beats": [
            "I had been traveling for work.",
            "I came back to a notice on my door.",
            "Complaint filed Wednesday night.",
            "I had left Sunday morning.",
            "I told the building manager.",
            "He said someone had definitely heard noise from my unit.",
            "I checked my smart lock log.",
            "It showed an entry Wednesday at 11pm.",
            "My spare key was with one person.",
        ],
        "twist": "The person with my spare key had been using my apartment while I was away.",
        "closer": "I changed the locks and never gave out a spare key again.",
    },
    {
        "label": "honest resignation",
        "hook": "I told my boss exactly why I was leaving. His response ended up in a company-wide email.",
        "beats": [
            "He asked me to be honest.",
            "I told him about the missed promotions.",
            "The credit that went to others.",
            "The salary that had not moved in three years.",
            "He took notes.",
            "He said he appreciated the feedback.",
            "He said he wished I had said something sooner.",
            "Two weeks later the CEO sent a company-wide email about culture improvements.",
            "It listed every single issue I had raised.",
        ],
        "twist": "My feedback had been forwarded to leadership without my name on it and used as evidence in a review process.",
        "closer": "Three of my former colleagues got raises that month. I got a job offer with a forty percent increase.",
    },
    {
        "label": "baby shower reveal",
        "hook": "My sister announced my pregnancy at her own baby shower before I had told anyone.",
        "beats": [
            "I had told her in confidence.",
            "I was only eight weeks.",
            "I was not ready.",
            "I was standing right there.",
            "She said she had exciting news.",
            "She pointed at me.",
            "Twenty people turned around.",
            "My mother started crying.",
            "I had not even told my husband's family yet.",
        ],
        "twist": "She said she thought I was being too secretive and that good news should be shared.",
        "closer": "I left the shower early. We did not speak for six weeks.",
    },
]

FRESH_CONFESSIONS = STRONG_CONFESSIONS.copy()
RECENT_HOOKS: list[str] = []

ESCALATION_LINES = [
    "I kept my face completely neutral.",
    "I did not say a word. I just waited.",
    "The more I listened, the clearer it became.",
    "Everyone in the room felt the shift.",
    "I asked one question and let the silence do the rest.",
    "Something about it did not add up.",
    "I had noticed this before but never said anything.",
    "That was the moment I stopped being surprised.",
    "I took a breath and decided to handle it differently.",
    "The one detail nobody expected me to notice — I noticed.",
    "I stayed calm because I already knew what I was going to do.",
    "What happened next took about thirty seconds and changed everything.",
    "I had been patient long enough.",
    "People always underestimate the person who stays quiet.",
    "I had documented everything. That turned out to matter.",
    "The confident expression on their face disappeared quickly.",
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
    """
    Build one continuous flowing paragraph — no line breaks, no short fragments.
    Short beats (under 5 words) are joined with commas so TTS reads them smoothly.
    Longer sentences get a period. Result: natural human narration pace.
    """
    hook  = [p for p in parts if p["kind"] == "hook"]
    story = [p for p in parts if p["kind"] == "story"]
    twist = [p for p in parts if p["kind"] == "twist"]
    outro = [p for p in parts if p["kind"] == "outro"]

    tokens: list[str] = []

    # Hook — always a full sentence
    for p in hook:
        tokens.append(clean_caption_text(p["text"]).rstrip(".!?,") + ".")

    # Story beats — group short fragments together with commas
    if story:
        buffer: list[str] = []
        for p in story:
            beat = clean_caption_text(p["text"]).rstrip(".!?,")
            word_count = len(beat.split())
            if word_count < 6:
                # Short fragment — accumulate with comma
                buffer.append(beat)
            else:
                # Long enough — flush buffer first, then add as own sentence
                if buffer:
                    tokens.append(", ".join(buffer) + ".")
                    buffer = []
                tokens.append(beat + ".")
        if buffer:
            tokens.append(", ".join(buffer) + ".")

    # Twist — full sentence
    for p in twist:
        tokens.append(clean_caption_text(p["text"]).rstrip(".!?,") + ".")

    # Outro — full sentence
    for p in outro:
        tokens.append(clean_caption_text(p["text"]).rstrip(".!?,") + ".")

    # Join everything with a single space — one continuous paragraph
    return " ".join(tokens)


def make_hook_script(parts: list[dict]) -> str:
    hook = next((p for p in parts if p["kind"] == "hook"), parts[0])
    return clean_caption_text(hook["text"]).rstrip(".!?") + "."


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


RECENT_LABELS: list[str] = []


def generate_story_with_groq(avoid_labels: list[str] | None = None) -> dict | None:
    """Generate a relatable life-drama story using Groq API."""
    if not GROQ_API_KEY:
        return None
    avoid_str = ", ".join(avoid_labels[-5:]) if avoid_labels else "none"
    prompt = (
        "You write viral confession stories for YouTube Shorts. "
        "Style: real, relatable, everyday life situations. "
        "Topics: workplace drama, family conflict, friendship betrayal, relationship moments. "
        "NO crime, NO violence, NO horror, NO dark themes. "
        "HOOK rule: must name one SPECIFIC detail (a text message, a receipt, a name, a time, a number). "
        "Hook must make the reader think 'wait, what?' in under 12 words. "
        "BEATS: exactly 9 sentences. Each beat MUST be a complete sentence with subject and verb, 6-12 words each. "
        "NEVER write fragments like 'Job on line' or 'Boss angry' — write full sentences like 'My job was suddenly on the line.' "
        "Beats escalate tension naturally, each one revealing new information. "
        "TWIST: one sentence that reframes everything. Start with 'Turns out' or 'That was when'. "
        "CLOSER: one sentence — outcome, quiet win, or lesson learned. "
        f"Do NOT repeat these topics: {avoid_str}. "
        "Return ONLY JSON: "
        '{\"label\":\"2-3 words\",\"hook\":\"under 12 words\",'
        '\"beats\":[\"9 beats\"],\"twist\":\"one sentence\",\"closer\":\"one sentence\"}'
    )
    try:
        r = get_session().post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 1.0,
                "max_tokens": 800,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        story = __import__("json").loads(data["choices"][0]["message"]["content"])
        required = {"label", "hook", "beats", "twist", "closer"}
        if not required.issubset(story.keys()):
            return None
        if not isinstance(story["beats"], list) or len(story["beats"]) < 5:
            return None
        logger.info("Groq generated story: %s", story["label"])
        return story
    except Exception as e:
        logger.warning("Groq story generation failed: %s", e)
        return None


def build_script(topic_name: str) -> tuple[str, list[dict]]:
    global RECENT_LABELS
    confession = generate_story_with_groq(avoid_labels=RECENT_LABELS) or choose_fresh_confession()
    RECENT_LABELS.append(confession.get("label", ""))
    RECENT_LABELS = RECENT_LABELS[-5:]
    topic_label = confession["label"]
    parts = [{"kind": "hook", "label": topic_label, "text": confession["hook"]}]
    for beat in confession["beats"]:
        parts.append({"kind": "story", "label": topic_label, "text": beat})
    parts.append({"kind": "twist", "label": "wait for it", "text": confession["twist"]})
    parts.append({"kind": "outro", "label": "comment", "text": confession["closer"]})
    parts.append({"kind": "outro", "label": "comment", "text": "Has this happened to you? Comment below and follow for more."})
    extend_story_parts(parts, topic_label)
    narration = "\n".join(part["text"] for part in parts)
    return narration, parts


# ── TYPEWRITER PHONE ANIMATION BACKGROUND ────────────────────────────────────
#
# Renders a realistic phone Notes/iMessage UI with typewriter effect.
# Pure Python + ffmpeg — no external APIs, no downloads.
# Each video gets a random color scheme and slight variations for uniqueness.

# Phone UI themes — dark and light variants
PHONE_THEMES = [
    # (bg_color, phone_bg, header_color, text_color, cursor_color, app_name)
    ("#0d0d0d", "#1c1c1e", "#2c2c2e", "#ffffff", "#ffffff", "Notes"),
    ("#0d0d0d", "#1c1c1e", "#2c2c2e", "#fffde7", "#ffe082", "Notes"),
    ("#0a0a0f", "#1a1a2e", "#16213e", "#e0e0ff", "#7c83fd", "Notes"),
    ("#0d0d0d", "#1e1e1e", "#252525", "#f5f5f5", "#4caf50", "Notes"),
    ("#050505", "#111111", "#1a1a1a", "#ffffff", "#ff6b6b", "Notes"),
]

# Blinking cursor chars
CURSOR_CHAR = "▋"


def _wrap_words(text: str, max_chars: int = 32) -> list[str]:
    """Word-wrap text to fit phone screen width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + (1 if current else 0) <= max_chars:
            current = current + (" " if current else "") + word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_typewriter_background(tmp_dir: Path, parts: list[dict], audio_seconds: float) -> Path:
    """
    Generate a phone Notes typewriter animation synced to the story parts.
    Uses Pillow to render frames, then encodes with ffmpeg.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        subprocess.run(
            ["pip", "install", "Pillow", "--break-system-packages", "-q"],
            check=True, capture_output=True
        )
        from PIL import Image, ImageDraw, ImageFont

    theme = random.choice(PHONE_THEMES)
    bg_hex, phone_bg_hex, header_hex, text_hex, cursor_hex, app_name = theme

    def hex_to_rgb(h: str) -> tuple:
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    bg_color      = hex_to_rgb(bg_hex)
    phone_bg      = hex_to_rgb(phone_bg_hex)
    header_color  = hex_to_rgb(header_hex)
    text_color    = hex_to_rgb(text_hex)
    cursor_color  = hex_to_rgb(cursor_hex)

    # Canvas: 1080x1920 (9:16)
    CW, CH = W, H

    # Phone frame dimensions — centered card
    PW = 880   # phone width
    PH = 1600  # phone height
    PX = (CW - PW) // 2  # left offset
    PY = (CH - PH) // 2  # top offset
    CORNER = 54
    HEADER_H = 120
    PADDING = 48
    LINE_H = 58
    FONT_SIZE = 38
    HEADER_FONT_SIZE = 44
    TIME_FONT_SIZE = 28

    # Try to find a decent font
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font_bold_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]

    font_path = next((f for f in font_candidates if Path(f).exists()), None)
    font_bold_path = next((f for f in font_bold_candidates if Path(f).exists()), None)

    try:
        font      = ImageFont.truetype(font_path, FONT_SIZE) if font_path else ImageFont.load_default()
        font_bold = ImageFont.truetype(font_bold_path or font_path, HEADER_FONT_SIZE) if (font_bold_path or font_path) else ImageFont.load_default()
        font_time = ImageFont.truetype(font_path, TIME_FONT_SIZE) if font_path else ImageFont.load_default()
    except Exception:
        font = font_bold = font_time = ImageFont.load_default()

    # Build the full story text to reveal progressively
    story_lines_all: list[str] = []
    for part in parts:
        if part["kind"] in ("hook", "story", "twist", "outro"):
            text = clean_caption_text(part["text"])
            wrapped = _wrap_words(text, max_chars=30)
            story_lines_all.extend(wrapped)
            story_lines_all.append("")  # blank line between parts

    # Remove trailing blank lines
    while story_lines_all and story_lines_all[-1] == "":
        story_lines_all.pop()

    total_frames = int(audio_seconds * FPS)

    # How many chars to reveal per frame (typewriter speed)
    full_text = "\n".join(story_lines_all)
    total_chars = len(full_text)
    # Reveal all text by 80% of video duration, then hold
    reveal_frames = int(total_frames * 0.80)
    chars_per_frame = total_chars / max(reveal_frames, 1)

    def draw_rounded_rect(draw: ImageDraw.Draw, xy, radius: int, fill):
        x1, y1, x2, y2 = xy
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
        draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
        draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
        draw.ellipse([x2 - 2*radius, y2, x2, y2], fill=fill)

    def render_frame(chars_revealed: int, frame_idx: int) -> Image.Image:
        img = Image.new("RGB", (CW, CH), bg_color)
        draw = ImageDraw.Draw(img)

        # Outer glow / shadow effect
        for offset in range(8, 0, -2):
            shadow_color = tuple(min(255, c + 15) for c in bg_color)
            draw_rounded_rect(
                draw,
                (PX - offset, PY - offset, PX + PW + offset, PY + PH + offset),
                CORNER + offset,
                shadow_color
            )

        # Phone body
        draw_rounded_rect(draw, (PX, PY, PX + PW, PY + PH), CORNER, phone_bg)

        # Header bar
        draw_rounded_rect(draw, (PX, PY, PX + PW, PY + HEADER_H), CORNER, header_color)
        # Straight bottom of header
        draw.rectangle([PX, PY + CORNER, PX + PW, PY + HEADER_H], fill=header_color)

        # App name in header
        draw.text(
            (PX + PW // 2, PY + HEADER_H // 2),
            app_name,
            font=font_bold,
            fill=text_color,
            anchor="mm"
        )

        # Status bar time (top left)
        draw.text(
            (PX + 28, PY + 22),
            "9:41",
            font=font_time,
            fill=text_color,
        )

        # Status icons (top right) — simple dots
        for i, dot_color in enumerate([text_color, text_color, text_color]):
            draw.ellipse(
                [PX + PW - 90 + i * 22, PY + 26, PX + PW - 78 + i * 22, PY + 38],
                fill=dot_color
            )

        # Divider line under header
        draw.line(
            [(PX, PY + HEADER_H), (PX + PW, PY + HEADER_H)],
            fill=tuple(max(0, c - 20) for c in header_color),
            width=2
        )

        # Text area
        text_x = PX + PADDING
        text_y = PY + HEADER_H + PADDING

        # Reconstruct visible text from char count
        visible_text = full_text[:chars_revealed]
        visible_lines = visible_text.split("\n")

        # Max visible lines that fit in phone
        max_lines_visible = (PH - HEADER_H - PADDING * 2) // LINE_H

        # Scroll: show last N lines as text grows
        if len(visible_lines) > max_lines_visible:
            visible_lines = visible_lines[-max_lines_visible:]

        for i, line in enumerate(visible_lines):
            y = text_y + i * LINE_H
            if y + LINE_H > PY + PH - PADDING:
                break
            if line:
                draw.text((text_x, y), line, font=font, fill=text_color)

        # Blinking cursor (blink every 0.5s)
        cursor_visible = (frame_idx // (FPS // 2)) % 2 == 0
        if cursor_visible and chars_revealed <= total_chars:
            # Position cursor after last char on last line
            last_line = visible_lines[-1] if visible_lines else ""
            cursor_x = text_x
            cursor_y = text_y + (len(visible_lines) - 1) * LINE_H
            if last_line:
                try:
                    bbox = draw.textbbox((cursor_x, cursor_y), last_line, font=font)
                    cursor_x = bbox[2] + 4
                except Exception:
                    cursor_x = text_x + len(last_line) * (FONT_SIZE // 2)
            draw.text((cursor_x, cursor_y), CURSOR_CHAR, font=font, fill=cursor_color)

        # Subtle vignette effect (darken edges of canvas)
        vignette = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vignette)
        for r in range(300, 0, -10):
            alpha = int((300 - r) * 0.35)
            vd.ellipse(
                [CW // 2 - r * 2, CH // 2 - r * 3,
                 CW // 2 + r * 2, CH // 2 + r * 3],
                outline=(0, 0, 0, alpha), width=10
            )
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, vignette)
        img = img.convert("RGB")

        return img

    # Write frames to temp directory
    frames_dir = tmp_dir / "frames"
    frames_dir.mkdir()

    logger.info("Rendering %d typewriter frames...", total_frames)
    for frame_idx in range(total_frames):
        chars_revealed = min(total_chars, int(frame_idx * chars_per_frame))
        img = render_frame(chars_revealed, frame_idx)
        img.save(frames_dir / f"frame_{frame_idx:05d}.png", optimize=False)

    # Encode frames to video
    out = tmp_dir / "base.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-t", f"{audio_seconds:.2f}",
        str(out)
    ], check=True, capture_output=True, timeout=300)

    logger.info("Typewriter background rendered: %s", out)
    return out


def make_generative_background(tmp_dir: Path, audio_seconds: float, parts: list[dict] | None = None) -> Path:
    """Main background dispatcher — typewriter first, then fallbacks."""
    out = tmp_dir / "base.mp4"

    # 1. Typewriter animation (primary)
    if parts:
        try:
            return make_typewriter_background(tmp_dir, parts, audio_seconds)
        except Exception as e:
            logger.warning("Typewriter background failed: %s — falling back", e)

    # 2. Uploaded gameplay videos
    uploaded = sorted(GAMEPLAY_CACHE_DIR.glob("*.mp4"))
    if uploaded:
        src_file = random.choice(uploaded)
        logger.info("Using uploaded gameplay: %s", src_file.name)
        src_duration = ffprobe_duration(src_file)
        speed = 2.0
        src_needed = audio_seconds * speed
        max_seek = max(0, src_duration - src_needed - 2)
        seek = random.uniform(0, max_seek) if max_seek > 0 else 0
        vf = (
            f"setpts=PTS/{speed},"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,"
            f"fps={FPS},setsar=1"
        )
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{seek:.2f}",
            "-stream_loop", "-1",
            "-i", str(src_file),
            "-t", f"{src_needed + 5:.2f}",
            "-vf", vf,
            "-t", f"{audio_seconds:.2f}",
            "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            str(out)
        ], check=True, capture_output=True, timeout=300)
        return out

    # 3. Pure generative (last resort)
    BG_PRESETS = [
        ("lavfi", f"nullsrc=size={W}x{H}:rate={FPS},geq=lum='random(1)*28+4':cb=128:cr=128"),
        ("lavfi", f"color=c=black:size={W}x{H}:rate={FPS},noise=alls=40:allf=t"),
    ]
    fmt, src = random.choice(BG_PRESETS)
    logger.info("Using generative background")
    subprocess.run([
        "ffmpeg", "-y", "-f", fmt, "-i", src,
        "-t", f"{audio_seconds:.2f}",
        "-vf", f"scale={W}:{H},setsar=1,fps={FPS}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-an", str(out),
    ], check=True, capture_output=True, timeout=120)
    return out


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


# ── SUBTITLES ─────────────────────────────────────────────────────────────────

def transcribe_with_whisper(audio_path: Path) -> list[dict] | None:
    if not GROQ_API_KEY:
        return None
    try:
        import json as _json
        with open(audio_path, "rb") as f:
            audio_data = f.read()
        import urllib.request
        boundary = "----FormBoundary7MA4YWxkTrZu0gW"
        nl = "\r\n"
        body = (
            ("--" + boundary + nl).encode()
            + ('Content-Disposition: form-data; name="file"; filename="audio.mp3"' + nl).encode()
            + ("Content-Type: audio/mpeg" + nl + nl).encode()
            + audio_data
            + (nl + "--" + boundary + nl).encode()
            + ('Content-Disposition: form-data; name="model"' + nl + nl).encode()
            + ("whisper-large-v3-turbo" + nl).encode()
            + ("--" + boundary + nl).encode()
            + ('Content-Disposition: form-data; name="response_format"' + nl + nl).encode()
            + ("verbose_json" + nl).encode()
            + ("--" + boundary + nl).encode()
            + ('Content-Disposition: form-data; name="timestamp_granularities[]"' + nl + nl).encode()
            + ("word" + nl).encode()
            + ("--" + boundary + "--" + nl).encode()
        )
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = _json.loads(r.read())
        words = result.get("words", [])
        if not words:
            return None
        logger.info("Whisper transcribed %d words", len(words))
        return words
    except Exception as e:
        logger.warning("Whisper failed: %s", e)
        return None


def write_ass_from_whisper(words: list[dict], audio_seconds: float, out_path: Path) -> None:
    YELLOW = "&H0000FFFF"
    BLACK_O = "&H00000000"
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,130,{YELLOW},&H000000FF,{BLACK_O},&H00000000,1,0,0,0,100,100,2,0,1,12,0,5,60,60,0,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = [header]
    chunk = []
    chunk_start = None

    def flush_chunk(end_time):
        if not chunk:
            return
        text = ass_escape(" ".join(w["word"].strip() for w in chunk))
        lines.append(
            f"Dialogue: 0,{ass_time(chunk_start)},{ass_time(min(end_time, audio_seconds - 0.05))},Default,,0,0,0,,{text}\n"
        )

    for word in words:
        w_start = float(word.get("start", 0))
        w_end = float(word.get("end", w_start + 0.3))
        if chunk_start is None:
            chunk_start = w_start
        chunk.append(word)
        if len(chunk) >= SUBTITLE_WORDS:
            flush_chunk(w_end)
            chunk = []
            chunk_start = None

    if chunk:
        last_end = float(words[-1].get("end", audio_seconds))
        flush_chunk(last_end)

    out_path.write_text("".join(lines), encoding="utf-8")


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
    def part_weight(part: dict) -> float:
        text = clean_caption_text(part["text"])
        words = len(text.split())
        pause = 0.35 if part["kind"] in ("hook", "twist", "outro") else 0.15
        return words * 0.22 + pause

    weights = [max(0.5, part_weight(p)) for p in parts]
    total_weight = sum(weights)
    scale = (total_seconds - 0.3) / total_weight if total_weight > 0 else 1.0
    cursor = 0.15
    events: list[dict] = []
    for part, weight in zip(parts, weights):
        part_duration = weight * scale
        chunks = chunk_subtitle_text(part["text"], SUBTITLE_WORDS)
        chunk_words = [max(1, len(c.split())) for c in chunks]
        total_chunk_words = sum(chunk_words)
        part_start = cursor
        part_end = min(total_seconds - 0.1, cursor + part_duration)
        events.append({
            "start": part_start,
            "end": min(part_end, part_start + 2.5),
            "text": part["label"].upper(),
            "kind": "label",
        })
        for chunk, cw in zip(chunks, chunk_words):
            start = cursor
            duration = max(0.35, part_duration * cw / total_chunk_words)
            end = min(total_seconds - 0.1, cursor + duration)
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
    YELLOW = "&H0000FFFF"
    BLACK_O = "&H00000000"
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,130,{YELLOW},&H000000FF,{BLACK_O},&H00000000,1,0,0,0,100,100,2,0,1,12,0,5,60,60,0,1\n"
        f"Style: Hook,Arial,148,{YELLOW},&H000000FF,{BLACK_O},&H00000000,1,0,0,0,100,100,2,0,1,14,0,5,56,56,0,1\n"
        f"Style: Twist,Arial,148,{YELLOW},&H000000FF,{BLACK_O},&H00000000,1,0,0,0,100,100,2,0,1,14,0,5,56,56,0,1\n"
        f"Style: Label,Arial,56,{YELLOW},&H000000FF,{BLACK_O},&HCC000000,1,0,0,0,100,100,0,0,3,14,0,8,80,80,120,1\n\n"
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


def burn_subtitles_and_audio(base_video: Path, voiceover: Path, subtitles: Path, out_path: Path, duration: float) -> None:
    sub_path = subtitles.as_posix().replace(":", r"\:").replace("'", r"\'")
    vf = (
        f"subtitles='{sub_path}',"
        "drawtext=text='Follow for more':"
        "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        "fontsize=52:fontcolor=white:borderw=4:bordercolor=black:"
        "x=(w-text_w)/2:y=h-160:enable='lt(t,3)',"
        "scale=1080:1920"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(base_video), "-i", str(voiceover),
         "-t", f"{duration:.2f}",
         "-vf", vf,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-maxrate", "8M", "-bufsize", "16M",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", str(out_path)],
        check=True, capture_output=True,
    )


def inject_beep_after_hook(voiceover: Path, tmp_dir: Path, hook_duration: float) -> Path:
    out = tmp_dir / "voice_resampled.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(voiceover),
        "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        str(out)
    ], check=True, capture_output=True)
    return out


# ── MAIN VIDEO GENERATION ─────────────────────────────────────────────────────

async def generate_story_video(topic_name: str) -> tuple[Path, str]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="storybot_"))
    narration, parts = build_script(topic_name)
    voiceover = tmp_dir / "voice.mp3"
    subtitles = tmp_dir / "subs.ass"
    out_path = tmp_dir / f"{clean_filename(topic_name)}.mp4"

    hook_audio = tmp_dir / "hook_probe.mp3"
    await make_voiceover(make_hook_script(parts), hook_audio)
    hook_duration = ffprobe_duration(hook_audio)
    logger.info("Hook duration: %.2fs", hook_duration)

    await make_voiceover(make_tts_script(parts), voiceover)
    voiceover = await asyncio.to_thread(inject_beep_after_hook, voiceover, tmp_dir, hook_duration)
    await asyncio.to_thread(ensure_min_audio_duration, voiceover, tmp_dir)
    audio_seconds = min(VIDEO_SECONDS, ffprobe_duration(voiceover))

    if USE_WHISPER and GROQ_API_KEY:
        whisper_words = await asyncio.to_thread(transcribe_with_whisper, voiceover)
        if whisper_words:
            await asyncio.to_thread(write_ass_from_whisper, whisper_words, audio_seconds, subtitles)
        else:
            write_ass_subtitles(parts, audio_seconds, subtitles, layout=LAYOUT_MODE)
    else:
        write_ass_subtitles(parts, audio_seconds, subtitles, layout=LAYOUT_MODE)

    base_video = await asyncio.to_thread(make_generative_background, tmp_dir, audio_seconds, parts)
    await asyncio.to_thread(burn_subtitles_and_audio, base_video, voiceover, subtitles, out_path, audio_seconds)

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
    hashtags = "#shorts #storytime #drama #confession #redditstories #fyp #viral #truestory #workplacedrama #relatable"
    description = f"{hook}\n\nAnonymous confession. Real situations, real outcomes.\n\n{hashtags}"
    tags = ["shorts", "storytime", "reddit stories", "drama", "confession",
            "workplace drama", "relatable", "true story", "fyp", "viral"]
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


@dp.message(F.video | F.document)
async def handle_video_upload(message: Message) -> None:
    user_id = message.from_user.id
    if AUTOPILOT_USER_ID and user_id != AUTOPILOT_USER_ID:
        await message.answer("⛔ Только владелец может загружать видео.")
        return
    file = message.video or message.document
    if not file:
        return
    mime = getattr(file, "mime_type", "") or ""
    if message.document and not mime.startswith("video/"):
        await message.answer("Отправь видео файлом (mp4).")
        return
    existing = list(GAMEPLAY_CACHE_DIR.glob("*.mp4"))
    name = f"gameplay_{len(existing) + 1:02d}.mp4"
    save_path = GAMEPLAY_CACHE_DIR / name
    await message.answer(f"⏳ Сохраняю как {name}...")
    try:
        tg_file = await bot.get_file(file.file_id)
        await bot.download_file(tg_file.file_path, save_path)
        size_mb = save_path.stat().st_size / 1024 / 1024
        total = len(list(GAMEPLAY_CACHE_DIR.glob("*.mp4")))
        await message.answer(
            f"✅ <b>Сохранено!</b> {name} ({size_mb:.1f} MB)\n📁 Всего видео: {total}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(F.text == "📁 Библиотека")
async def handle_library(message: Message) -> None:
    files = list(GAMEPLAY_CACHE_DIR.glob("*.mp4"))
    if not files:
        await message.answer("📁 Библиотека пуста. Отправь видео файлом — сохраню как фон.")
        return
    lines = [f"📁 <b>Видео в библиотеке ({len(files)} шт):</b>\n"]
    for f in sorted(files):
        mb = f.stat().st_size / 1024 / 1024
        lines.append(f"• {f.name} — {mb:.1f} MB")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Нажми кнопку 👇\n\nОтправь mp4 файлом — сохраню как фон для видео.",
        reply_markup=keyboard_main()
    )


async def main() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required")
    await bot.delete_webhook(drop_pending_updates=True)
    if AUTOPILOT_ENABLED:
        asyncio.create_task(autopilot_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
