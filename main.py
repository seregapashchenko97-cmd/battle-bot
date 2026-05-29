from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from moviepy.editor import ImageClip

WIDTH = 720
HEIGHT = 1280
HALF = HEIGHT // 2

BOT_TOKEN = "8330007893:AAGBWfwgoF3dxVJvBQTEADQnK-kCQRz40BE"
CHAT_ID = "476718796"

TOP_TEXT = "PRIVATE JET"
BOTTOM_TEXT = "LUXURY VILLA"

TOP_URL = "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=1800"
BOTTOM_URL = "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=1800"

response1 = requests.get(TOP_URL)
img1 = Image.open(BytesIO(response1.content)).convert("RGB")

response2 = requests.get(BOTTOM_URL)
img2 = Image.open(BytesIO(response2.content)).convert("RGB")

def crop_center(img, target_w, target_h):

```
scale = max(
    target_w / img.width,
    target_h / img.height
)

new_w = int(img.width * scale)
new_h = int(img.height * scale)

img = img.resize((new_w, new_h))

left = (new_w - target_w) // 2
top = (new_h - target_h) // 2

img = img.crop(
    (
        left,
        top,
        left + target_w,
        top + target_h
    )
)

return img
```

img1 = crop_center(img1, WIDTH, HALF)
img2 = crop_center(img2, WIDTH, HALF)

canvas = Image.new("RGB", (WIDTH, HEIGHT))

canvas.paste(img1, (0, 0))
canvas.paste(img2, (0, HALF))

draw = ImageDraw.Draw(canvas)

try:

```
font_big = ImageFont.truetype(
    "DejaVuSans-Bold.ttf",
    90
)

font_vs = ImageFont.truetype(
    "DejaVuSans-Bold.ttf",
    180
)

font_timer = ImageFont.truetype(
    "DejaVuSans-Bold.ttf",
    130
)
```

except:

```
font_big = ImageFont.load_default()
font_vs = ImageFont.load_default()
font_timer = ImageFont.load_default()
```

draw.line(
[(0, HALF), (WIDTH, HALF)],
fill=(255,255,255),
width=8
)

draw.rectangle(
[(120, 40), (600, 180)],
fill=(0,0,0)
)

draw.text(
(360, 110),
"5",
anchor="mm",
font=font_timer,
fill=(255,0,0),
stroke_width=3,
stroke_fill=(0,0,0)
)

draw.rectangle(
[(40, 430), (680, 560)],
fill=(0,0,0)
)

draw.text(
(360, 495),
TOP_TEXT,
anchor="mm",
font=font_big,
fill=(255,255,255),
stroke_width=3,
stroke_fill=(0,0,0)
)

draw.rectangle(
[(40, 720), (680, 850)],
fill=(0,0,0)
)

draw.text(
(360, 785),
BOTTOM_TEXT,
anchor="mm",
font=font_big,
fill=(255,255,255),
stroke_width=3,
stroke_fill=(0,0,0)
)

draw.rectangle(
[(180, 520), (540, 760)],
fill=(0,0,0)
)

draw.text(
(360, 640),
"VS",
anchor="mm",
font=font_vs,
fill=(255,215,0),
stroke_width=4,
stroke_fill=(0,0,0)
)

canvas.save("battle.png")

clip = ImageClip("battle.png").set_duration(3)

clip = clip.resize(
lambda t: 1 + 0.03 * t
)

clip.write_videofile(
"battle.mp4",
fps=24,
codec="libx264",
audio=False,
preset="ultrafast",
logger=None
)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"

video = open("battle.mp4", "rb")

requests.post(
url,
data={
"chat_id": CHAT_ID
},
files={
"video": video
}
)

video.close()

print("DONE")
