FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp as a binary (always latest, no pip dependency issues)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gameplay cache persists between restarts if you mount a volume
# On Railway: set GAMEPLAY_CACHE_DIR=/data/gameplay and add a volume at /data
RUN mkdir -p /tmp/gameplay_cache

CMD ["python", "main.py"]
