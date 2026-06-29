#!/bin/bash
# Run on the VPS inside the clone directory (e.g. /home/alecadmin/youtube-instagram-downloader).
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f .env ]]; then
  echo "ERROR: .env already exists. Edit it manually or remove first." >&2
  exit 1
fi

: "${R2_ACCOUNT_ID:?Set R2_ACCOUNT_ID}"
: "${R2_ACCESS_KEY_ID:?Set R2_ACCESS_KEY_ID}"
: "${R2_SECRET_ACCESS_KEY:?Set R2_SECRET_ACCESS_KEY}"

UI_PASSWORD="${GIV_YTDLP_UI_PASSWORD:-$(openssl rand -hex 16)}"

cat > .env <<EOF
GIV_YTDLP_HOST=0.0.0.0
GIV_YTDLP_PORT=9876
GIV_YTDLP_TOKEN=
GIV_YTDLP_UI_PASSWORD=${UI_PASSWORD}
GIV_YTDLP_DATA_DIR=/data

R2_ACCOUNT_ID=${R2_ACCOUNT_ID}
R2_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
R2_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
R2_BUCKET=givsharifi-videos
R2_PREFIX=library
R2_PUBLIC_BASE_URL=https://media.givsharifi.com
EOF

chmod 600 .env
echo "OK: .env created (chmod 600)."
echo "UI password is in .env as GIV_YTDLP_UI_PASSWORD"
echo "Next: docker compose build && docker compose up -d"
