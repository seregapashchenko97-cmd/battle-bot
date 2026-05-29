```python id="q7m4xp"
from PIL import Image, ImageDraw, ImageFont

Image.ANTIALIAS = Image.Resampling.LANCZOS

import requests
from io import BytesIO
import random
from moviepy.editor import *

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
HALF = HEIGHT // 2

# =========================
# BATTLES
# =========================

battles = [

    {
        "top_text": "PRIVATE JET",
        "bottom_text": "LUXURY VILLA",
        "top": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1800"
    },

    {
        "top_text": "MALDIVES",
        "bottom_text": "LAMBORGHINI",
        "top": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?q=80&w=1800"
    }

]

battle = random.choice(battles)

# =========================
# LOAD IMAGE
# =========================

def load_image(url, target_h):

    response = requests.get(url)

    img = Image.open(
        BytesIO(response.content)
    ).convert("RGB")

    scale = max(
        WIDTH / img.width,
        target_h / img.height
    )

    img = img.resize(
        (
            int(img.width * scale),
            int(img.height * scale)
        )
    )

    left = (img.width - WIDTH) // 2
    top = (img.height - target_h) // 2

    img = img.crop(
        (
            left,
            top,
            left + WIDTH,
            top + target_h
        )
    )

    return img

# =========================
# CREATE IMAGE
# =========================

top_img = load_image(battle["top"], HALF)
bottom_img = load_image(battle["bottom"], HALF)

canvas = Image.new("RGB", (WIDTH, HEIGHT))

canvas.paste(top_img, (0, 0))
canvas.paste(bottom_img, (0, HALF))

# =========================
# OVERLAY
# =========================

overlay = Image.new(
    "RGBA",
    (WIDTH, HEIGHT),
    (0, 0, 0, 70)
)

canvas = Image.alpha_composite(
    canvas.convert("RGBA"),
    overlay
)

draw = ImageDraw.Draw(canvas)

# =========================
# FONTS
# =========================

try:

    font_big = ImageFont.truetype(
        "DejaVuSans-Bold.ttf",
        110
    )

    font_vs = ImageFont.truetype(
        "DejaVuSans-Bold.ttf",
        240
    )

    timer_font = ImageFont.truetype(
        "DejaVuSans-Bold.ttf",
        150
    )

except:

    font_big = ImageFont.load_default()
    font_vs = ImageFont.load_default()
    timer_font = ImageFont.load_default()

# =========================
# LINE
# =========================

draw.line(
    [(0, HALF), (WIDTH, HALF)],
    fill=(255,255,255),
    width=10
)

# =========================
# TOP TEXT
# =========================

draw.text(
    (WIDTH // 2, HALF - 180),
    battle["top_text"],
    anchor="mm",
    font=font_big,
    fill=(255,255,255),
    stroke_width=8,
    stroke_fill=(0,0,0)
)

# =========================
# BOTTOM TEXT
# =========================

draw.text(
    (WIDTH // 2, HALF + 180),
    battle["bottom_text"],
    anchor="mm",
    font=font_big,
    fill=(255,255,255),
    stroke_width=8,
    stroke_fill=(0,0,0)
)

# =========================
# VS
# =========================

draw.text(
    (WIDTH // 2, HALF),
    "VS",
    anchor="mm",
    font=font_vs,
    fill=(255,215,0),
    stroke_width=12,
    stroke_fill=(0,0,0)
)

# =========================
# TIMER
# =========================

draw.text(
    (WIDTH // 2, HALF - 120),
    "5",
    anchor="mm",
    font=timer_font,
    fill=(255,50,50),
    stroke_width=10,
    stroke_fill=(0,0,0)
)

# =========================
# SAVE IMAGE
# =========================

image_path = "battle.png"

canvas.convert("RGB").save(
    image_path,
    quality=95
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

requests.post(
    url,
    files=files,
    data=data
)

print("DONE")
```
