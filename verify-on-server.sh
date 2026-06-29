#!/bin/bash
# Run on VPS: bash verify-on-server.sh [youtube-or-instagram-url]
set -euo pipefail

URL="${1:-https://youtu.be/cuomkatlVtg}"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=== 1) Container ==="
docker compose ps

echo ""
echo "=== 2) cookies.txt ==="
if docker exec giv-ytdlp test -f /data/cookies.txt; then
  docker exec giv-ytdlp ls -la /data/cookies.txt
else
  echo "MISSING: /data/cookies.txt (YouTube will fail without it)"
fi

echo ""
echo "=== 3) Deno + yt-dlp ==="
docker exec giv-ytdlp deno --version
docker exec giv-ytdlp yt-dlp --version

echo ""
echo "=== 4) HTTP health ==="
docker exec giv-ytdlp python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9876/health').read().decode())"

echo ""
echo "=== 5) n8n API POST /download (no token, upload_r2=false) ==="
docker exec giv-ytdlp python -c "
import json, urllib.request
url = '''$URL'''
req = urllib.request.Request(
    'http://127.0.0.1:9876/download',
    data=json.dumps({'url': url, 'work_id': 'verify-n8n', 'upload_r2': False}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
resp = urllib.request.urlopen(req, timeout=600)
body = resp.read().decode()
print(body[:800])
data = json.loads(body)
assert data.get('ok'), data
print('OK: video_id =', data['video_id'])
"

echo ""
echo "=== DONE ==="
