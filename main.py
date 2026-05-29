from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import random
from moviepy.editor import ImageClip

WIDTH = 720
HEIGHT = 1280
HALF = HEIGHT // 2

BOT_TOKEN = "8330007893"
CHAT_ID = "476718796"

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

def load_image(url, target_h):
response = requests.get(url)

img = Image.open(BytesIO(response.content)).convert("RGB")

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

top_img = load_image(
battle["top"],
HALF
)

bottom_img = load_image(
battle["bottom"],
HALF
)

canvas = Image.new(
"RGB",
(WIDTH, HEIGHT)
)

canvas.paste(top_img, (0, 0))
canvas.paste(bottom_img, (0, HALF))

draw = ImageDraw.Draw(canvas)

try:
font_big = ImageFont.truetype(
"DejaVuSans-Bold.ttf",
170
)

font_vs = ImageFont.truetype(
    "DejaVuSans-Bold.ttf",
    340
)

timer_font = ImageFont.truetype(
    "DejaVuSans-Bold.ttf",
    220
)

except:
font_big = ImageFont.load_default()
font_vs = ImageFont.load_default()
timer_font = ImageFont.load_default()

draw.line(
[(0, HALF), (WIDTH, HALF)],
fill=(255,255,255),
width=10
)

draw.rectangle(
[(40, HALF - 280), (680, HALF - 120)],
fill=(0,0,0)
)

draw.text(
(WIDTH // 2, HALF - 200),
battle["top_text"],
anchor="mm",
font=font_big,
fill=(255,255,255),
stroke_width=4,
stroke_fill=(0,0,0)
)

draw.rectangle(
[(40, HALF + 120), (680, HALF + 280)],
fill=(0,0,0)
)

draw.text(
(WIDTH // 2, HALF + 200),
battle["bottom_text"],
anchor="mm",
font=font_big,
fill=(255,255,255),
stroke_width=4,
stroke_fill=(0,0,0)
)

draw.rectangle(
[(210, HALF - 130), (510, HALF + 130)],
fill=(0,0,0)
)

draw.text(
(WIDTH // 2, HALF),
"VS",
anchor="mm",
font=font_vs,
fill=(255,215,0),
stroke_width=6,
stroke_fill=(0,0,0)
)

draw.rectangle(
[(240, 40), (480, 220)],
fill=(0,0,0)
)

draw.text(
(WIDTH // 2, 130),
"5",
anchor="mm",
font=timer_font,
fill=(255,50,50),
stroke_width=6,
stroke_fill=(0,0,0)
)

image_path = "battle.png"

canvas.save(
image_path,
quality=95
)

clip = ImageClip(image_path).set_duration(3)

video_path = "battle.mp4"

clip.write_videofile(
video_path,
fps=20,
codec="libx264",
preset="ultrafast",
audio=False,
threads=1,
logger=None
)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"

with open(video_path, "rb") as video_file:
requests.post(
url,
data={
"chat_id": CHAT_ID
},
files={
"video": video_file
}
)

print("DONE")
