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

VOICE = os.getenv("VOICE", "en-US-GuyNeural")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "edge").lower()
VOICE_SPEED = float(os.getenv("VOICE_SPEED", "1.0"))
EDGE_RATE = os.getenv("EDGE_RATE", "+2%")
EDGE_PITCH = os.getenv("EDGE_PITCH", "-4Hz")
ALLOW_GTTS_FALLBACK = os.getenv("ALLOW_GTTS_FALLBACK", "false").lower() == "true"
VIDEO_SPEED = float(os.getenv("VIDEO_SPEED", "1.35"))
SUBTITLE_WORDS = int(os.getenv("SUBTITLE_WORDS", "3"))
VIDEO_SECONDS = int(os.getenv("VIDEO_SECONDS", "70"))
MAX_PARALLEL_GENERATIONS = int(os.getenv("MAX_PARALLEL_GENERATIONS", "1"))
AUTOPILOT_ENABLED = os.getenv("AUTOPILOT_ENABLED", "false").lower() == "true"
AUTOPILOT_USER_ID = int(os.getenv("AUTOPILOT_USER_ID", "0"))
AUTOPILOT_INTERVAL_HOURS = float(os.getenv("AUTOPILOT_INTERVAL_HOURS", "6"))
AUTOPILOT_TOPICS = [x.strip() for x in os.getenv("AUTOPILOT_TOPICS", "").split(",") if x.strip()]
AUTOPILOT_TARGET = os.getenv("AUTOPILOT_TARGET", "telegram").lower()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

YOUTUBE_UPLOAD_ENABLED = os.getenv("YOUTUBE_UPLOAD_ENABLED", "false").lower() == "true"
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_PRIVACY_STATUS = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "24")

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

FRESH_TOPIC_NAME = "Fresh drama"

FRESH_CONFESSIONS = [
    {
        "label": "family betrayal",
        "queries": ["angry man phone close up", "pov cooking close up hands", "knife cutting vegetables close up"],
        "hook": "My boss started dating my daughter. She is twenty, and he is my father's age.",
        "beats": [
            "He invited me to lunch like nothing was wrong.",
            "Then he said he wanted my blessing.",
            "My daughter texted me not to overreact.",
            "I asked how long this had been going on.",
            "He smiled and said, before her birthday.",
        ],
        "twist": "Then I found out he approved her promotion himself.",
        "closer": "I quit before he could call it a family issue.",
    },
    {
        "label": "wedding betrayal",
        "queries": ["wedding cake close up", "bride phone close up", "champagne pouring close up"],
        "hook": "My fiance cheated on me during our wedding. I found out before the first dance.",
        "beats": [
            "Her phone kept lighting up on the table.",
            "The message said, I miss the room upstairs.",
            "I thought it was a joke.",
            "Then the best man disappeared.",
            "So did she.",
        ],
        "twist": "The photographer caught both of them in the hallway mirror.",
        "closer": "I played the photo on the projector.",
    },
    {
        "label": "cheating wife",
        "queries": ["phone texting close up dark", "coffee pouring close up", "street food cooking close up"],
        "hook": "My wife sent me a photo by mistake. The mirror behind her showed everything.",
        "beats": [
            "She said she was working late.",
            "The photo was supposed to be innocent.",
            "Just her coffee and laptop.",
            "But the mirror showed a hotel bed.",
            "And a man's watch on the pillow.",
        ],
        "twist": "The watch was mine. I gave it to my brother last Christmas.",
        "closer": "I called him first.",
    },
    {
        "label": "secret child",
        "queries": ["family dinner close up", "old photo close up", "hands washing dishes close up"],
        "hook": "A woman brought a child to my door and said my husband already knew.",
        "beats": [
            "The boy had my husband's eyes.",
            "She had his old hoodie.",
            "I asked when this happened.",
            "She said, before your honeymoon.",
            "My husband went pale.",
        ],
        "twist": "Then the boy called my mother-in-law grandma.",
        "closer": "Everyone knew except me.",
    },
    {
        "label": "boss revenge",
        "queries": ["office desk typing close up", "keyboard close up", "coffee spill close up"],
        "hook": "My boss fired me for being late. He forgot why I was late.",
        "beats": [
            "I was at the hospital with his wife.",
            "She begged me not to tell him.",
            "I came back and found my badge disabled.",
            "He said loyalty matters.",
            "So I forwarded one email.",
        ],
        "twist": "It was the hotel booking he made under my name.",
        "closer": "HR called me before I reached the elevator.",
    },
    {
        "label": "daughter secret",
        "queries": ["birthday cake close up", "phone texting close up", "pov cooking close up"],
        "hook": "My daughter invited her boyfriend to dinner. It was my wife's ex.",
        "beats": [
            "He walked in like he owned the room.",
            "My wife dropped a glass.",
            "My daughter said they met at the gym.",
            "I asked his age.",
            "He said age is just pressure from society.",
        ],
        "twist": "Then my wife whispered, he knows.",
        "closer": "Dinner ended before the food came out.",
    },
    {
        "label": "neighbor secret",
        "queries": ["apartment door lock close up", "kitchen close up night", "cleaning kitchen close up"],
        "hook": "My neighbor knew what I cooked every night. Then she named the pan.",
        "beats": [
            "I laughed at first.",
            "Then she mentioned the broken handle.",
            "I never posted it.",
            "I checked the window.",
            "Nothing was there.",
        ],
        "twist": "The camera was inside my smoke alarm.",
        "closer": "The landlord changed his story three times.",
    },
    {
        "label": "inheritance trap",
        "queries": ["signing papers close up", "old documents close up", "cash money close up"],
        "hook": "Grandpa left me one dollar. Then the lawyer gave me a second envelope.",
        "beats": [
            "My cousins laughed.",
            "My aunt filmed my reaction.",
            "The envelope said, open alone.",
            "Inside was a key.",
            "The key opened his storage unit.",
        ],
        "twist": "Everything valuable was already there.",
        "closer": "The one dollar was bait.",
    },
    {
        "label": "best friend betrayal",
        "queries": ["phone notification close up", "coffee table close up", "street food close up"],
        "hook": "My best friend exposed my cheating girlfriend. Then I checked his phone.",
        "beats": [
            "He acted like he saved me.",
            "He showed screenshots.",
            "He hugged me too long.",
            "Something felt off.",
            "So I looked at the contact name.",
        ],
        "twist": "The other man was him.",
        "closer": "He exposed himself by accident.",
    },
    {
        "label": "mother in law",
        "queries": ["family dinner close up", "wedding ring close up", "cake cutting close up"],
        "hook": "My mother-in-law asked for a private talk. She told me not to marry her son.",
        "beats": [
            "The wedding was in two days.",
            "She said I deserved the truth.",
            "My fiance had another apartment.",
            "Another bank account.",
            "And another name on the lease.",
        ],
        "twist": "The name was my sister's.",
        "closer": "I still wore the dress, just not for him.",
    },
    {
        "label": "fake pregnancy",
        "queries": ["pregnancy test close up", "bathroom sink close up", "phone texting close up"],
        "hook": "My girlfriend said she was pregnant. The doctor congratulated my roommate.",
        "beats": [
            "I thought I heard wrong.",
            "She squeezed my hand too hard.",
            "My roommate stopped smiling.",
            "The doctor asked if we were both fathers.",
            "Nobody answered.",
        ],
        "twist": "She had used his insurance card.",
        "closer": "That tiny mistake saved me years.",
    },
    {
        "label": "hidden camera",
        "queries": ["bedroom lamp close up", "door lock close up", "dark room close up"],
        "hook": "My boyfriend gifted me a lamp. My brother found a camera inside it.",
        "beats": [
            "He said it was expensive.",
            "He asked me to keep it near my bed.",
            "My brother works in security.",
            "He noticed the tiny lens.",
            "I called my boyfriend on speaker.",
        ],
        "twist": "He said, which lamp.",
        "closer": "There were more than one.",
    },
]

STRONG_CONFESSIONS = [
    {
        "label": "family betrayal",
        "queries": STICKY_QUERIES,
        "hook": "My boss started dating my twenty-year-old daughter, then threatened to fire me if I said anything.",
        "beats": [
            "He called it a serious relationship.",
            "I called it a man twice her age using his power.",
            "My daughter begged me not to make a scene.",
            "Then he invited both of us to dinner.",
            "At the table, he asked for my blessing.",
            "When I refused, he said my job review was coming up.",
            "That was when my daughter started crying.",
            "She said he had promised her a promotion for months.",
            "I recorded the whole conversation on my phone.",
        ],
        "twist": "The next morning, HR asked why he approved her raise before they ever started dating.",
        "closer": "He thought I was scared. I was just waiting for him to say it out loud.",
    },
    {
        "label": "wedding betrayal",
        "queries": STICKY_QUERIES,
        "hook": "My bride cheated on me during our wedding, and the photographer accidentally caught everything.",
        "beats": [
            "We had not even cut the cake yet.",
            "Her phone kept lighting up beside my plate.",
            "One message said, come back upstairs.",
            "I thought someone was drunk and joking.",
            "Then my best man disappeared.",
            "Five minutes later, so did she.",
            "I went looking and saw the photographer frozen in the hallway.",
            "He whispered, do not go in there.",
            "His camera screen showed my wife in her dress with my best man behind her.",
        ],
        "twist": "Instead of giving a speech, I asked the DJ to put the photo on the projector.",
        "closer": "Her father was the first person to stand up and leave.",
    },
    {
        "label": "cheating wife",
        "queries": STICKY_QUERIES,
        "hook": "My wife sent me a cute selfie from work, but the mirror behind her exposed the lie.",
        "beats": [
            "She said she was working late.",
            "The photo showed coffee, a laptop, and her fake tired smile.",
            "I almost replied, get some rest.",
            "Then I noticed the mirror behind her.",
            "It showed a hotel bed.",
            "On the bed was a man's jacket.",
            "Beside it was a watch I knew too well.",
            "I bought that watch for my brother last Christmas.",
            "I called him, and he declined before the first ring ended.",
        ],
        "twist": "When I got home, my wife had already packed my brother's clothes by mistake.",
        "closer": "That was the only honest thing she did all night.",
    },
    {
        "label": "secret child",
        "queries": STICKY_QUERIES,
        "hook": "A woman showed up at my door with a little boy and said my husband had been paying her for years.",
        "beats": [
            "The boy looked exactly like him.",
            "Same eyes, same nervous smile, same scar on the chin.",
            "She said she did not want money anymore.",
            "She wanted him to stop hiding.",
            "My husband walked in and dropped his keys.",
            "I asked if this was his son.",
            "He did not answer.",
            "The boy looked at my mother-in-law and smiled.",
            "Then he called her grandma.",
        ],
        "twist": "My mother-in-law had been babysitting him every Friday while I worked late.",
        "closer": "The affair hurt. The family cover-up destroyed me.",
    },
    {
        "label": "hidden camera",
        "queries": STICKY_QUERIES,
        "hook": "My neighbor texted me a photo of my bedroom while I was standing inside it.",
        "beats": [
            "The message said, close your curtains.",
            "I looked at the window.",
            "The curtains were already closed.",
            "The photo was from inside the room.",
            "I thought someone had broken in.",
            "Then I noticed the angle.",
            "It came from the smoke alarm.",
            "I ripped it open and found a tiny camera.",
            "The Wi-Fi name connected to it was my landlord's last name.",
        ],
        "twist": "When police checked the apartment, they found cameras in two other rooms.",
        "closer": "My neighbor was not spying. She was warning me.",
    },
    {
        "label": "inheritance trap",
        "queries": STICKY_QUERIES,
        "hook": "My family laughed when grandpa left me one dollar, until the lawyer asked everyone else to leave.",
        "beats": [
            "My cousins recorded my reaction.",
            "My aunt filmed my face.",
            "My uncle said grandpa finally saw my real value.",
            "I smiled because the lawyer was still holding another envelope.",
            "It said, open only when the room is empty.",
            "Inside was a storage key.",
            "There was also a note in grandpa's handwriting.",
            "It said, they only came for the house.",
            "The storage unit had the real will, cash, and documents.",
        ],
        "twist": "The house they were fighting over had already been sold to pay their debts.",
        "closer": "The one dollar was bait, and every greedy person took it.",
    },
    {
        "label": "best friend betrayal",
        "queries": STICKY_QUERIES,
        "hook": "My best friend exposed my cheating girlfriend, then accidentally proved he was the other man.",
        "beats": [
            "He rushed to my apartment like a hero.",
            "He showed screenshots.",
            "He said I deserved better.",
            "He kept touching my shoulder like he had won something.",
            "Something felt off.",
            "The screenshots had one contact name blurred.",
            "I asked why.",
            "He said privacy.",
            "Then his phone lit up on the table.",
            "My girlfriend's name was on the screen.",
        ],
        "twist": "The message said, did he believe the fake screenshots.",
        "closer": "He did not expose the affair. He tried to control the ending.",
    },
    {
        "label": "mother in law",
        "queries": STICKY_QUERIES,
        "hook": "Two days before my wedding, my future mother-in-law begged me not to marry her son.",
        "beats": [
            "She said I deserved the truth.",
            "My fiance had another apartment.",
            "Another bank account.",
            "And another name on the lease.",
            "I thought it was another woman.",
            "She said it was worse.",
            "She handed me a folder.",
            "Inside were photos, receipts, and a lease agreement.",
            "The apartment was paid from our wedding savings.",
        ],
        "twist": "The second name on the lease was my sister's.",
        "closer": "I still wore the dress. I just did not walk toward him.",
    },
    {
        "label": "fake pregnancy",
        "queries": STICKY_QUERIES,
        "hook": "My girlfriend said she was pregnant, but the doctor congratulated my roommate instead of me.",
        "beats": [
            "I thought I heard wrong.",
            "She squeezed my hand too hard.",
            "My roommate stopped smiling.",
            "The doctor looked at the insurance form.",
            "Then he looked at my roommate.",
            "He said, congratulations, dad.",
            "The room went silent.",
            "My girlfriend said it was a paperwork mistake.",
            "My roommate said nothing.",
            "That was how I knew.",
        ],
        "twist": "She had used his insurance card for three appointments and forgot to change the name.",
        "closer": "The baby was not mine. The betrayal was.",
    },
    {
        "label": "hidden camera",
        "queries": STICKY_QUERIES,
        "hook": "My boyfriend bought me a bedside lamp, and my brother found a camera hidden inside it.",
        "beats": [
            "He insisted I keep it facing the bed.",
            "He said the light made me look beautiful.",
            "My brother works in security.",
            "He noticed a tiny reflection in the shade.",
            "We opened the lamp and found a camera.",
            "I called my boyfriend on speaker.",
            "I asked why there was a camera in my room.",
            "He did not ask what camera.",
            "He asked, which lamp.",
        ],
        "twist": "There were cameras in the clock, the charger, and the smoke alarm too.",
        "closer": "I thought he was romantic. He was building a prison.",
    },
    {
        "label": "work affair",
        "queries": STICKY_QUERIES,
        "hook": "My wife told me her boss was harmless, then I found our house key on his keychain.",
        "beats": [
            "He came over for a work dinner.",
            "He acted too comfortable in my kitchen.",
            "He knew where we kept the wine glasses.",
            "He knew our dog hated the back door.",
            "I tried to stay calm.",
            "Then he dropped his keys on the counter.",
            "Our spare house key was hanging next to his car key.",
            "My wife said it was for emergencies.",
            "I asked what emergency happened at midnight last Tuesday.",
        ],
        "twist": "That was when he said, she told me you were separated.",
        "closer": "I was the only person in my marriage who did not know it was over.",
    },
    {
        "label": "wedding speech",
        "queries": STICKY_QUERIES,
        "hook": "The best man's wedding speech started with, I am sorry, but the groom paid me to lie.",
        "beats": [
            "Everyone thought it was a joke.",
            "The groom shouted his name.",
            "The bride stopped smiling.",
            "The best man pulled out his phone.",
            "He said the groom wanted one last weekend before marriage.",
            "Then he showed the hotel messages.",
            "The bride's father stood up.",
            "The groom said it was taken out of context.",
            "Then the hotel receipt appeared on the screen.",
        ],
        "twist": "The receipt was from the night before the wedding.",
        "closer": "The bride never said a word. She just handed him the ring.",
    },
    {
        "label": "family money",
        "queries": STICKY_QUERIES,
        "hook": "My sister begged me to pay for her surgery, then posted vacation photos from the hospital bed.",
        "beats": [
            "She said insurance denied everything.",
            "My parents cried on the phone.",
            "I emptied my savings.",
            "She thanked me like I saved her life.",
            "Three days later, she posted from a beach resort.",
            "The caption said, healing era.",
            "I thought it was an old photo.",
            "Then I saw the hospital bracelet.",
            "It matched the fundraiser photos exactly.",
        ],
        "twist": "There was no surgery. The doctor she named had retired five years earlier.",
        "closer": "My parents still asked me to forgive her because family is family.",
    },
]

FRESH_CONFESSIONS = STRONG_CONFESSIONS

RECENT_HOOKS: list[str] = []

TOPICS[FRESH_TOPIC_NAME] = {
    "button": "Fresh drama",
    "label": "fresh confession",
    "question": "Generate a fresh confession with a strong hook.",
    "queries": STICKY_QUERIES,
    "confessions": [],
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
    text = " ".join(clean_caption_text(part["text"]) for part in parts)
    text = re.sub(r"\.\s+", ", ", text)
    text = re.sub(r"\?\s+", "? ", text)
    text = re.sub(r"!\s+", "! ", text)
    return text


def build_script(topic_name: str) -> tuple[str, list[dict]]:
    if topic_name == FRESH_TOPIC_NAME:
        topic = TOPICS[FRESH_TOPIC_NAME]
        confession = choose_fresh_confession()
        topic_label = confession["label"]
        topic["queries"] = STICKY_QUERIES.copy()
    else:
        topic = TOPICS[topic_name]
        confession = random.choice(topic["confessions"])
        topic_label = topic["label"]

    parts = [
        {"kind": "hook", "label": topic_label, "text": confession["hook"]},
    ]
    for beat in confession["beats"]:
        parts.append({"kind": "story", "label": topic_label, "text": beat})
    parts.append({"kind": "twist", "label": "wait for it", "text": confession["twist"]})
    parts.append({"kind": "outro", "label": "comment", "text": confession["closer"]})
    parts.append({"kind": "outro", "label": "comment", "text": "What would you do next?"})

    narration = "\n".join(part["text"] for part in parts)
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
            if not ALLOW_GTTS_FALLBACK:
                raise
            logger.warning("Primary TTS failed, falling back to gTTS: %s", e)
            await asyncio.to_thread(make_voiceover_gtts, text, raw_path)

    await asyncio.to_thread(speed_audio, raw_path, out_path, VOICE_SPEED)


async def make_voiceover_edge(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate=EDGE_RATE, pitch=EDGE_PITCH)
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

    await make_voiceover(make_tts_script(parts), voiceover)
    audio_seconds = min(VIDEO_SECONDS, ffprobe_duration(voiceover))
    write_ass_subtitles(parts, audio_seconds, subtitles)

    source_clips = await asyncio.to_thread(download_pexels_clips, topic_name, tmp_dir)
    segments = await asyncio.to_thread(make_video_segments, source_clips, tmp_dir, audio_seconds)
    base_video = await asyncio.to_thread(concat_segments, segments, tmp_dir)
    await asyncio.to_thread(burn_subtitles_and_audio, base_video, voiceover, subtitles, out_path, audio_seconds)

    return out_path, narration


def make_youtube_metadata(topic_name: str, narration: str) -> tuple[str, str, list[str]]:
    first_line = clean_caption_text(narration.splitlines()[0] if narration.splitlines() else TOPICS[topic_name]["question"])
    title = first_line[:88].rstrip(" .,!?:;")
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"

    description = (
        f"{first_line}\n\n"
        "Anonymous story with a twist.\n\n"
        "#shorts #storytime #redditstories #drama #confession"
    )
    tags = [
        "shorts",
        "storytime",
        "reddit stories",
        "drama",
        "confession",
        "family drama",
        "cheating story",
        "true story",
    ]
    return title, description, tags


def upload_to_youtube(video_path: Path, topic_name: str, narration: str) -> str:
    if not (YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN):
        raise RuntimeError(
            "YouTube upload needs YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN"
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=scopes,
    )
    credentials.refresh(Request())

    youtube = build("youtube", "v3", credentials=credentials)
    title, description, tags = make_youtube_metadata(topic_name, narration)
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": YOUTUBE_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": YOUTUBE_PRIVACY_STATUS,
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    return f"https://www.youtube.com/watch?v={video_id}"


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
    return FRESH_TOPIC_NAME


async def autopilot_loop() -> None:
    if not AUTOPILOT_ENABLED:
        return
    youtube_mode = YOUTUBE_UPLOAD_ENABLED or AUTOPILOT_TARGET == "youtube"
    if not youtube_mode and not AUTOPILOT_USER_ID:
        logger.warning("Autopilot has no target. Set AUTOPILOT_TARGET=youtube or AUTOPILOT_USER_ID.")
        return

    while True:
        topic_name = choose_autopilot_topic()
        try:
            if AUTOPILOT_USER_ID:
                await bot.send_message(AUTOPILOT_USER_ID, f"Autopilot generating: {TOPICS[topic_name]['question']}")

            video_path, narration = await generate_story_video(topic_name)

            youtube_url = ""
            if youtube_mode:
                youtube_url = await asyncio.to_thread(upload_to_youtube, video_path, topic_name, narration)
                logger.info("Uploaded to YouTube: %s", youtube_url)

            if AUTOPILOT_USER_ID:
                caption = f"Autopilot ready: {topic_name}"
                if youtube_url:
                    caption += f"\nYouTube: {youtube_url}"
                await bot.send_video(
                    AUTOPILOT_USER_ID,
                    FSInputFile(video_path, filename="story_short.mp4"),
                    caption=caption,
                    supports_streaming=True,
                    request_timeout=300,
                )
                await bot.send_message(AUTOPILOT_USER_ID, f"Voiceover text:\n\n{narration}")
        except Exception as e:
            logger.error("Autopilot failed: %s", e, exc_info=True)
            if AUTOPILOT_USER_ID:
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
    await start_generation(message, FRESH_TOPIC_NAME)


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
