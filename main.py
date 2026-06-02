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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-image")
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
# РўР•РњРђРўРР§Р•РЎРљРР• РљРђРўР•Р“РћР РР
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
