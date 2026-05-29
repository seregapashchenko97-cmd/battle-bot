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

img1 = img1.resize((720, 640))
img2 = img2.resize((720, 640))

canvas = Image.new("RGB", (WIDTH, HEIGHT))

canvas.paste(img1, (0, 0))
canvas.paste(img2, (0, HALF))

draw = ImageDraw.Draw(canvas)

font = ImageFont.load_default()

draw.rectangle(
[(0, HALF - 5), (720, HALF + 5)],
fill=(255,255,255)
)

draw.rectangle(
[(40, 420), (680, 560)],
fill=(0,0,0)
)

draw.text(
(360, 490),
TOP_TEXT,
anchor="mm",
font=font,
fill=(255,255,255)
)

draw.rectangle(
[(40, 720), (680, 860)],
fill=(0,0,0)
)

draw.text(
(360, 790),
BOTTOM_TEXT,
anchor="mm",
font=font,
fill=(255,255,255)
)

draw.rectangle(
[(250, 540), (470, 740)],
fill=(0,0,0)
)

draw.text(
(360, 640),
"VS",
anchor="mm",
font=font,
fill=(255,215,0)
)

draw.rectangle(
[(280, 40), (440, 180)],
fill=(0,0,0)
)

draw.text(
(360, 110),
"5",
anchor="mm",
font=font,
fill=(255,0,0)
)

canvas.save("battle.png")

clip = ImageClip("battle.png").set_duration(3)

clip.write_videofile(
"battle.mp4",
fps=20,
codec="libx264",
audio=False,
preset="ultrafast",
logger=None
)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"

with open("battle.mp4", "rb") as video:
requests.post(
url,
data={"chat_id": CHAT_ID},
files={"video": video}
)

print("DONE")
