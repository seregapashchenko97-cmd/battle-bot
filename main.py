from PIL import Image
import requests

def test():
response = requests.get("https://picsum.photos/500")
img = Image.open(requests.get("https://picsum.photos/500", stream=True).raw)
img.save("test.png")

print("WORKING")
