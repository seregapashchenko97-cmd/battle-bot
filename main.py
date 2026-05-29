from PIL import Image, ImageDraw, ImageFont

Image.ANTIALIAS = Image.Resampling.LANCZOS

import requests
from io import BytesIO
import random
from moviepy.editor import *
import os

# =========================
# TELEGRAM
# =========================

BOT_TOKEN = "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE"
CHAT_ID = "476718796"

# =========================
# SIZE
# =========================

WIDTH = 720
HEIGHT = 1280
HALF_HEIGHT = HEIGHT // 2

# =========================
# BATTLES
# =========================

battles = [

    {
        "top_text": "LUXURY VILLA",
        "bottom_text": "PRIVATE JET",
        "top": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=1800"
    },

    {
        "top_text": "MALDIVES",
        "bottom_text": "LAMBORGHINI",
        "top": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?q=80&w=1800"
    },

    {
        "top_text": "PENTHOUSE",
        "bottom_text": "YACHT",
        "top": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1567899378494-47b22a2ae96a?q=80&w=1800"
    }

]

battle = random.choice(battles)

# =========================
# LOAD IMAGE
# =========================

def load_image(url):

    response = requests.get(url)

    img = Image.open(
        BytesIO(response.content)
    ).convert("RGB")

    scale = max(
        WIDTH / img.width,
        HALF_HEIGHT / img.height
    )

    img = img.resize(
        (
            int(img.width * scale),
            int(img.height * scale)
        )
    )

    left = (img.width - WIDTH) // 2
    top = (img.height - HALF_HEIGHT) // 2

    img = img.crop(
        (
            left,
            top,
            left + WIDTH,
            top + HALF_HEIGHT
        )
    )

    return img

# =========================
# CREATE IMAGE
# =========================

top_img = load_image(battle["top"])
bottom_img = load_image(battle["bottom"])

final = Image.new(
    "RGB",
    (WIDTH, HEIGHT)
)

final.paste(top_img, (0, 0))
final.paste(bottom_img, (0, HALF_HEIGHT))

draw = ImageDraw.Draw(final)

# =========================
# FONT
# =========================

try:
    font_big = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        70
    )

    font_vs = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        120
    )

    timer_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        90
    )

except:
    font_big = ImageFont.load_default()
    font_vs = ImageFont.load_default()
    timer_font = ImageFont.load_default()

# =========================
# TEXT
# =========================

top_text = battle["top_text"]
bottom_text = battle["bottom_text"]

# top text
draw.text(
    (WIDTH // 2, HALF_HEIGHT - 180),
    top_text,
    anchor="mm",
    font=font_big,
    fill="white",
    stroke_width=4,
    stroke_fill="black"
)

# bottom text
draw.text(
    (WIDTH // 2, HALF_HEIGHT + 180),
    bottom_text,
    anchor="mm",
    font=font_big,
    fill="white",
    stroke_width=4,
    stroke_fill="black"
)

# VS
draw.text(
    (WIDTH // 2, HALF_HEIGHT),
    "VS",
    anchor="mm",
    font=font_vs,
    fill="yellow",
    stroke_width=6,
    stroke_fill="black"
)

# TIMER
draw.text(
    (WIDTH // 2, HALF_HEIGHT - 80),
    "5",
    anchor="mm",
    font=timer_font,
    fill="red",
    stroke_width=5,
    stroke_fill="black"
)

image_path = "battle.jpg"

final.save(
    image_path,
    quality=90
)

# =========================
# VIDEO
# =========================

clip = ImageClip(image_path).set_duration(5)

video_path = "battle.mp4"

clip.write_videofile(
    video_path,
    fps=24,
    codec="libx264",
    preset="ultrafast",
    audio=False,
    threads=2
)

# =========================
# SEND TELEGRAM
# =========================

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"

files = {
    "video": open(video_path, "rb")
}

data = {
    "chat_id": CHAT_ID
}

response = requests.post(
    url,
    files=files,
    data=data
)

print(response.text)
