import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips
import numpy as np
import random
import os

WIDTH = 1080
HEIGHT = 1920
FPS = 30
DURATION = 5

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

choices = [
"BMW",
"MERCEDES"
]

def download_image():
response = requests.get("https://picsum.photos/1080/1920")
return Image.open(BytesIO(response.content)).convert("RGB")

img1 = download_image()
img2 = download_image()

winner = random.choice([0, 1])

font_big = ImageFont.load_default()
font_timer = ImageFont.load_default()
font_vs = ImageFont.load_default()

frames = []

for i in range(DURATION * FPS):

```
t = i / FPS
seconds_left = DURATION - int(t)

bg = Image.new("RGB", (WIDTH, HEIGHT), "black")

left = img1.resize((WIDTH // 2, HEIGHT))
right = img2.resize((WIDTH // 2, HEIGHT))

zoom = 1 + (t * 0.04)

zw = int((WIDTH // 2) * zoom)
zh = int(HEIGHT * zoom)

left = left.resize((zw, zh))
right = right.resize((zw, zh))

left_crop = left.crop((0, 0, WIDTH // 2, HEIGHT))
right_crop = right.crop((0, 0, WIDTH // 2, HEIGHT))

bg.paste(left_crop, (0, 0))
bg.paste(right_crop, (WIDTH // 2, 0))

draw = ImageDraw.Draw(bg)

timer_text = str(seconds_left)

timer_box = draw.textbbox(
    (0, 0),
    timer_text,
    font=font_timer
)

timer_width = timer_box[2] - timer_box[0]

timer_x = WIDTH // 2 - timer_width // 2

draw.text(
    (timer_x, 80),
    timer_text,
    fill="white",
    font=font_timer
)

left_color = "white"
right_color = "white"

if seconds_left <= 1:
    if winner == 0:
        left_color = "#00ff66"
    else:
        right_color = "#00ff66"

draw.text(
    (60, 350),
    choices[0],
    fill=left_color,
    font=font_big
)

draw.text(
    (WIDTH // 2 + 60, 350),
    choices[1],
    fill=right_color,
    font=font_big
)

vs_box = draw.textbbox(
    (0, 0),
    "VS",
    font=font_vs
)

vs_width = vs_box[2] - vs_box[0]

vs_x = WIDTH // 2 - vs_width // 2
vs_y = HEIGHT // 2 - 120

draw.text(
    (vs_x, vs_y),
    "VS",
    fill="white",
    font=font_vs
)

frames.append(np.array(bg))
```

clips = []

for frame in frames:
clip = ImageClip(frame).set_duration(1 / FPS)
clips.append(clip)

video = concatenate_videoclips(
clips,
method="compose"
)

video.write_videofile(
"battle.mp4",
fps=FPS,
codec="libx264",
audio=False,
preset="ultrafast"
)

with open("battle.mp4", "rb") as video_file:

```
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
    data={
        "chat_id": CHAT_ID
    },
    files={
        "video": video_file
    }
)
```

print("VIDEO SENT")
