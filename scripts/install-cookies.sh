#!/bin/bash
# Copy merged cookies into the running giv-ytdlp container (run on VPS).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COOKIES="$ROOT/cookies/cookies.txt"

if [[ ! -f "$COOKIES" ]]; then
  echo "ERROR: $COOKIES not found." >&2
  echo "On your laptop: python scripts/merge-cookies.py" >&2
  echo "Then copy to server:" >&2
  echo "  scp cookies/cookies.txt alecadmin@YOUR_SERVER:~/youtube-instagram-downloader/cookies/cookies.txt" >&2
  exit 1
fi

cd "$ROOT"

if ! docker compose ps --status running --services | grep -q '^giv-ytdlp$'; then
  echo "Starting giv-ytdlp..."
  docker compose up -d
  sleep 2
fi

echo "Installing cookies ($(wc -c < "$COOKIES") bytes)..."
docker cp "$COOKIES" giv-ytdlp:/data/cookies.txt
docker exec giv-ytdlp ls -la /data/cookies.txt
docker compose restart giv-ytdlp
sleep 3
docker exec giv-ytdlp python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9876/health').read().decode())"
echo "OK — cookies installed. Test YouTube with: bash verify-on-server.sh 'YOUTUBE_URL'"
