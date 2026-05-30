from moviepy.editor import ColorClip

clip = ColorClip(
size=(1080, 1920),
color=(255, 0, 0),
duration=3
)

clip.write_videofile(
"test.mp4",
fps=30,
codec="libx264"
)

print("VIDEO CREATED")
