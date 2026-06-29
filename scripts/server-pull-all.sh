#!/bin/bash
# Run on VPS: update downloader + optional givsharifi-website clone.
set -euo pipefail

DOWNLOADER="${HOME}/youtube-instagram-downloader"
WEBSITE="${HOME}/givsharifi-website"

echo "=== youtube-instagram-downloader ==="
if [[ -d "$DOWNLOADER/.git" ]]; then
  cd "$DOWNLOADER"
  git pull --ff-only origin main
  docker compose build
  docker compose up -d
  docker compose ps
else
  echo "Clone first: git clone https://github.com/alecasgari/youtube-instagram-downloader.git $DOWNLOADER"
fi

echo ""
echo "=== givsharifi-website (reference / n8n workflows) ==="
if [[ -d "$WEBSITE/.git" ]]; then
  cd "$WEBSITE"
  git pull --ff-only origin main
  echo "Updated at $(git log -1 --oneline)"
else
  echo "Optional clone:"
  echo "  git clone https://github.com/alecasgari/givsharifi-website.git $WEBSITE"
fi

echo ""
echo "=== health ==="
docker exec giv-ytdlp python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9876/health').read().decode())" 2>/dev/null || echo "giv-ytdlp not running"
