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

scale1 = max(WIDTH / img1.width, HALF / img1.height)
new_w1 = int(img1.width * scale1)
new_h1 = int(img1.height * scale1)

img1 = img1.resize((new_w1, new_h1))

left1 = (new_w1 - WIDTH) // 2
top1 = (new_h1 - HALF) // 2

img1 = img1.crop((
left1,
top1,
left1 + WIDTH,
top1 + HALF
))

scale2 = max(WIDTH / img2.width, HALF / img2.height)
new_w2 = int(img2.width * scale2)
new_h2 = int(img2.height * scale2)

img2 = img2.resize((new_w2, new_h2))

left2 = (new_w2 - WIDTH) // 2
top2 = (new_h2 - HALF) // 2

img2 = img2.crop((
left2,
top2,
left2 + WIDTH,
top2 + HALF
))

canvas = Image.new("RGB", (WIDTH, HEIGHT))

canvas.paste(img1, (0, 0))
canvas.paste(img2, (0, HALF))

draw = ImageDraw.Draw(canvas)

font_big = ImageFont.load_default()
font_vs = ImageFont.load_default()
font_timer = ImageFont.load_default()

draw.line(
[(0, HALF), (WIDTH, HALF)],
fill=(255,255,255),
width=8
)

draw.text(
(360, 90),
"5",
anchor="mm",
font=font_timer,
fill=(255,0,0),
stroke_width=3,
stroke_fill=(0,0,0)
)

draw.text(
(360, 500),
TOP_TEXT,
anchor="mm",
font=font_big,
fill=(255,255,255),
stroke_width=2,
stroke_fill=(0,0,0)
)

draw.text(
(360, 780),
BOTTOM_TEXT,
anchor="mm",
font=font_big,
fill=(255,255,255),
stroke_width=2,
stroke_fill=(0,0,0)
)

draw.text(
(360, 640),
"VS",
anchor="mm",
font=font_vs,
fill=(255,215,0),
stroke_width=2,
stroke_fill=(0,0,0)
)

canvas = canvas.resize((1080, 1920))

canvas.save("battle.png")

clip = ImageClip("battle.png").set_duration(3)

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
data={"chat_id": CHAT_ID},
files={"video": video}
)

video.close()

print("DONE")
