import asyncio
import html
import json
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import edge_tts
import requests
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup
from gtts import gTTS
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

VOICE = os.getenv("VOICE", "en-US-ChristopherNeural")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "auto").lower()
VOICE_SPEED = float(os.getenv("VOICE_SPEED", "1.5"))
VIDEO_SPEED = float(os.getenv("VIDEO_SPEED", "2.0"))
SUBTITLE_WORDS = int(os.getenv("SUBTITLE_WORDS", "3"))
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
W, H = 1080, 1920
FPS = 30
VIDEO_SECONDS = int(os.getenv("VIDEO_SECONDS", "42"))
MAX_PARALLEL_GENERATIONS = int(os.getenv("MAX_PARALLEL_GENERATIONS", "1"))
AUTOPILOT_ENABLED = os.getenv("AUTOPILOT_ENABLED", "false").lower() == "true"
AUTOPILOT_USER_ID = int(os.getenv("AUTOPILOT_USER_ID", "0"))
AUTOPILOT_INTERVAL_HOURS = float(os.getenv("AUTOPILOT_INTERVAL_HOURS", "6"))
AUTOPILOT_TOPICS = [
    topic.strip()
    for topic in os.getenv("AUTOPILOT_TOPICS", "").split(",")
    if topic.strip()
]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not PEXELS_API_KEY:
    raise RuntimeError("PEXELS_API_KEY is missing")

bot = Bot(BOT_TOKEN, request_timeout=300)
dp = Dispatcher()
active_users = set()


TOPICS = {
    "Boss cringe": {
        "button": "😬 Boss cringe",
        "question": "What is the cringiest thing your boss ever did?",
        "queries": [
            "close up soap cutting satisfying",
            "macro carpet cleaning satisfying",
            "close up concrete smoothing trowel",
            "close up pressure washing dirty surface",
            "macro paint mixing satisfying",
        ],
        "stories": [
            "My boss made every email start with, dear workplace family. Even emails about the broken printer.",
            "One manager created a fun jar. If you looked tired, you had to pull a note. Mine said, do ten jumping jacks and compliment the CEO.",
            "A boss announced Hawaiian shirt Friday. Then he wrote up everyone who wore one because it was too distracting.",
            "My old boss made us clap when he entered the room. By Friday, people started taking lunch before he arrived.",
            "One boss installed a dress code for beach day. It was a normal Monday. He was the only person who showed up in swim shorts.",
        ],
    },
    "Weird school": {
        "button": "🏫 Weird school",
        "question": "What was the weirdest rule at your school?",
        "queries": [
            "close up slime satisfying hands",
            "macro sand cutting satisfying",
            "close up soap cutting knife",
            "close up cleaning satisfying scrub",
            "macro cake decorating icing",
        ],
        "stories": [
            "My school banned backpacks because they were a distraction. So everyone carried books in laundry baskets.",
            "A teacher made us ask permission to sharpen pencils. Then got mad because everyone kept interrupting class.",
            "Our principal banned running in the hallway. Then made us do a timed evacuation drill.",
            "They banned hoodies for safety. But the mascot costume had a giant hood and was somehow fine.",
            "One teacher said blue pens were disrespectful. Nobody knew why. She just called them aggressive.",
        ],
    },
    "First date": {
        "button": "💔 First date",
        "question": "What was your worst first date?",
        "queries": [
            "close up food cutting knife satisfying",
            "macro chocolate pouring",
            "close up coffee latte art",
            "close up soap cutting satisfying",
            "macro ice cream making",
        ],
        "stories": [
            "He brought his mom. Not by accident. She sat next to us and rated my answers out of ten.",
            "She asked me my credit score before the appetizers came. Then said mine had backup character energy.",
            "He took me to a restaurant where he worked, then asked his manager for an employee discount mid-date.",
            "She spent twenty minutes explaining her ex's workout routine. I still do not know her favorite color.",
            "He said he forgot his wallet. Then ordered the most expensive steak and called it a trust exercise.",
        ],
    },
    "Got fired": {
        "button": "🧾 Got fired",
        "question": "What is the dumbest reason someone got fired?",
        "queries": [
            "close up factory machine satisfying",
            "macro machine cutting metal",
            "close up woodworking satisfying",
            "macro metal polishing satisfying",
            "close up pressure washing",
        ],
        "stories": [
            "A guy got fired for being late to a meeting that got canceled before he arrived.",
            "Someone got fired for eating a donut from the break room. The donut was from the box he brought.",
            "My coworker got written up for not smiling during a power outage.",
            "A manager fired someone for using too many sticky notes. The next week they launched a productivity board.",
            "One employee got fired for replying okay too quickly. The boss said it felt sarcastic.",
        ],
    },
    "Roommate": {
        "button": "🛋 Roommate",
        "question": "What is the weirdest thing your roommate did?",
        "queries": [
            "close up deep cleaning satisfying",
            "macro car wash foam satisfying",
            "close up carpet cleaning dirty water",
            "close up organizing satisfying hands",
            "macro soap cutting satisfying",
        ],
        "stories": [
            "My roommate labeled every egg in the fridge with a tiny first name. Then got upset when I ate Brandon.",
            "He vacuumed at 3 AM because he said dust is most vulnerable at night.",
            "She kept a spreadsheet of who opened the fridge. We were two people.",
            "My roommate washed paper plates because he said disposable was a mindset.",
            "He used the oven as a sock drawer. I found out while preheating pizza.",
        ],
    },
}

BUTTON_TO_TOPIC = {topic["button"]: name for name, topic in TOPICS.items()}


def main_keyboard() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=topic["button"])] for topic in TOPICS.values()]
    buttons.append([KeyboardButton(text="🎲 Random story")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def clean_filename(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")[:50] or "video"


def build_script(topic_name: str) -> tuple[str, list[dict]]:
    topic = TOPICS[topic_name]
    stories = random.sample(topic["stories"], k=3)
    parts = [{"kind": "hook", "text": topic["question"]}]
    for story in stories:
        parts.append({"kind": "story", "text": story})
    parts.append({"kind": "outro", "text": "Would you quit, or just pretend this was normal?"})
    narration = "\n\n".join(part["text"] for part in parts)
    return narration, parts


async def make_voiceover(text: str, out_path: Path) -> None:
    raw_path = out_path.with_name("voice_raw.mp3")

    if TTS_PROVIDER == "gtts":
        await asyncio.to_thread(make_voiceover_gtts, text, raw_path)
        await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)
        return

    if TTS_PROVIDER == "edge":
        await make_voiceover_edge(text, raw_path)
        await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)
        return

    if TTS_PROVIDER == "elevenlabs":
        await asyncio.to_thread(make_voiceover_elevenlabs, text, raw_path)
        await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)
        return

    try:
        if ELEVENLABS_API_KEY:
            await asyncio.to_thread(make_voiceover_elevenlabs, text, raw_path)
        else:
            await make_voiceover_edge(text, raw_path)
    except Exception as e:
        logger.warning("Primary TTS failed, falling back to gTTS: %s", e)
        await asyncio.to_thread(make_voiceover_gtts, text, raw_path)

    await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)


async def make_voiceover_edge(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate="+8%")
    await communicate.save(str(out_path))


def make_voiceover_gtts(text: str, out_path: Path) -> None:
    tts = gTTS(text=text, lang="en", tld="com", slow=False)
    tts.save(str(out_path))


def make_voiceover_elevenlabs(text: str, out_path: Path) -> None:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY is missing")

    response = get_session().post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.42,
                "similarity_boost": 0.78,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        },
        timeout=90,
    )
    response.raise_for_status()
    out_path.write_bytes(response.content)


def speed_audio(input_path: Path, out_path: Path, speed: float) -> None:
    if abs(speed - 1.0) < 0.01:
        shutil.copyfile(input_path, out_path)
        return

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter:a",
            f"atempo={speed}",
            "-vn",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


async def make_voiceover_sequence(parts: list[dict], out_path: Path, tmp_dir: Path) -> None:
    audio_parts = []
    transition = tmp_dir / "transition.mp3"
    await asyncio.to_thread(make_transition_sound, transition)

    for index, part in enumerate(parts):
        if index > 0:
            audio_parts.append(transition)

        part_audio = tmp_dir / f"voice_part_{index:02d}.mp3"
        await make_voiceover(part["text"], part_audio)
        audio_parts.append(part_audio)

    await asyncio.to_thread(concat_audio_files, audio_parts, out_path, tmp_dir)


def make_transition_sound(out_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=130:duration=0.18",
            "-af",
            "tremolo=f=24:d=0.8,volume=0.9",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def concat_audio_files(audio_parts: list[Path], out_path: Path, tmp_dir: Path) -> None:
    list_file = tmp_dir / "audio_parts.txt"
    list_file.write_text(
        "".join(f"file '{part.as_posix()}'\n" for part in audio_parts),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def estimate_subtitle_timings(parts: list[dict], total_seconds: float) -> list[dict]:
    weights = [max(4, len(part["text"].split())) for part in parts]
    weight_total = sum(weights)
    cursor = 0.2
    result = []
    usable = max(8, total_seconds - 0.7)

    for part, weight in zip(parts, weights):
        duration = usable * weight / weight_total
        chunks = chunk_subtitle_text(part["text"], SUBTITLE_WORDS)
        chunk_duration = max(0.55, duration / max(1, len(chunks)))

        for chunk in chunks:
            start = cursor
            end = min(total_seconds - 0.2, cursor + chunk_duration)
            result.append({"start": start, "end": end, "text": chunk, "kind": part["kind"]})
            cursor = end
    return result


def ass_time(seconds: float) -> str:
    seconds = max(0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def chunk_subtitle_text(text: str, max_words: int = 3) -> list[str]:
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def wrap_subtitle(text: str) -> str:
    return r"\N".join(chunk_subtitle_text(text, max(2, SUBTITLE_WORDS)))


def write_ass_subtitles(parts: list[dict], audio_seconds: float, out_path: Path) -> None:
    events = estimate_subtitle_timings(parts, audio_seconds)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,118,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,0,0,1,8,3,5,70,70,0,1
Style: Hook,Arial,126,&H0000FFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,0,0,1,9,3,5,70,70,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for item in events:
        style = "Hook" if item["kind"] == "hook" else "Default"
        text = html.escape(item["text"]).replace(",", r"\,")
        lines.append(
            f"Dialogue: 0,{ass_time(item['start'])},{ass_time(item['end'])},{style},,0,0,0,,{text}\n"
        )
    out_path.write_text("".join(lines), encoding="utf-8")


def ffprobe_duration(path: Path) -> float:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(proc.stdout.strip())


def search_pexels_videos(query: str, per_page: int = 8) -> list[dict]:
    logger.info("Searching Pexels videos: %s", query)
    r = get_session().get(
        "https://api.pexels.com/videos/search",
        params={"query": query, "per_page": per_page},
        headers={"Authorization": PEXELS_API_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("videos", [])


def best_video_file(video: dict) -> str | None:
    files = video.get("video_files", [])
    files = [f for f in files if f.get("link")]
    if not files:
        return None

    portrait = [f for f in files if (f.get("height") or 0) >= (f.get("width") or 0)]
    candidates = portrait or files
    candidates.sort(key=lambda f: (f.get("height") or 0, f.get("width") or 0), reverse=True)
    return candidates[0]["link"]


def download_pexels_clips(topic_name: str, tmp_dir: Path, wanted: int = 8) -> list[Path]:
    topic = TOPICS[topic_name]
    urls = []
    random_queries = topic["queries"].copy()
    random.shuffle(random_queries)

    for query in random_queries:
        for video in search_pexels_videos(query):
            url = best_video_file(video)
            if url and url not in urls:
                urls.append(url)
            if len(urls) >= wanted:
                break
        if len(urls) >= wanted:
            break

    if not urls:
        raise RuntimeError("No Pexels videos found")

    clips = []
    session = get_session()
    for index, url in enumerate(urls[:wanted], start=1):
        path = tmp_dir / f"source_{index:02d}.mp4"
        logger.info("Downloading clip %s/%s", index, len(urls[:wanted]))
        with session.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        clips.append(path)
    return clips


def make_video_segments(source_clips: list[Path], tmp_dir: Path, target_seconds: float) -> list[Path]:
    segment_seconds = 1.6
    needed = max(6, int(target_seconds // segment_seconds) + 2)
    segments = []

    for index in range(needed):
        src = source_clips[index % len(source_clips)]
        out = tmp_dir / f"segment_{index:02d}.mp4"
        duration = min(segment_seconds, max(0.8, target_seconds - index * segment_seconds))
        input_duration = duration * VIDEO_SPEED
        vf = (
            f"scale={int(W * 1.22)}:{int(H * 1.22)}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setpts=PTS/{VIDEO_SPEED},fps={FPS},setsar=1"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-stream_loop",
                "-1",
                "-i",
                str(src),
                "-t",
                f"{input_duration:.2f}",
                "-vf",
                vf,
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                str(out),
            ],
            check=True,
            capture_output=True,
        )
        segments.append(out)
    return segments


def concat_segments(segments: list[Path], tmp_dir: Path) -> Path:
    list_file = tmp_dir / "segments.txt"
    list_file.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    out = tmp_dir / "base.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)],
        check=True,
        capture_output=True,
    )
    return out


def burn_subtitles_and_audio(base_video: Path, voiceover: Path, subtitles: Path, out_path: Path, duration: float) -> None:
    sub_path = subtitles.as_posix().replace(":", r"\:").replace("'", r"\'")
    vf = f"subtitles='{sub_path}'"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(base_video),
            "-i",
            str(voiceover),
            "-t",
            f"{duration:.2f}",
            "-vf",
            vf,
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


async def generate_story_video(topic_name: str) -> tuple[Path, str]:
    tmp_dir = Path(tempfile.mkdtemp(prefix="storybot_"))
    narration, parts = build_script(topic_name)
    voiceover = tmp_dir / "voice.mp3"
    subtitles = tmp_dir / "subs.ass"
    out_path = tmp_dir / f"{clean_filename(topic_name)}.mp4"

    await make_voiceover(narration, voiceover)
    audio_seconds = min(VIDEO_SECONDS, ffprobe_duration(voiceover))
    write_ass_subtitles(parts, audio_seconds, subtitles)

    source_clips = await asyncio.to_thread(download_pexels_clips, topic_name, tmp_dir)
    segments = await asyncio.to_thread(make_video_segments, source_clips, tmp_dir, audio_seconds)
    base_video = await asyncio.to_thread(concat_segments, segments, tmp_dir)
    await asyncio.to_thread(burn_subtitles_and_audio, base_video, voiceover, subtitles, out_path, audio_seconds)

    return out_path, narration


async def start_generation(message: Message, topic_name: str) -> None:
    user_id = message.from_user.id
    if len(active_users) >= MAX_PARALLEL_GENERATIONS and user_id not in active_users:
        await message.answer("Сейчас уже идет генерация. Попробуй через пару минут.")
        return

    if user_id in active_users:
        await message.answer("Твое видео уже генерируется. Дождись результата.")
        return

    active_users.add(user_id)
    await message.answer(f"Генерирую: {TOPICS[topic_name]['question']}\nЭто займет несколько минут.")
    asyncio.create_task(run_generation(message, topic_name))


async def run_generation(message: Message, topic_name: str) -> None:
    user_id = message.from_user.id
    try:
        video_path, narration = await generate_story_video(topic_name)
        await message.answer_video(
            FSInputFile(video_path, filename="story_short.mp4"),
            caption=f"Ready: {topic_name}",
            supports_streaming=True,
            request_timeout=300,
        )
        await message.answer(f"Voiceover text:\n\n{narration}")
    except Exception as e:
        logger.error("Generation failed: %s", e, exc_info=True)
        await message.answer(f"Ошибка генерации: {e}")
    finally:
        active_users.discard(user_id)


def choose_autopilot_topic() -> str:
    valid_topics = [topic for topic in AUTOPILOT_TOPICS if topic in TOPICS]
    if valid_topics:
        return random.choice(valid_topics)
    return random.choice(list(TOPICS.keys()))


async def autopilot_loop() -> None:
    if not AUTOPILOT_ENABLED:
        return

    if not AUTOPILOT_USER_ID:
        logger.warning("AUTOPILOT_ENABLED=true, but AUTOPILOT_USER_ID is empty")
        return

    logger.info(
        "Autopilot started: user_id=%s interval_hours=%s",
        AUTOPILOT_USER_ID,
        AUTOPILOT_INTERVAL_HOURS,
    )

    while True:
        topic_name = choose_autopilot_topic()
        try:
            await bot.send_message(
                AUTOPILOT_USER_ID,
                f"Autopilot generating: {TOPICS[topic_name]['question']}",
            )
            video_path, narration = await generate_story_video(topic_name)
            await bot.send_video(
                AUTOPILOT_USER_ID,
                FSInputFile(video_path, filename="story_short.mp4"),
                caption=f"Autopilot ready: {topic_name}",
                supports_streaming=True,
                request_timeout=300,
            )
            await bot.send_message(AUTOPILOT_USER_ID, f"Voiceover text:\n\n{narration}")
            logger.info("Autopilot generated video: %s", topic_name)
        except Exception as e:
            logger.error("Autopilot failed: %s", e, exc_info=True)
            try:
                await bot.send_message(AUTOPILOT_USER_ID, f"Autopilot error: {e}")
            except Exception:
                pass

        await asyncio.sleep(max(900, int(AUTOPILOT_INTERVAL_HOURS * 3600)))


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Story Satisfying Bot\nВыбери рубрику, и я соберу ролик: Pexels video + English voiceover + subtitles.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "🎲 Random story")
async def random_story(message: Message) -> None:
    await start_generation(message, random.choice(list(TOPICS.keys())))


@dp.message(F.text.in_(set(BUTTON_TO_TOPIC.keys())))
async def topic_selected(message: Message) -> None:
    await start_generation(message, BUTTON_TO_TOPIC[message.text])


@dp.message()
async def fallback(message: Message) -> None:
    await message.answer("Нажми кнопку с рубрикой.", reply_markup=main_keyboard())


async def main() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe are required")
    await bot.delete_webhook(drop_pending_updates=True)
    if AUTOPILOT_ENABLED:
        asyncio.create_task(autopilot_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
