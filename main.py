import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip
import numpy as np
import random
import os

WIDTH = 1080
HEIGHT = 1920
DURATION = 5
FPS = 30

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

try:
font_big = ImageFont.truetype(
"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
120
)

```
font_timer = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    220
)

font_vs = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    260
)
```

except:
font_big = ImageFont.load_default()
font_timer = ImageFont.load_default()
font_vs = ImageFont.load_default()

frames = []

for i in range(DURATION * FPS):

```
t = i / FPS
seconds_left = DURATION - int(t)

base = Image.new("RGB", (WIDTH, HEIGHT), "black")

left = img1.resize((WIDTH // 2, HEIGHT))
right = img2.resize((WIDTH // 2, HEIGHT))

zoom = 1 + (t * 0.03)

zw = int((WIDTH // 2) * zoom)
zh = int(HEIGHT * zoom)

left = left.resize((zw, zh))
right = right.resize((zw, zh))

lx = -(zw - WIDTH // 2) // 2
ly = -(zh - HEIGHT) // 2

rx = -(zw - WIDTH // 2) // 2
ry = -(zh - HEIGHT) // 2

base.paste(left.crop((0, 0, WIDTH // 2, HEIGHT)), (0, 0))
base.paste(right.crop((0, 0, WIDTH // 2, HEIGHT)), (WIDTH // 2, 0))

draw = ImageDraw.Draw(base)

timer_text = str(seconds_left)

timer_box = draw.textbbox(
    (0, 0),
    timer_text,
    font=font_timer
)

timer_width = timer_box[2] - timer_box[0]

timer_x = WIDTH // 2 - timer_width // 2
timer_y = 80

draw.text(
    (timer_x, timer_y),
    timer_text,
    font=font_timer,
    fill="white",
    stroke_width=8,
    stroke_fill="black"
)

left_color = "white"
right_color = "white"

if seconds_left <= 1:
    if winner == 0:
        left_color = "#00ff66"
    else:
        right_color = "#00ff66"

draw.text(
    (70, 350),
    choices[0],
    font=font_big,
    fill=left_color,
    stroke_width=6,
    stroke_fill="black"
)

draw.text(
    (WIDTH // 2 + 70, 350),
    choices[1],
    font=font_big,
    fill=right_color,
    stroke_width=6,
    stroke_fill="black"
)

vs_text = "VS"

vs_box = draw.textbbox(
    (0, 0),
    vs_text,
    font=font_vs
)

vs_width = vs_box[2] - vs_box[0]

vs_x = WIDTH // 2 - vs_width // 2
vs_y = HEIGHT // 2 - 140

draw.text(
    (vs_x, vs_y),
    vs_text,
    font=font_vs,
    fill="white",
    stroke_width=10,
    stroke_fill="black"
)

frames.append(np.array(base))
```

clips = [
ImageClip(frame).set_duration(1 / FPS)
for frame in frames
]

video = concatenate_videoclips(
clips,
method="compose"
)

video_path = "battle.mp4"

video.write_videofile(
video_path,
fps=FPS,
codec="libx264",
audio=False,
preset="ultrafast",
threads=2
)

with open(video_path, "rb") as f:
requests.post(
f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
data={
"chat_id": CHAT_ID
},
files={
"video": f
}
)

print("VIDEO SENT")
