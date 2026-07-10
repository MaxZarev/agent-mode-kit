#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$DIR/.env" ] && set -a && . "$DIR/.env" && set +a
: "${TELEGRAM_BOT_TOKEN:?missing in .env}"
: "${TELEGRAM_CHAT_ID:?missing in .env}"
curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
  --data-urlencode "text=${1:-Task complete}" >/dev/null
