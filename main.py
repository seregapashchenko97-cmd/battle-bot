import asyncio
import random
import base64
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
import time
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
POLLINATIONS_MODEL = os.getenv("POLLINATIONS_MODEL", "flux")
POLLINATIONS_TIMEOUT = int(os.getenv("POLLINATIONS_TIMEOUT", "35"))
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UCPq1H-SmJ_N7UxImtFHrdeQ")
AUTOPILOT_USER_ID = int(os.getenv("AUTOPILOT_USER_ID", "0"))
AUTOPILOT_ENABLED = os.getenv("AUTOPILOT_ENABLED", "false").lower() == "true"

bot = Bot(BOT_TOKEN, request_timeout=120)
dp = Dispatcher()

FONT_PATH = "Anton-Regular.ttf"
CLIP_DURATION = 5
FPS = 20
W, H = 720, 1280
QUEUE_SLOTS = [9, 15, 21]

# ============================================================
# РўР•РњРђРўРР§Р•РЎРљРР• РљРђРўР•Р“РћР РР
# ============================================================
CATEGORIES = {
    "рџ’° Money & Success": {
        "battles": [
            ("Money", "Love"),
            ("Fame", "Happiness"),
            ("Hustle", "Balance"),
            ("Rich & Alone", "Poor & Together"),
            ("Billionaire", "Rock Star"),
            ("Work Hard", "Work Smart"),
            ("Success", "Peace of Mind"),
            ("Power", "Freedom"),
            ("Ambition", "Loyalty"),
            ("Career", "Family"),
        ],
        "pexels": {
            "Money": "luxury money cash gold dark background cinematic",
            "Love": "romantic couple love dark moody cinematic",
            "Fame": "celebrity red carpet spotlight crowd dark",
            "Happiness": "happy laughing friends joy",
            "Hustle": "businessman working late night office dark",
            "Balance": "yoga meditation peaceful nature",
            "Rich & Alone": "luxury penthouse alone",
            "Poor & Together": "friends together happy community",
            "Billionaire": "luxury yacht private jet mansion dark",
            "Rock Star": "rock concert stage performer",
            "Work Hard": "working late night laptop grind",
            "Work Smart": "smart strategy chess planning",
            "Success": "winner trophy podium celebrate",
            "Peace of Mind": "peaceful calm nature zen",
            "Power": "strong leader confident",
            "Freedom": "open road motorcycle freedom sky",
            "Ambition": "skyscraper climbing top goal",
            "Loyalty": "friendship trust handshake bond",
            "Career": "corporate office career suit",
            "Family": "family together home warm",
        }
    },
    "рџљ— Cars & Luxury": {
        "battles": [
            ("Ferrari", "Lamborghini"),
            ("Rolls Royce", "Bugatti"),
            ("BMW", "Mercedes"),
            ("Porsche", "Aston Martin"),
            ("Tesla", "Ferrari"),
            ("Sports Car", "SUV"),
            ("Lamborghini Urus", "Porsche Cayenne"),
            ("McLaren", "Ferrari"),
            ("Bentley", "Rolls Royce"),
            ("Corvette", "Mustang"),
        ],
        "pexels": {
            "Ferrari": "red ferrari sports car dark background studio",
            "Lamborghini": "lamborghini aventador dark background dramatic",
            "Rolls Royce": "rolls royce luxury black car",
            "Bugatti": "bugatti chiron supercar fast",
            "BMW": "bmw m3 sports car",
            "Mercedes": "mercedes amg luxury car",
            "Porsche": "porsche 911 sports car",
            "Aston Martin": "aston martin luxury british car",
            "Tesla": "tesla electric car modern",
            "Sports Car": "sports car racing track speed",
            "SUV": "suv luxury offroad",
            "Lamborghini Urus": "lamborghini urus suv",
            "Porsche Cayenne": "porsche cayenne suv",
            "McLaren": "mclaren supercar british",
            "Bentley": "bentley luxury continental",
            "Corvette": "corvette american muscle car",
            "Mustang": "ford mustang muscle car",
        }
    },
    "рџЌ” Food & Drink": {
        "battles": [
            ("Burger", "Pizza"),
            ("Sushi", "Steak"),
            ("Coffee", "Energy Drink"),
            ("Tacos", "Burrito"),
            ("Ramen", "Pasta"),
            ("Fried Chicken", "Grilled Salmon"),
            ("Cheesecake", "Chocolate Cake"),
            ("Beer", "Whiskey"),
            ("Chips", "Popcorn"),
            ("Pancakes", "Waffles"),
        ],
        "pexels": {
            "Burger": "gourmet burger dark background dramatic close up",
            "Pizza": "pizza slice melting cheese dark moody close up",
            "Sushi": "sushi rolls japanese food",
            "Steak": "wagyu steak grilled dark background cinematic",
            "Coffee": "espresso coffee dark moody cafe aesthetic",
            "Energy Drink": "energy drink can neon dark",
            "Tacos": "mexican tacos street food",
            "Burrito": "burrito wrap mexican food",
            "Ramen": "ramen noodles japanese broth",
            "Pasta": "pasta italian food sauce",
            "Fried Chicken": "fried chicken crispy golden",
            "Grilled Salmon": "grilled salmon healthy food",
            "Cheesecake": "cheesecake dessert slice",
            "Chocolate Cake": "chocolate cake dessert dark",
            "Beer": "beer glass pub cold",
            "Whiskey": "whiskey glass dark bar",
            "Chips": "chips snack bowl",
            "Popcorn": "popcorn cinema movie",
            "Pancakes": "pancakes stack maple syrup",
            "Waffles": "waffles breakfast sweet",
        }
    },
    "рџЋµ Music & Entertainment": {
        "battles": [
            ("Hip Hop", "Rock"),
            ("Drake", "Kendrick"),
            ("Netflix", "Cinema"),
            ("Vinyl", "Streaming"),
            ("Concert", "Festival"),
            ("Pop", "Jazz"),
            ("Guitar", "Piano"),
            ("Studio", "Live Performance"),
            ("Headphones", "Speakers"),
            ("Classical", "Electronic"),
        ],
        "pexels": {
            "Hip Hop": "hip hop rapper microphone urban dark stage",
            "Rock": "rock concert electric guitar dark stage dramatic",
            "Drake": "rapper music stage microphone",
            "Kendrick": "rapper performer stage lights",
            "Netflix": "watching tv series couch night",
            "Cinema": "movie theater cinema screen dark",
            "Vinyl": "vinyl record player retro music",
            "Streaming": "spotify music phone earphones",
            "Concert": "music concert crowd lights stage",
            "Festival": "music festival outdoor crowd",
            "Pop": "pop music singer stage performance",
            "Jazz": "jazz music saxophone dark bar",
            "Guitar": "electric guitar music dark",
            "Piano": "piano keys music performance",
            "Studio": "recording studio music producer",
            "Live Performance": "live music band stage",
            "Headphones": "headphones music listening",
            "Speakers": "speakers sound system music",
            "Classical": "orchestra classical music concert",
            "Electronic": "dj electronic music club",
        }
    },
    "рџ’Є Lifestyle & Fitness": {
        "battles": [
            ("Gym", "Home Workout"),
            ("Running", "Swimming"),
            ("Vegan", "Carnivore"),
            ("Early Bird", "Night Owl"),
            ("City Life", "Country Life"),
            ("Solo Travel", "Group Travel"),
            ("Beach", "Mountains"),
            ("Meditation", "Gym"),
            ("Minimalism", "Luxury"),
            ("Cold Shower", "Hot Bath"),
        ],
        "pexels": {
            "Gym": "bodybuilder gym dark dramatic workout pumping iron",
            "Home Workout": "home workout exercise training",
            "Running": "athlete running city marathon dramatic dark",
            "Swimming": "swimming pool athlete water",
            "Vegan": "vegan food healthy green vegetables",
            "Carnivore": "steak meat protein diet",
            "Early Bird": "sunrise morning coffee fresh",
            "Night Owl": "night city dark working late",
            "City Life": "city skyline urban life busy",
            "Country Life": "countryside peaceful nature farm",
            "Solo Travel": "solo traveler backpack adventure",
            "Group Travel": "group friends travel adventure",
            "Beach": "tropical beach ocean sunset",
            "Mountains": "mountain peak snow adventure",
            "Meditation": "meditation yoga peace mindfulness",
            "Minimalism": "minimalist clean simple interior",
            "Luxury": "luxury lifestyle expensive fashion",
            "Cold Shower": "cold shower water refreshing",
            "Hot Bath": "hot bath relaxing spa",
        }
    },
    "рџ“± Tech & Brands": {
        "battles": [
            ("iPhone", "Android"),
            ("Nike", "Adidas"),
            ("PlayStation", "Xbox"),
            ("Mac", "PC"),
            ("Instagram", "TikTok"),
            ("Apple Watch", "Rolex"),
            ("Google", "Apple"),
            ("YouTube", "Netflix"),
            ("Uber", "Taxi"),
            ("Amazon", "Local Shop"),
        ],
        "pexels": {
            "iPhone": "iphone pro dark background studio minimal",
            "Android": "samsung android smartphone",
            "Nike": "nike air jordan sneakers dark background studio",
            "Adidas": "adidas sneakers shoes sport",
            "PlayStation": "playstation gaming console controller",
            "Xbox": "xbox gaming controller",
            "Mac": "macbook apple laptop",
            "PC": "gaming pc desktop setup",
            "Instagram": "instagram phone social media",
            "TikTok": "tiktok phone social media video",
            "Apple Watch": "apple watch smartwatch tech",
            "Rolex": "rolex gold watch dark background luxury closeup",
            "Google": "google tech modern office",
            "Apple": "apple logo tech modern",
            "YouTube": "youtube watching video phone",
            "Netflix": "netflix streaming tv series",
            "Uber": "uber ride car city",
            "Taxi": "taxi cab yellow city",
            "Amazon": "amazon package delivery shopping",
            "Local Shop": "local market small business",
        }
    },
    "рџ‘™ Girls Battle": {
        "battles": [
            ("Blonde", "Brunette"),
            ("Fitness Girl", "Curvy Girl"),
            ("Natural Beauty", "Full Makeup"),
            ("Beach Girl", "Gym Girl"),
            ("Tattoo Girl", "Clean Look"),
            ("Short Hair", "Long Hair"),
            ("Blue Eyes", "Brown Eyes"),
            ("Street Style", "Elegant Look"),
            ("Sporty Girl", "Girly Girl"),
            ("Summer Vibe", "Winter Vibe"),
        ],
        "pexels": {
            "Blonde": "blonde model studio portrait dark background",
            "Brunette": "brunette model studio portrait dark background",
            "Fitness Girl": "fitness model athletic woman sport dark",
            "Curvy Girl": "curvy woman confident fashion model",
            "Natural Beauty": "natural woman no makeup fresh skin portrait",
            "Full Makeup": "woman glamour makeup red lips portrait",
            "Beach Girl": "woman bikini beach ocean summer",
            "Gym Girl": "woman gym workout strong fitness dark",
            "Tattoo Girl": "woman tattoos dark alternative model",
            "Clean Look": "woman clean elegant fashion model",
            "Short Hair": "woman short hair model fashion portrait",
            "Long Hair": "woman long hair flowing model beautiful",
            "Blue Eyes": "woman blue eyes portrait close up studio",
            "Brown Eyes": "woman brown eyes portrait dark studio",
            "Street Style": "woman street fashion urban style",
            "Elegant Look": "woman elegant dress luxury fashion",
            "Sporty Girl": "woman sporty athletic casual outdoor",
            "Girly Girl": "woman feminine pink elegant dress",
            "Summer Vibe": "woman summer tropical beach vibes",
            "Winter Vibe": "woman winter fashion snow cozy",
        }
    },
    "рџ§  Deep Questions": {
        "battles": [
            ("Truth", "Kindness"),
            ("Revenge", "Forgiveness"),
            ("Logic", "Intuition"),
            ("Alpha", "Sigma"),
            ("Respected", "Loved"),
            ("Die Famous", "Live Unknown"),
            ("Hard Truth", "Sweet Lie"),
            ("Short Pleasure", "Long Success"),
            ("Passion", "Stability"),
            ("Being Right", "Being Happy"),
        ],
        "pexels": {
            "Truth": "truth light mirror honest face",
            "Kindness": "kindness help hand charity",
            "Revenge": "dark storm angry revenge shadow",
            "Forgiveness": "forgiveness light peace calm",
            "Logic": "chess strategy thinking mind",
            "Intuition": "intuition spiritual meditation soul",
            "Alpha": "alpha male confident strong leader",
            "Sigma": "lone wolf solitary alone dark forest",
            "Respected": "respected leader business podium",
            "Loved": "loved couple embrace romantic",
            "Die Famous": "celebrity famous spotlight crowd",
            "Live Unknown": "peaceful unknown quiet simple life",
            "Hard Truth": "mirror truth face honest reality",
            "Sweet Lie": "sweet smile fake mask illusion",
            "Short Pleasure": "party fun night pleasure enjoy",
            "Long Success": "success trophy achievement goal",
            "Passion": "passion fire intense emotion",
            "Stability": "stable home family secure",
            "Being Right": "arguing debate strong opinion",
            "Being Happy": "happy smile joy content",
        }
    },
}

CATEGORIES["🌍 Места & Путешествия"] = {
    "battles": [
        ("Dubai", "Miami"),
        ("New York", "Los Angeles"),
        ("Paris", "Rome"),
        ("Bali", "Maldives"),
        ("Tokyo", "Seoul"),
        ("Las Vegas", "Ibiza"),
        ("Santorini", "Capri"),
        ("London", "Barcelona"),
        ("Hawaii", "Bahamas"),
        ("Monaco", "Singapore"),
        ("Thailand", "Mexico"),
        ("Amsterdam", "Berlin"),
        ("Iceland", "Switzerland"),
        ("Rio", "Cancun"),
        ("Sydney", "Melbourne"),
        ("Marrakech", "Istanbul"),
        ("Mykonos", "Tulum"),
        ("Aspen", "Lake Como"),
        ("Hong Kong", "Shanghai"),
        ("Cape Town", "Lisbon"),
    ],
    "pexels": {
        "Dubai": "Dubai luxury skyline bright sunny beach supercars",
        "Miami": "Miami beach neon nightlife palm trees bright",
        "New York": "New York city skyline Times Square bright lights",
        "Los Angeles": "Los Angeles Hollywood sunset palm trees luxury",
        "Paris": "Paris Eiffel Tower romantic bright cinematic",
        "Rome": "Rome Italy colosseum sunset travel cinematic",
        "Bali": "Bali tropical villa jungle beach bright",
        "Maldives": "Maldives overwater villa turquoise ocean bright",
        "Tokyo": "Tokyo neon city street vibrant night",
        "Seoul": "Seoul city neon kpop street vibrant",
        "Las Vegas": "Las Vegas strip neon party bright",
        "Ibiza": "Ibiza beach party sunset luxury",
        "Santorini": "Santorini Greece white houses blue sea bright",
        "Capri": "Capri Italy luxury coast bright blue water",
        "London": "London city landmarks bright travel",
        "Barcelona": "Barcelona beach city sunny travel",
        "Hawaii": "Hawaii tropical beach volcano bright",
        "Bahamas": "Bahamas turquoise water tropical beach",
        "Monaco": "Monaco luxury yachts casino bright",
        "Singapore": "Singapore skyline marina bay bright",
        "Thailand": "Thailand island beach tropical bright",
        "Mexico": "Mexico resort beach colorful travel",
        "Amsterdam": "Amsterdam canals colorful city bright",
        "Berlin": "Berlin city nightlife bright street",
        "Iceland": "Iceland waterfall northern lights epic",
        "Switzerland": "Switzerland alpine mountains luxury bright",
        "Rio": "Rio de Janeiro beach carnival bright",
        "Cancun": "Cancun resort beach turquoise water",
        "Sydney": "Sydney opera house harbor bright",
        "Melbourne": "Melbourne city street art bright",
        "Marrakech": "Marrakech market colorful luxury travel",
        "Istanbul": "Istanbul mosque city sunset travel",
        "Mykonos": "Mykonos Greece beach party bright",
        "Tulum": "Tulum Mexico beach jungle luxury",
        "Aspen": "Aspen luxury ski resort sunny snow",
        "Lake Como": "Lake Como Italy luxury villa bright",
        "Hong Kong": "Hong Kong skyline neon harbor bright",
        "Shanghai": "Shanghai skyline neon futuristic bright",
        "Cape Town": "Cape Town beach mountain bright travel",
        "Lisbon": "Lisbon Portugal colorful streets ocean bright",
    }
}

CATEGORY_EXTRAS = {
    0: [
        ("Private Jet", "Super Yacht"), ("CEO Life", "Creator Life"),
        ("Luxury Watch", "Sports Car"), ("Penthouse", "Beach Villa"),
        ("Gold Card", "Crypto Wallet"), ("Startup", "Real Estate"),
        ("Passive Income", "Dream Job"), ("Millionaire", "Influencer"),
        ("Big City", "Island Life"), ("Shopping Spree", "Early Retirement"),
    ],
    1: [
        ("G-Wagon", "Range Rover"), ("Cybertruck", "Hummer EV"),
        ("Ferrari Roma", "Porsche GT3"), ("Lambo Huracan", "McLaren 720S"),
        ("Classic Mustang", "Dodge Charger"), ("Maybach", "Bentley GT"),
        ("Superbike", "Supercar"), ("JDM", "German Cars"),
        ("Offroad Jeep", "Luxury Sedan"), ("Drift Car", "Drag Car"),
    ],
    2: [
        ("Ice Cream", "Donuts"), ("Smoothie", "Milkshake"),
        ("Lobster", "Caviar"), ("BBQ Ribs", "Fried Wings"),
        ("Croissant", "Bagel"), ("Boba Tea", "Lemonade"),
        ("Nachos", "Mozzarella Sticks"), ("Poke Bowl", "Caesar Salad"),
        ("Hot Dog", "Chicken Sandwich"), ("Tiramisu", "Brownie"),
    ],
    3: [
        ("DJ Set", "Live Band"), ("Grammy", "Oscar"),
        ("Comedy Show", "Horror Movie"), ("K-Pop", "Latin Music"),
        ("VIP Club", "House Party"), ("Podcast", "Reality Show"),
        ("Rap Battle", "Dance Battle"), ("Music Video", "Movie Trailer"),
        ("Karaoke", "Open Mic"), ("Backstage Pass", "Front Row"),
    ],
    4: [
        ("Six Pack", "Big Arms"), ("Yoga", "CrossFit"),
        ("Protein Shake", "Green Juice"), ("Sauna", "Ice Bath"),
        ("Luxury Hotel", "Camping"), ("Road Trip", "Cruise"),
        ("Morning Run", "Midnight Walk"), ("Spa Day", "Leg Day"),
        ("Surfing", "Snowboarding"), ("Streetwear", "Old Money Style"),
    ],
    5: [
        ("AirPods", "Beats"), ("iPad", "Gaming Laptop"),
        ("VR Headset", "Drone"), ("Netflix", "Disney Plus"),
        ("Tesla", "Rivian"), ("ChatGPT", "Gemini"),
        ("Sneakers", "Smartwatch"), ("GoPro", "iPhone Camera"),
        ("TikTok Fame", "YouTube Fame"), ("Amazon Prime", "Apple Store"),
    ],
    6: [
        ("Red Dress", "Black Dress"), ("Beach Look", "City Look"),
        ("Luxury Girl", "Sporty Girl"), ("Curly Hair", "Straight Hair"),
        ("Blue Bikini", "Red Bikini"), ("Fashion Model", "Fitness Model"),
        ("Soft Glam", "Bold Glam"), ("Summer Tan", "Snow Queen"),
        ("High Heels", "Sneakers"), ("Angel Look", "Baddie Look"),
    ],
    7: [
        ("Risk", "Comfort"), ("Dreams", "Reality"),
        ("Money First", "Love First"), ("Silence", "Truth"),
        ("Past", "Future"), ("Famous Friend", "Loyal Friend"),
        ("One Chance", "Second Chance"), ("Fast Win", "Slow Growth"),
        ("Big Ego", "Big Heart"), ("Wild Life", "Peaceful Life"),
    ],
}

for index, category_name in enumerate(list(CATEGORIES.keys())):
    extras = CATEGORY_EXTRAS.get(index, [])
    CATEGORIES[category_name]["battles"].extend(extras)
    pexels_map = CATEGORIES[category_name].setdefault("pexels", {})
    for left, right in extras:
        pexels_map.setdefault(left, f"{left} bright colorful viral cinematic photo")
        pexels_map.setdefault(right, f"{right} bright colorful viral cinematic photo")

CATEGORY_NAMES = list(CATEGORIES.keys())
CATEGORY_DISPLAY = {
    CATEGORY_NAMES[0]: "💰 Деньги и успех",
    CATEGORY_NAMES[1]: "🚗 Машины и люкс",
    CATEGORY_NAMES[2]: "🍔 Еда и напитки",
    CATEGORY_NAMES[3]: "🎵 Музыка и шоу",
    CATEGORY_NAMES[4]: "💪 Лайфстайл и фитнес",
    CATEGORY_NAMES[5]: "📱 Техника и бренды",
    CATEGORY_NAMES[6]: "💃 Девушки баттл",
    CATEGORY_NAMES[7]: "🧠 Глубокие вопросы",
    CATEGORY_NAMES[8]: "🌍 Места и путешествия",
}
DISPLAY_TO_CATEGORY = {v: k for k, v in CATEGORY_DISPLAY.items()}
RANDOM_CATEGORY_TEXT = "🎲 Случайная категория"


def category_title(category_name):
    return CATEGORY_DISPLAY.get(category_name, category_name)


def normalize_battle(battle):
    return tuple(sorted([battle[0], battle[1]]))

# РҐСЂР°РЅРёР»РёС‰Р°
pending_videos = {}
publish_queue = {}
USED_VARIANTS_FILE = "/tmp/used_variants.json"
user_category = {}  # С‚РµРєСѓС‰Р°СЏ РєР°С‚РµРіРѕСЂРёСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ


def load_used_variants():
    try:
        with open(USED_VARIANTS_FILE, "r") as f:
            data = json.load(f)
            return {int(k): set(tuple(v) for v in vals) for k, vals in data.items()}
    except Exception:
        return {}


def save_used_variants(used):
    try:
        with open(USED_VARIANTS_FILE, "w") as f:
            json.dump({str(k): [list(v) for v in vals] for k, vals in used.items()}, f)
    except Exception:
        pass


used_variants = load_used_variants()


def get_session():
    session = requests.Session()
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_image_pollinations(prompt):
    """Generate a free image through Pollinations. Returns PIL Image or None."""
    try:
        session = get_session()
        full_prompt = (
            f"{prompt}, bright colorful viral TikTok style image, glossy luxury look, "
            "sunny vibrant lighting, high contrast, saturated colors, energetic mood, "
            "professional commercial photography, sharp focus, clean background, "
            "beautiful composition, no text, no captions, no watermark, no logo"
        )
        encoded_prompt = urllib.parse.quote(full_prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width=1024&height=576&model={urllib.parse.quote(POLLINATIONS_MODEL)}"
            "&nologo=true&private=true&enhance=true"
        )

        r = session.get(
            url,
            headers={"Accept": "image/*"},
            timeout=POLLINATIONS_TIMEOUT
        )
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "")
        if "image" not in content_type.lower():
            logger.warning(f"Pollinations returned non-image response: {r.text[:300]}")
            return None

        logger.info(f"Pollinations image generated for: {prompt[:30]}")
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Pollinations failed: {e}")
        return None


def fetch_image(query, category_name):
    logger.info(f"Generating: {query}")
    category = CATEGORIES.get(category_name, {})
    pexels_map = category.get("pexels", {})
    search_query = pexels_map.get(query, f"{query} dramatic dark")
    search_query = f"{search_query} bright colorful vibrant high energy"

    # First try free AI generation through Pollinations.
    img = fetch_image_pollinations(search_query)
    if img:
        return img

    # Fallback to Pexels if Gemini is unavailable or failed.
    logger.info(f"Falling back to Pexels for: {query}")
    session = get_session()
    headers = {"Authorization": PEXELS_API_KEY}

    for q in [search_query, query, "dramatic dark cinematic"]:
        try:
            r = session.get("https://api.pexels.com/v1/search",
                           params={"query": q, "per_page": 20, "orientation": "landscape"},
                           headers=headers, timeout=20)
            r.raise_for_status()
            photos = r.json().get("photos", [])
            if photos:
                photo = random.choice(photos)
                img_url = photo["src"]["large2x"] if "large2x" in photo["src"] else photo["src"]["large"]
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


def make_beep_pcm(freq=880, sr=44100, duration=0.12):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    wave = (0.4 * np.sin(2 * np.pi * freq * t) * np.linspace(1, 0, len(t))).astype(np.float32)
    silence = np.zeros(sr - len(wave), dtype=np.float32)
    mono = np.concatenate([wave, silence])
    return (np.stack([mono, mono], axis=1) * 32767).astype(np.int16).tobytes()


def make_voiceover(text, tmp_dir, index):
    """Create a short English voiceover mp3. Returns path or None."""
    try:
        encoded_text = urllib.parse.quote(text[:180])
        url = (
            "https://translate.google.com/translate_tts"
            f"?ie=UTF-8&tl=en&client=tw-ob&q={encoded_text}"
        )
        r = get_session().get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "audio/mpeg,*/*",
            },
            timeout=20
        )
        r.raise_for_status()
        path = os.path.join(tmp_dir, f"voice_{index}.mp3")
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        logger.warning(f"Voiceover failed: {e}")
        return None


def build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, index):
    logger.info(f"Building clip {index}: {left_label} VS {right_label}")
    out_path = os.path.join(tmp_dir, f"battle_{index:02d}.mp4")
    raw_path = os.path.join(tmp_dir, f"battle_raw_{index:02d}.mp4")
    audio_path = os.path.join(tmp_dir, f"audio_{index}.pcm")

    left_pct = random.randint(30, 70)
    right_pct = 100 - left_pct

    frames_bytes = b""
    audio_bytes = b""

    for sec in range(CLIP_DURATION, 0, -1):
        frame = build_frame(left_label, right_label, left_img, right_img, countdown=sec)
        for _ in range(FPS):
            frames_bytes += frame.tobytes()
        audio_bytes += make_beep_pcm(freq=1200 if sec == 1 else 880)

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
        "-shortest", raw_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.communicate(input=frames_bytes)

    voice_path = make_voiceover(f"{left_label} versus {right_label}. Which one would you choose?", tmp_dir, index)
    if voice_path:
        try:
            subprocess.run([
                "ffmpeg", "-y", "-i", raw_path, "-i", voice_path,
                "-filter_complex", "[0:a]volume=0.25[a0];[1:a]volume=1.45[a1];[a0][a1]amix=inputs=2:duration=first[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                "-shortest", out_path
            ], check=True, capture_output=True)
        except Exception as e:
            logger.warning(f"Voice mix failed: {e}")
            os.rename(raw_path, out_path)
    else:
        os.rename(raw_path, out_path)

    logger.info(f"Clip {index} done")
    return out_path


def download_music(tmp_dir):
    try:
        music_urls = [
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3",
        ]
        r = get_session().get(random.choice(music_urls), timeout=30)
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
            "-filter_complex", "[1:a]volume=0.18[m];[0:a][m]amix=inputs=2:duration=first[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
            "-shortest", out
        ], check=True, capture_output=True)
    else:
        os.rename(merged, out)
    return out


def generate_metadata(variants, category_name):
    clean_cat = re.sub(r'[^\w\s]', '', category_title(category_name)).strip()
    title = f"{variants[0][0]} VS {variants[0][1]} - Which Side Are You On? #shorts"
    desc = "Every day we put two choices head-to-head - YOU decide!\n\n"
    desc += f"Category: {clean_cat}\n\nToday's battles:\n"
    for l, r in variants:
        desc += f"* {l} VS {r}\n"
    desc += "\nLIKE for top | COMMENT for bottom\n"
    desc += "Subscribe @BattleVoteUSA\n\n"
    desc += "#shorts #vs #battle #wouldyourather #viral #battlevote #pickone"
    return title, desc


def generate_tiktok_metadata(variants):
    title = f"{variants[0][0]} VS {variants[0][1]} - Which side are you? Comment below!"
    tags = "#vs #battle #foryou #fyp #viral #wouldyourather #pickone #shorts #battlevote #trending"
    return title, f"{title}\n\n{tags}"


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
    now_utc = datetime.datetime.utcnow()
    is_dst = 3 <= now_utc.month <= 11
    utc_offset = 4 if is_dst else 5

    if user_id not in publish_queue:
        publish_queue[user_id] = []

    publish_queue[user_id] = [s for s in publish_queue[user_id] if s["target_utc"] > now_utc]
    busy = [s["hour_est"] for s in publish_queue[user_id] if s["day"] == now_utc.date()]

    for slot in QUEUE_SLOTS:
        if slot not in busy:
            target_hour_utc = (slot + utc_offset) % 24
            target = now_utc.replace(hour=target_hour_utc, minute=0, second=0, microsecond=0)
            if target > now_utc:
                return slot, target, now_utc.date()

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
        await message.answer(f"Published!\n{url}")
    except Exception as e:
        logger.error(f"Scheduled upload error: {e}", exc_info=True)
        await message.answer(f"Publish error: {e}")


async def build_video_for_user(user_id, category_name, variants, message):
    try:
        tmp_dir = tempfile.mkdtemp()
        clip_paths = []

        for idx, (left_label, right_label) in enumerate(variants, start=1):
            await message.answer(f"Battle {idx}/5: {left_label} VS {right_label}")
            left_img = fetch_image(left_label, category_name)
            right_img = fetch_image(right_label, category_name)
            clip_path = build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, idx)
            clip_paths.append(clip_path)

        await message.answer("Merging final video...")
        final_path = concat_with_ffmpeg(clip_paths, tmp_dir)
        title, description = generate_metadata(variants, category_name)
        _, tiktok_desc = generate_tiktok_metadata(variants)

        pending_videos[user_id] = {
            "path": final_path,
            "tmp_dir": tmp_dir,
            "title": title,
            "description": description
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📅 В очередь", callback_data="add_to_queue"),
            InlineKeyboardButton(text="🚀 Сейчас", callback_data="publish_now"),
        ]])

        await message.answer_video(
            FSInputFile(final_path, filename="vs_battle.mp4"),
            caption=f"Готово! Категория: {category_title(category_name)}",
            supports_streaming=True
        )
        await message.answer(
            f"YouTube:\n{title}\n\nTikTok:\n{tiktok_desc}"
        )
        await message.answer("Опубликовать на YouTube?", reply_markup=kb)

    except Exception as e:
        logger.error(f"Build error: {e}", exc_info=True)
        await message.answer(f"Error: {e}")


def get_category_keyboard():
    buttons = []
    for i in range(0, len(CATEGORY_NAMES), 2):
        row = [KeyboardButton(text=category_title(CATEGORY_NAMES[i]))]
        if i + 1 < len(CATEGORY_NAMES):
            row.append(KeyboardButton(text=category_title(CATEGORY_NAMES[i + 1])))
        buttons.append(row)
    buttons.append([KeyboardButton(text=RANDOM_CATEGORY_TEXT)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "BattleVote Bot\nВыбери категорию для генерации видео:",
        reply_markup=get_category_keyboard()
    )


@dp.message(F.text == RANDOM_CATEGORY_TEXT)
async def random_category(message: Message):
    category_name = random.choice(CATEGORY_NAMES)
    await generate_from_category(message, category_name)


@dp.message(F.text.in_(set(DISPLAY_TO_CATEGORY.keys())))
async def category_selected(message: Message):
    await generate_from_category(message, DISPLAY_TO_CATEGORY[message.text])


async def generate_from_category(message: Message, category_name: str):
    user_id = message.from_user.id
    category = CATEGORIES[category_name]
    all_battles = category["battles"]

    if user_id not in used_variants:
        used_variants[user_id] = set()

    available = [b for b in all_battles if normalize_battle(b) not in used_variants[user_id]]
    if len(available) < 5:
        used_variants[user_id] = {v for v in used_variants[user_id]
                                   if v not in [normalize_battle(b) for b in all_battles]}
        available = all_battles.copy()

    variants = random.sample(available, min(5, len(available)))
    variants = [(r, l) if random.random() < 0.5 else (l, r) for l, r in variants]
    for v in variants:
        used_variants[user_id].add(normalize_battle(v))
    save_used_variants(used_variants)

    await message.answer(
        f"Категория: {category_title(category_name)}\n\n" +
        "\n".join(f"* {l} VS {r}" for l, r in variants)
    )
    await build_video_for_user(user_id, category_name, variants, message)


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
        "id": slot_id, "hour_est": slot_hour,
        "day": target_day, "target_utc": target_utc
    })

    day_str = "Today" if target_day == datetime.datetime.utcnow().date() else "Tomorrow"
    queue_text = f"Added to queue!\n{day_str} at {slot_hour}:00 EST\n\nQueue:\n"
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


async def autopilot():
    if not AUTOPILOT_ENABLED or not AUTOPILOT_USER_ID:
        return

    logger.info("Autopilot started")

    while True:
        now_utc = datetime.datetime.utcnow()
        is_dst = 3 <= now_utc.month <= 11
        utc_offset = 4 if is_dst else 5

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

        try:
            user_id = AUTOPILOT_USER_ID

            # Р’С‹Р±РёСЂР°РµРј СЃР»СѓС‡Р°Р№РЅСѓСЋ РєР°С‚РµРіРѕСЂРёСЋ
            category_name = random.choice(CATEGORY_NAMES)
            category = CATEGORIES[category_name]
            all_battles = category["battles"]

            if user_id not in used_variants:
                used_variants[user_id] = set()

            available = [b for b in all_battles if tuple(b) not in used_variants[user_id]]
            if len(available) < 5:
                used_variants[user_id] = {v for v in used_variants[user_id]
                                           if v not in [tuple(b) for b in all_battles]}
                available = all_battles.copy()

            variants = random.sample(available, min(5, len(available)))
            for v in variants:
                used_variants[user_id].add(tuple(v))
            save_used_variants(used_variants)

            logger.info(f"Autopilot: {category_name} вЂ” {variants}")
            await bot.send_message(user_id, f"Autopilot: {category_name}")

            tmp_dir = tempfile.mkdtemp()
            clip_paths = []

            for idx, (left_label, right_label) in enumerate(variants, start=1):
                left_img = fetch_image(left_label, category_name)
                right_img = fetch_image(right_label, category_name)
                clip_path = build_battle_clip(left_label, right_label, left_img, right_img, tmp_dir, idx)
                clip_paths.append(clip_path)

            final_path = concat_with_ffmpeg(clip_paths, tmp_dir)
            title, description = generate_metadata(variants, category_name)

            url = upload_to_youtube(final_path, title, description)
            await bot.send_message(user_id, f"Autopilot published!\n{url}")
            logger.info(f"Autopilot published: {url}")

        except Exception as e:
            logger.error(f"Autopilot error: {e}", exc_info=True)
            try:
                await bot.send_message(AUTOPILOT_USER_ID, f"Autopilot error: {e}")
            except Exception:
                pass

        await asyncio.sleep(60)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    if AUTOPILOT_ENABLED:
        asyncio.create_task(autopilot())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

