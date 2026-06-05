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
VOICE_SPEED = float(os.getenv("VOICE_SPEED", "1.32"))
VIDEO_SPEED = float(os.getenv("VIDEO_SPEED", "1.35"))
SUBTITLE_WORDS = int(os.getenv("SUBTITLE_WORDS", "3"))
VIDEO_SECONDS = int(os.getenv("VIDEO_SECONDS", "48"))
MAX_PARALLEL_GENERATIONS = int(os.getenv("MAX_PARALLEL_GENERATIONS", "1"))
AUTOPILOT_ENABLED = os.getenv("AUTOPILOT_ENABLED", "false").lower() == "true"
AUTOPILOT_USER_ID = int(os.getenv("AUTOPILOT_USER_ID", "0"))
AUTOPILOT_INTERVAL_HOURS = float(os.getenv("AUTOPILOT_INTERVAL_HOURS", "6"))
AUTOPILOT_TOPICS = [x.strip() for x in os.getenv("AUTOPILOT_TOPICS", "").split(",") if x.strip()]

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

W, H = 1080, 1920
FPS = 30

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not PEXELS_API_KEY:
    raise RuntimeError("PEXELS_API_KEY is missing")

bot = Bot(BOT_TOKEN, request_timeout=300)
dp = Dispatcher()
active_users = set()


STICKY_QUERIES = [
    "pov cooking close up hands",
    "street food cooking close up",
    "knife cutting vegetables close up",
    "steak cooking close up",
    "macro cake decorating icing",
    "coffee pouring close up",
    "chocolate pouring close up",
    "satisfying cleaning close up",
    "soap cutting close up",
    "car detailing close up",
]


TOPICS = {
    "Cheating texts": {
        "button": "Cheating texts",
        "label": "anonymous confession",
        "question": "I found deleted texts from my wife. Then I checked the dates.",
        "queries": [
            "phone texting close up dark",
            "pov cooking close up hands",
            "knife cutting vegetables close up",
            "coffee pouring close up",
            "street food cooking close up",
        ],
        "confessions": [
            {
                "hook": "I found deleted texts from my wife. One name kept showing up.",
                "beats": [
                    "At first I thought it was spam.",
                    "Then I saw the dates.",
                    "Every message was from nights she said she was with her sister.",
                    "I did not confront her.",
                    "I texted the number from my work phone.",
                    "A man replied with our wedding photo.",
                ],
                "twist": "He was not her boyfriend. He was my brother.",
                "closer": "Now the family group chat is silent.",
            },
            {
                "hook": "My wife asked why I was quiet at dinner. I was reading her second phone.",
                "beats": [
                    "She hid it inside an old boot box.",
                    "The first chat said baby.",
                    "The second chat had our address.",
                    "The third chat was worse.",
                    "It was a plan to move out while I was at work.",
                ],
                "twist": "She forgot the phone was still sharing location with our car.",
                "closer": "I packed my own bags first.",
            },
        ],
    },
    "DNA test": {
        "button": "DNA test",
        "label": "family secret",
        "question": "My sister bought everyone DNA tests. One result ruined dinner.",
        "queries": [
            "family dinner table close up",
            "pov cooking close up",
            "cutting fruit close up",
            "cake decorating close up",
            "hands washing dishes close up",
        ],
        "confessions": [
            {
                "hook": "My sister bought DNA tests as a joke. Nobody laughed after mine came back.",
                "beats": [
                    "Dad said the website was probably wrong.",
                    "Mom got very quiet.",
                    "My sister kept refreshing the page.",
                    "My closest match was not anyone at the table.",
                    "It was our neighbor.",
                ],
                "twist": "Dad already knew. He had known for twenty years.",
                "closer": "The neighbor sent me a friend request that night.",
            },
            {
                "hook": "A DNA test said my twin and I were not related.",
                "beats": [
                    "We thought it was a lab mistake.",
                    "Then my mom started crying.",
                    "She said the hospital called once.",
                    "Dad made her hang up.",
                    "He said it was better if nobody knew.",
                ],
                "twist": "My real twin lives three towns away.",
                "closer": "We met last week. Same laugh. Different life.",
            },
        ],
    },
    "Secret revenge": {
        "button": "Secret revenge",
        "label": "petty revenge",
        "question": "My boss fired me by email. He forgot I still had one password.",
        "queries": [
            "office desk close up typing",
            "keyboard typing close up",
            "coffee spilling close up",
            "satisfying cleaning desk close up",
            "woodworking close up",
        ],
        "confessions": [
            {
                "hook": "My boss fired me by email. He forgot I still had one password.",
                "beats": [
                    "I did not delete anything.",
                    "I did not leak anything.",
                    "I just opened the shared calendar.",
                    "Every meeting he skipped had notes.",
                    "Every note said who actually did the work.",
                    "I invited the CEO.",
                ],
                "twist": "He replied all before he noticed the guest list.",
                "closer": "By lunch, I was invited back.",
            },
            {
                "hook": "My manager stole my idea. So I let him present it exactly as written.",
                "beats": [
                    "The first slide looked normal.",
                    "The second slide had fake numbers.",
                    "The third slide asked one question.",
                    "Do you know what this product does.",
                    "He said yes.",
                    "Then clicked the next slide.",
                ],
                "twist": "It said, this was a loyalty test.",
                "closer": "HR asked me for the real deck.",
            },
        ],
    },
    "Wedding disaster": {
        "button": "Wedding disaster",
        "label": "wedding chaos",
        "question": "The bride stopped walking down the aisle when she saw row three.",
        "queries": [
            "wedding table close up",
            "flower arrangement close up",
            "cake decorating close up",
            "champagne pouring close up",
            "pov cooking close up hands",
        ],
        "confessions": [
            {
                "hook": "The bride stopped walking down the aisle when she saw row three.",
                "beats": [
                    "Nobody understood why.",
                    "Then the groom turned around.",
                    "His ex was sitting with his mother.",
                    "Wearing white.",
                    "Holding a baby.",
                    "The baby had the groom's name as a bracelet.",
                ],
                "twist": "The bride smiled and handed the bouquet to the ex.",
                "closer": "Then she walked out alone.",
            },
            {
                "hook": "My cousin's wedding ended before the vows.",
                "beats": [
                    "The best man gave a speech too early.",
                    "He said he could not keep lying.",
                    "The room went silent.",
                    "The groom grabbed the microphone.",
                    "The bride just nodded.",
                ],
                "twist": "She already knew. The speech was her proof.",
                "closer": "The reception became a divorce party.",
            },
        ],
    },
    "Neighbor camera": {
        "button": "Neighbor camera",
        "label": "creepy neighbor",
        "question": "My neighbor sent me a photo of my kitchen. I live alone.",
        "queries": [
            "apartment kitchen close up",
            "door lock close up",
            "cleaning kitchen close up",
            "pov cooking close up",
            "night window rain close up",
        ],
        "confessions": [
            {
                "hook": "My neighbor sent me a photo of my kitchen. I live alone.",
                "beats": [
                    "He said my window was open.",
                    "It was not.",
                    "The photo was from inside.",
                    "I checked the cabinets.",
                    "Then I saw a small red light under the sink.",
                ],
                "twist": "The camera was connected to my landlord's Wi-Fi.",
                "closer": "I moved out before sunset.",
            },
            {
                "hook": "The woman next door knew what I cooked every night.",
                "beats": [
                    "I thought she smelled it.",
                    "Then she mentioned the brand of pan.",
                    "I never told her.",
                    "I put tape over my window.",
                    "That night she texted, bad angle.",
                ],
                "twist": "The camera was hidden inside the smoke alarm.",
                "closer": "The police found three more.",
            },
        ],
    },
    "Inheritance": {
        "button": "Inheritance",
        "label": "money drama",
        "question": "Grandpa left everyone money except one person. Then the video played.",
        "queries": [
            "old documents close up",
            "signing papers close up",
            "cash money close up",
            "coffee table close up",
            "pov cooking close up hands",
        ],
        "confessions": [
            {
                "hook": "Grandpa left everyone money except my uncle. Then the video played.",
                "beats": [
                    "The lawyer said grandpa recorded it himself.",
                    "My uncle laughed.",
                    "The video showed grandpa at the kitchen table.",
                    "He said, check the garage.",
                    "Inside was a locked freezer.",
                ],
                "twist": "It was full of things my uncle claimed were stolen.",
                "closer": "The will was the least awkward part.",
            },
            {
                "hook": "My aunt cried when she saw the will. Not because she got nothing.",
                "beats": [
                    "She got the house.",
                    "My dad got one envelope.",
                    "Inside was a photo.",
                    "It showed my aunt signing grandpa's name.",
                    "The date was two days after he died.",
                ],
                "twist": "The lawyer already had the original papers.",
                "closer": "My aunt left without the house keys.",
            },
        ],
    },
}

BUTTON_TO_TOPIC = {topic["button"]: name for name, topic in TOPICS.items()}


def main_keyboard() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=topic["button"])] for topic in TOPICS.values()]
    buttons.append([KeyboardButton(text="Random story")])
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


def clean_caption_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("/", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_script(topic_name: str) -> tuple[str, list[dict]]:
    topic = TOPICS[topic_name]
    confession = random.choice(topic["confessions"])

    parts = [
        {"kind": "hook", "label": topic["label"], "text": confession["hook"]},
    ]
    for beat in confession["beats"]:
        parts.append({"kind": "story", "label": topic["label"], "text": beat})
    parts.append({"kind": "twist", "label": "wait for it", "text": confession["twist"]})
    parts.append({"kind": "outro", "label": "comment", "text": confession["closer"]})
    parts.append({"kind": "outro", "label": "comment", "text": "What would you do next?"})

    narration = "\n\n".join(part["text"] for part in parts)
    return narration, parts


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
            logger.warning("Primary TTS failed, falling back to gTTS: %s", e)
            await asyncio.to_thread(make_voiceover_gtts, text, raw_path)

    await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)


async def make_voiceover_edge(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate="+3%", pitch="-3Hz")
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
                "stability": 0.34,
                "similarity_boost": 0.82,
                "style": 0.45,
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

    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    filters.append(f"atempo={remaining:.3f}")

    subprocess.run(
        ["ffmpeg", "-y", "-i", str(input_path), "-filter:a", ",".join(filters), "-vn", str(out_path)],
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
            "sine=frequency=520:duration=0.11",
            "-af",
            "volume=0.38,afade=t=out:st=0.07:d=0.04",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )


def concat_audio_files(audio_parts: list[Path], out_path: Path, tmp_dir: Path) -> None:
    list_file = tmp_dir / "audio_parts.txt"
    list_file.write_text("".join(f"file '{part.as_posix()}'\n" for part in audio_parts), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c:a", "libmp3lame", "-q:a", "4", str(out_path)],
        check=True,
        capture_output=True,
    )


def chunk_subtitle_text(text: str, max_words: int = 3) -> list[str]:
    words = re.findall(r"[A-Za-z0-9']+|[!?.,]", clean_caption_text(text))
    chunks = []
    current = []
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
    events = []

    for part, weight in zip(parts, weights):
        part_duration = usable * weight / sum(weights)
        chunks = chunk_subtitle_text(part["text"], SUBTITLE_WORDS)
        chunk_duration = max(0.42, part_duration / max(1, len(chunks)))
        part_start = cursor
        part_end = min(total_seconds - 0.12, cursor + part_duration)
        events.append(
            {
                "start": part_start,
                "end": min(part_end, part_start + 2.7),
                "text": part["label"].upper(),
                "kind": "label",
            }
        )
        for chunk in chunks:
            start = cursor
            end = min(total_seconds - 0.1, cursor + chunk_duration)
            events.append({"start": start, "end": end, "text": chunk, "kind": part["kind"]})
            cursor = end
    return events


def ass_time(seconds: float) -> str:
    seconds = max(0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def ass_escape(text: str) -> str:
    text = clean_caption_text(text)
    text = text.replace("\\", "")
    text = text.replace("{", "(").replace("}", ")")
    return text


def color_caption(text: str, kind: str) -> str:
    text = ass_escape(text)
    if kind in {"hook", "twist"}:
        return r"{\c&H00FFFF&}" + text + r"{\c&HFFFFFF&}"

    words = text.split()
    if len(words) < 2:
        return text
    hot = random.randrange(len(words))
    words[hot] = r"{\c&H00FFFF&}" + words[hot] + r"{\c&HFFFFFF&}"
    return " ".join(words)


def write_ass_subtitles(parts: list[dict], audio_seconds: float, out_path: Path) -> None:
    events = estimate_subtitle_timings(parts, audio_seconds)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,132,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,1,0,0,0,100,100,0,0,1,9,4,5,64,64,0,1
Style: Hook,Arial,142,&H0000FFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,0,0,1,10,4,5,58,58,0,1
Style: Twist,Arial,146,&H0000FFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,0,0,1,10,4,5,58,58,0,1
Style: Label,Arial,48,&H00FFFFFF,&H000000FF,&H00232323,&HCC232323,1,0,0,0,100,100,0,0,3,18,0,8,90,90,142,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for item in events:
        if item["kind"] == "label":
            style = "Label"
            text = ass_escape(item["text"])
        elif item["kind"] == "hook":
            style = "Hook"
            text = color_caption(item["text"], "hook")
        elif item["kind"] == "twist":
            style = "Twist"
            text = color_caption(item["text"], "twist")
        else:
            style = "Default"
            text = color_caption(item["text"], item["kind"])

        lines.append(f"Dialogue: 0,{ass_time(item['start'])},{ass_time(item['end'])},{style},,0,0,0,,{text}\n")
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


def search_pexels_videos(query: str, per_page: int = 12) -> list[dict]:
    logger.info("Searching Pexels videos: %s", query)
    r = get_session().get(
        "https://api.pexels.com/videos/search",
        params={"query": query, "per_page": per_page, "orientation": "portrait"},
        headers={"Authorization": PEXELS_API_KEY},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("videos", [])


def best_video_file(video: dict) -> str | None:
    files = [f for f in video.get("video_files", []) if f.get("link")]
    if not files:
        return None

    portrait = [f for f in files if (f.get("height") or 0) >= (f.get("width") or 0)]
    strong = [f for f in portrait if (f.get("height") or 0) >= 1280 and (f.get("width") or 0) >= 720]
    candidates = strong or portrait or files
    candidates.sort(
        key=lambda f: (
            f.get("height") or 0,
            f.get("width") or 0,
            f.get("fps") or 0,
            f.get("size") or 0,
        ),
        reverse=True,
    )
    return candidates[0]["link"]


def download_pexels_clips(topic_name: str, tmp_dir: Path, wanted: int = 10) -> list[Path]:
    topic = TOPICS[topic_name]
    urls = []
    queries = topic["queries"] + random.sample(STICKY_QUERIES, k=min(4, len(STICKY_QUERIES)))
    random.shuffle(queries)

    for query in queries:
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
    segment_seconds = 1.15
    needed = max(8, int(target_seconds // segment_seconds) + 2)
    segments = []

    for index in range(needed):
        src = source_clips[index % len(source_clips)]
        out = tmp_dir / f"segment_{index:02d}.mp4"
        duration = min(segment_seconds, max(0.75, target_seconds - index * segment_seconds))
        input_duration = duration * VIDEO_SPEED
        try:
            src_duration = ffprobe_duration(src)
        except Exception:
            src_duration = 0
        seek = 0
        if src_duration > input_duration + 2.5:
            seek = random.uniform(0.4, src_duration - input_duration - 0.4)

        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            "unsharp=5:5:0.55:3:3:0.25,"
            f"setpts=PTS/{VIDEO_SPEED},fps={FPS},setsar=1"
        )
        cmd = ["ffmpeg", "-y"]
        if seek:
            cmd += ["-ss", f"{seek:.2f}"]
        cmd += [
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
            "20",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        segments.append(out)
    return segments


def concat_segments(segments: list[Path], tmp_dir: Path) -> Path:
    list_file = tmp_dir / "segments.txt"
    list_file.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
    out = tmp_dir / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)], check=True, capture_output=True)
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
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
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

    await make_voiceover_sequence(parts, voiceover, tmp_dir)
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

    while True:
        topic_name = choose_autopilot_topic()
        try:
            await bot.send_message(AUTOPILOT_USER_ID, f"Autopilot generating: {TOPICS[topic_name]['question']}")
            video_path, narration = await generate_story_video(topic_name)
            await bot.send_video(
                AUTOPILOT_USER_ID,
                FSInputFile(video_path, filename="story_short.mp4"),
                caption=f"Autopilot ready: {topic_name}",
                supports_streaming=True,
                request_timeout=300,
            )
            await bot.send_message(AUTOPILOT_USER_ID, f"Voiceover text:\n\n{narration}")
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
        "Story Satisfying Bot\nВыбери тему, и я соберу ролик: сильный хук + мужская озвучка + короткие субтитры + залипательный фон.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "Random story")
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
