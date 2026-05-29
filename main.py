from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from moviepy.editor import ImageClip, concatenate_videoclips
import random

WIDTH = 1080
HEIGHT = 1920
HALF = HEIGHT // 2

BOT_TOKEN = "ТВОЙ_БОТ_ТОКЕН"
CHAT_ID = "ТВОЙ_CHAT_ID"

TOP_TEXT = "PRIVATE JET"
BOTTOM_TEXT = "LUXURY VILLA"

TOP_URL = "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=1800"
BOTTOM_URL = "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1800"

WINNER = random.choice(["top", "bottom"])

def prepare_image(url):
response = requests.get(url)

```
img = Image.open(BytesIO(response.content)).convert("RGB")

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

top_img = prepare_image(TOP_URL)
bottom_img = prepare_image(BOTTOM_URL)

font_big = ImageFont.truetype("Anton-Regular.ttf", 120)
font_vs = ImageFont.truetype("Anton-Regular.ttf", 90)
font_timer = ImageFont.truetype("Anton-Regular.ttf", 170)

clips = []

fps = 12

for second in [5,4,3,2,1]:

```
canvas = Image.new("RGB", (WIDTH, HEIGHT))

canvas.paste(top_img, (0, 0))
canvas.paste(bottom_img, (0, HALF))

draw = ImageDraw.Draw(canvas)

draw.line(
    [(0, HALF), (WIDTH, HALF)],
    fill=(255,255,255),
    width=8
)

top_color = (255,255,255)
bottom_color = (255,255,255)

if second == 1:
    if WINNER == "top":
        top_color = (0,255,120)
    else:
        bottom_color = (0,255,120)

draw.text(
    (540, 120),
    str(second),
    anchor="mm",
    font=font_timer,
    fill=(255,0,0),
    stroke_width=8,
    stroke_fill=(0,0,0)
)

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

draw.text(
    (540, 960),
    "VS",
    anchor="mm",
    font=font_vs,
    fill=(255,215,0),
    stroke_width=6,
    stroke_fill=(0,0,0)
)

frame_name = f"{second}.png"

canvas.save(frame_name)

clip = ImageClip(frame_name).set_duration(1)

clips.append(clip)
```

video = concatenate_videoclips(clips)

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
