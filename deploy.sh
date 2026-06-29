#!/bin/bash
# Pull latest code and recreate container on the VPS.
set -euo pipefail
cd "$(dirname "$0")"
git pull --ff-only origin main
docker compose build
docker compose up -d --force-recreate
docker compose ps
docker exec giv-ytdlp python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9876/health').read().decode())"
