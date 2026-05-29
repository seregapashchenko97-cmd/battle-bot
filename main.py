from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from moviepy.editor import *
import random

WIDTH = 1080
HEIGHT = 1920
HALF = HEIGHT // 2

BOT_TOKEN = "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE"
CHAT_ID = "476718796"

TOP_TEXT = "PRIVATE JET"
BOTTOM_TEXT = "LUXURY VILLA"

TOP_URL = "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=1800"
BOTTOM_URL = "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1800"

WINNER = random.choice(["top", "bottom"])

def prepare_image(url, y_start):
response = requests.get(url)
img = Image.open(BytesIO(response.content)).convert("RGB")

```
scale = max(WIDTH / img.width, HALF / img.height)

new_w = int(img.width * scale)
new_h = int(img.height * scale)

img = img.resize((new_w, new_h))

left = (new_w - WIDTH) // 2
top = (new_h - HALF) // 2

img = img.crop((
    left,
    top,
    left + WIDTH,
    top + HALF
))

return img
```

top_img = prepare_image(TOP_URL, 0)
bottom_img = prepare_image(BOTTOM_URL, HALF)

font_big = ImageFont.truetype("Anton-Regular.ttf", 120)
font_vs = ImageFont.truetype("Anton-Regular.ttf", 90)
font_timer = ImageFont.truetype("Anton-Regular.ttf", 170)

frames = []

fps = 24
duration = 5

for i in range(duration * fps):

```
t = i / fps

canvas = Image.new("RGB", (WIDTH, HEIGHT))

zoom = 1 + (t * 0.04)

top_zoom = top_img.resize((
    int(WIDTH * zoom),
    int(HALF * zoom)
))

bottom_zoom = bottom_img.resize((
    int(WIDTH * zoom),
    int(HALF * zoom)
))

crop_x = (top_zoom.width - WIDTH) // 2
crop_y = (top_zoom.height - HALF) // 2

top_zoom = top_zoom.crop((
    crop_x,
    crop_y,
    crop_x + WIDTH,
    crop_y + HALF
))

bottom_zoom = bottom_zoom.crop((
    crop_x,
    crop_y,
    crop_x + WIDTH,
    crop_y + HALF
))

canvas.paste(top_zoom, (0, 0))
canvas.paste(bottom_zoom, (0, HALF))

draw = ImageDraw.Draw(canvas)

draw.line(
    [(0, HALF), (WIDTH, HALF)],
    fill=(255,255,255),
    width=8
)

countdown = str(max(1, 5 - int(t)))

timer_color = (255,0,0)

draw.text(
    (540, 120),
    countdown,
    anchor="mm",
    font=font_timer,
    fill=timer_color,
    stroke_width=8,
    stroke_fill=(0,0,0)
)

top_color = (255,255,255)
bottom_color = (255,255,255)

if t >= 4:
    if WINNER == "top":
        top_color = (0,255,120)
    else:
        bottom_color = (0,255,120)

draw.text(
    (540, 720),
    TOP_TEXT,
    anchor="mm",
    font=font_big,
    fill=top_color,
    stroke_width=8,
    stroke_fill=(0,0,0)
)

draw.text(
    (540, 1210),
    BOTTOM_TEXT,
    anchor="mm",
    font=font_big,
    fill=bottom_color,
    stroke_width=8,
    stroke_fill=(0,0,0)
)

vs_size = 90

if t >= 4:
    vs_size = 130

font_vs_dynamic = ImageFont.truetype(
    "Anton-Regular.ttf",
    vs_size
)

draw.text(
    (540, 960),
    "VS",
    anchor="mm",
    font=font_vs_dynamic,
    fill=(255,215,0),
    stroke_width=6,
    stroke_fill=(0,0,0)
)

if t >= 4:
    overlay = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        (0,255,100,45)
    )
    canvas = Image.alpha_composite(
        canvas.convert("RGBA"),
        overlay
    ).convert("RGB")

frame_path = f"frame_{i}.png"

canvas.save(frame_path)

frames.append(frame_path)
```

clips = []

for frame in frames:
clips.append(
ImageClip(frame).set_duration(1 / fps)
)

video = concatenate_videoclips(
clips,
method="compose"
)

video.write_videofile(
"battle.mp4",
fps=fps,
codec="libx264",
audio=False,
preset="ultrafast",
logger=None
)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"

video_file = open("battle.mp4", "rb")

requests.post(
url,
data={"chat_id": CHAT_ID},
files={"video": video_file}
)

video_file.close()

print("DONE")
