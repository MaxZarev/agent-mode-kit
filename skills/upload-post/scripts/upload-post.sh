#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

: "${API_KEY:?API_KEY is not set — copy scripts/.env.example to scripts/.env and fill it in}"
: "${BASE_URL:=https://api.upload-post.com/api}"

AUTH_HEADER="Authorization: Apikey $API_KEY"

usage() {
  cat <<'USAGE'
Usage: upload-post.sh <action> [options]

Actions:
  text        Publish a text post
  photos      Publish a photo post
  videos      Publish a video post
  status      Check post status
  history     View upload history
  schedule    View scheduled posts
  cancel      Cancel a scheduled post
  analytics   Get analytics
  media       Get recent posts from profile
  queue-settings   View queue settings
  queue-update     Update queue settings

Options (vary by action):
  --user <username>           Profile username (default: from $DEFAULT_USER or "default")
  --platform <name>           Platform name, can be repeated (default: threads)
  --title <text>              Post text / caption
  --scheduled_date <iso8601>  Schedule date (ISO-8601 UTC)
  --link_url <url>            URL for link preview
  --first_comment <text>      Auto-reply comment
  --photo <path>              Photo file path, can be repeated
  --video <path>              Video file path
  --request_id <id>           Request ID for status check
  --job_id <id>               Job ID for cancel
  --page <n>                  Page number for history (default: 1)
  --limit <n>                 Limit for history (default: 10)
  --add_to_queue              Add to queue instead of immediate publish
  --facebook_page_id <id>     Facebook page ID
  --subreddit <name>          Reddit subreddit
  --pinterest_board_id <id>   Pinterest board ID
  --queue_json <json>         JSON body for queue settings update
USAGE
  exit 1
}

[[ $# -lt 1 ]] && usage

ACTION="$1"
shift

# Defaults
USER="${DEFAULT_USER:-default}"
PLATFORMS=()
TITLE=""
SCHEDULED_DATE=""
LINK_URL=""
FIRST_COMMENT=""
PHOTOS=()
VIDEO=""
REQUEST_ID=""
JOB_ID=""
PAGE="1"
LIMIT="10"
ADD_TO_QUEUE=""
FACEBOOK_PAGE_ID=""
SUBREDDIT=""
PINTEREST_BOARD_ID=""
QUEUE_JSON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) USER="$2"; shift 2 ;;
    --platform) PLATFORMS+=("$2"); shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --scheduled_date) SCHEDULED_DATE="$2"; shift 2 ;;
    --link_url) LINK_URL="$2"; shift 2 ;;
    --first_comment) FIRST_COMMENT="$2"; shift 2 ;;
    --photo) PHOTOS+=("$2"); shift 2 ;;
    --video) VIDEO="$2"; shift 2 ;;
    --request_id) REQUEST_ID="$2"; shift 2 ;;
    --job_id) JOB_ID="$2"; shift 2 ;;
    --page) PAGE="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --add_to_queue) ADD_TO_QUEUE="true"; shift ;;
    --facebook_page_id) FACEBOOK_PAGE_ID="$2"; shift 2 ;;
    --subreddit) SUBREDDIT="$2"; shift 2 ;;
    --pinterest_board_id) PINTEREST_BOARD_ID="$2"; shift 2 ;;
    --queue_json) QUEUE_JSON="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# Default platform
[[ ${#PLATFORMS[@]} -eq 0 ]] && PLATFORMS=("threads")

# Build platform flags for curl
build_platform_flags() {
  local flags=()
  for p in "${PLATFORMS[@]}"; do
    flags+=(-F "platform[]=$p")
  done
  echo "${flags[@]}"
}

case "$ACTION" in
  text)
    [[ -z "$TITLE" ]] && { echo "Error: --title is required for text posts"; exit 1; }
    CMD=(curl -s -X POST "$BASE_URL/upload_text" -H "$AUTH_HEADER" -F "user=$USER" -F "title=$TITLE")
    for p in "${PLATFORMS[@]}"; do CMD+=(-F "platform[]=$p"); done
    [[ -n "$SCHEDULED_DATE" ]] && CMD+=(-F "scheduled_date=$SCHEDULED_DATE")
    [[ -n "$LINK_URL" ]] && CMD+=(-F "link_url=$LINK_URL")
    [[ -n "$FIRST_COMMENT" ]] && CMD+=(-F "first_comment=$FIRST_COMMENT")
    [[ -n "$ADD_TO_QUEUE" ]] && CMD+=(-F "add_to_queue=true")
    [[ -n "$FACEBOOK_PAGE_ID" ]] && CMD+=(-F "facebook_page_id=$FACEBOOK_PAGE_ID")
    [[ -n "$SUBREDDIT" ]] && CMD+=(-F "subreddit=$SUBREDDIT")
    [[ -n "$PINTEREST_BOARD_ID" ]] && CMD+=(-F "pinterest_board_id=$PINTEREST_BOARD_ID")
    "${CMD[@]}"
    ;;

  photos)
    [[ -z "$TITLE" ]] && { echo "Error: --title is required for photo posts"; exit 1; }
    [[ ${#PHOTOS[@]} -eq 0 ]] && { echo "Error: at least one --photo is required"; exit 1; }
    CMD=(curl -s -X POST "$BASE_URL/upload_photos" -H "$AUTH_HEADER" -F "user=$USER" -F "title=$TITLE")
    for p in "${PLATFORMS[@]}"; do CMD+=(-F "platform[]=$p"); done
    for ph in "${PHOTOS[@]}"; do CMD+=(-F "photos[]=@$ph"); done
    [[ -n "$SCHEDULED_DATE" ]] && CMD+=(-F "scheduled_date=$SCHEDULED_DATE")
    [[ -n "$FIRST_COMMENT" ]] && CMD+=(-F "first_comment=$FIRST_COMMENT")
    [[ -n "$ADD_TO_QUEUE" ]] && CMD+=(-F "add_to_queue=true")
    [[ -n "$FACEBOOK_PAGE_ID" ]] && CMD+=(-F "facebook_page_id=$FACEBOOK_PAGE_ID")
    [[ -n "$SUBREDDIT" ]] && CMD+=(-F "subreddit=$SUBREDDIT")
    [[ -n "$PINTEREST_BOARD_ID" ]] && CMD+=(-F "pinterest_board_id=$PINTEREST_BOARD_ID")
    "${CMD[@]}"
    ;;

  videos)
    [[ -z "$TITLE" ]] && { echo "Error: --title is required for video posts"; exit 1; }
    [[ -z "$VIDEO" ]] && { echo "Error: --video is required"; exit 1; }
    CMD=(curl -s -X POST "$BASE_URL/upload_videos" -H "$AUTH_HEADER" -F "user=$USER" -F "title=$TITLE" -F "video_file=@$VIDEO")
    for p in "${PLATFORMS[@]}"; do CMD+=(-F "platform[]=$p"); done
    [[ -n "$SCHEDULED_DATE" ]] && CMD+=(-F "scheduled_date=$SCHEDULED_DATE")
    [[ -n "$FIRST_COMMENT" ]] && CMD+=(-F "first_comment=$FIRST_COMMENT")
    [[ -n "$ADD_TO_QUEUE" ]] && CMD+=(-F "add_to_queue=true")
    [[ -n "$FACEBOOK_PAGE_ID" ]] && CMD+=(-F "facebook_page_id=$FACEBOOK_PAGE_ID")
    [[ -n "$SUBREDDIT" ]] && CMD+=(-F "subreddit=$SUBREDDIT")
    [[ -n "$PINTEREST_BOARD_ID" ]] && CMD+=(-F "pinterest_board_id=$PINTEREST_BOARD_ID")
    "${CMD[@]}"
    ;;

  status)
    [[ -z "$REQUEST_ID" ]] && { echo "Error: --request_id is required"; exit 1; }
    curl -s "$BASE_URL/uploadposts/status?request_id=$REQUEST_ID" -H "$AUTH_HEADER"
    ;;

  history)
    curl -s "$BASE_URL/uploadposts/history?page=$PAGE&limit=$LIMIT" -H "$AUTH_HEADER"
    ;;

  schedule)
    curl -s "$BASE_URL/uploadposts/schedule" -H "$AUTH_HEADER"
    ;;

  cancel)
    [[ -z "$JOB_ID" ]] && { echo "Error: --job_id is required"; exit 1; }
    curl -s -X DELETE "$BASE_URL/uploadposts/schedule/$JOB_ID" -H "$AUTH_HEADER"
    ;;

  analytics)
    PLATFORM_CSV=$(IFS=,; echo "${PLATFORMS[*]}")
    curl -s "$BASE_URL/analytics/$USER?platforms=$PLATFORM_CSV" -H "$AUTH_HEADER"
    ;;

  media)
    curl -s "$BASE_URL/uploadposts/media?platform=${PLATFORMS[0]}&user=$USER" -H "$AUTH_HEADER"
    ;;

  queue-settings)
    curl -s "$BASE_URL/uploadposts/queue/settings" -H "$AUTH_HEADER"
    ;;

  queue-update)
    [[ -z "$QUEUE_JSON" ]] && { echo "Error: --queue_json is required"; exit 1; }
    curl -s -X POST "$BASE_URL/uploadposts/queue/settings" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      -d "$QUEUE_JSON"
    ;;

  *)
    echo "Unknown action: $ACTION"
    usage
    ;;
esac
