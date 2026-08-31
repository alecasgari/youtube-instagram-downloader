#!/bin/bash
# Run on the VPS after GitHub Actions rsync. Does not git pull (no GitHub login).
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose build
docker compose up -d --force-recreate
docker compose ps

for _ in $(seq 1 12); do
  if docker exec giv-ytdlp python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9876/health')" >/dev/null 2>&1; then
    docker exec giv-ytdlp python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9876/health').read().decode())"
    exit 0
  fi
  sleep 5
done

echo "giv-ytdlp health check failed" >&2
docker compose logs --tail 80 giv-ytdlp >&2
exit 1
