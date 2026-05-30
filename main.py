import subprocess

cmd = [
    "ffmpeg",
    "-f", "lavfi",
    "-i", "color=c=red:s=540x960:d=3",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "test.mp4",
    "-y"
]

result = subprocess.run(cmd, capture_output=True, text=True)

print("RETURN CODE:", result.returncode)
print(result.stderr)
