import requests
from io import BytesIO
from PIL import Image

response = requests.get("https://picsum.photos/1080/1920")

img = Image.open(BytesIO(response.content)).convert("RGB")

print(img.size)

img.save("test.jpg")

print("DONE")
