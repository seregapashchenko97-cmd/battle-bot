from PIL import Image
import requests
from io import BytesIO
import random
from moviepy.editor import ImageClip
import os

# =========================
# TELEGRAM
# =========================

BOT_TOKEN = "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE"
CHAT_ID = "476718796"

# =========================
# SIZE
# =========================

WIDTH = 1080
HEIGHT = 1920
HALF_HEIGHT = HEIGHT // 2

# =========================
# BATTLES
# =========================

battles = [

    {
        "top": "https://images.unsplash.com/photo-1544636331-e26879cd4d9b?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1800"
    },

    {
        "top": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?q=80&w=1800"
    },

    {
        "top": "https://images.unsplash.com/photo-1511389026070-a14ae610a1be?q=80&w=1800",
        "bottom": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?q=80&w=1800"
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

image_path = "battle.jpg"

final.save(
    image_path,
    quality=95
)

# =========================
# CREATE VIDEO
# =========================

clip = ImageClip(image_path)

clip = clip.set_duration(5)

clip = clip.resize(
    lambda t: 1 + 0.03 * t
)

video_path = "battle.mp4"

clip.write_videofile(
    video_path,
    fps=30,
    codec="libx264",
    audio=False
)

# =========================
# SEND TO TELEGRAM
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
