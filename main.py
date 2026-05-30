from PIL import Image
from moviepy.editor import ImageClip

img = Image.new("RGB", (540, 960), (255, 0, 0))
img.save("test.png")

clip = ImageClip("test.png").set_duration(5)

clip.write_videofile(
    "test.mp4",
    fps=24,
    codec="libx264",
    audio=False,
    preset="ultrafast",
    logger=None
)

print("VIDEO OK")
