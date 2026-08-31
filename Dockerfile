FROM python:3.12-slim-bookworm

# ffmpeg for merge; Deno + EJS for yt-dlp YouTube (2026+)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl unzip \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -U --pre "yt-dlp[default]"

COPY config.py download.py r2_upload.py server.py main.py cookies_store.py ./
COPY static ./static

ENV GIV_YTDLP_HOST=0.0.0.0 \
    GIV_YTDLP_PORT=9876 \
    GIV_YTDLP_DATA_DIR=/data

EXPOSE 9876

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9876/health')"

CMD ["python", "main.py"]
