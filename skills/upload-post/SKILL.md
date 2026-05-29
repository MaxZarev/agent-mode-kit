---
name: "upload-post"
description: "Publish posts to social media (Threads, X, LinkedIn, Instagram, TikTok, Facebook, Bluesky, Pinterest, Reddit) via Upload-Post API. Use this skill whenever the user wants to publish, schedule, or post content to Threads or any social network through Upload-Post. Triggers on: 'опубликуй в тредс', 'запости в threads', 'publish to threads', 'отправь пост', 'запланируй пост в тредс', mentions of Upload-Post, or any request to post to social media platforms supported by Upload-Post. Also use when the user wants to check post status, view upload history, analytics, or manage scheduled posts. ALWAYS use this skill instead of manual API calls to Upload-Post."
---

# Upload-Post — Social Media Publishing

Publish text, photos, and videos to 10+ social networks through a single API.

## Setup

1. Sign up at https://app.upload-post.com/ and connect the social profiles you want to publish to.
2. Copy `scripts/.env.example` to `scripts/.env` and fill in:
   - `API_KEY` — from Upload-Post dashboard → Settings → API
   - `DEFAULT_USER` — the profile username you connected in the UI (override per-call with `--user`)
   - `BASE_URL` — keep the default unless Upload-Post changes it
3. Make the script executable: `chmod +x scripts/upload-post.sh`

All API calls use the `scripts/upload-post.sh` wrapper. Substitute the path below for your install scope:

- User scope: `~/.claude/skills/upload-post/scripts/upload-post.sh`
- Project scope: `<project>/.claude/skills/upload-post/scripts/upload-post.sh`

In the examples below the variable `$UP` stands for whichever full path applies.

## Quick Reference

### Publish text post

```bash
$UP text --title "Your post text here"
```

Optional parameters:
- `--scheduled_date <ISO-8601 UTC>` — e.g. `2026-03-20T15:00:00Z` for scheduled posts
- `--link_url <url>` — URL for link preview card
- `--first_comment <text>` — auto-reply after publishing
- `--platform <name>` — target platform (default: threads), can be repeated for multi-platform
- `--user <username>` — profile username (default: from `DEFAULT_USER` in `.env`)
- `--add_to_queue` — add to queue instead of immediate publish

### Publish photo post

```bash
$UP photos --title "Caption text" --photo /path/to/image.jpg
```

Multiple photos: repeat `--photo` for each file (max 10 for Threads).

Threads photo limits: JPEG/PNG, max 8MB, 320-1440px width, max 10 images per post.

### Publish video post

```bash
$UP videos --title "Caption text" --video /path/to/video.mp4
```

### Schedule a post

Add `--scheduled_date` to any publish command:

```bash
$UP text --title "Scheduled post" --scheduled_date "2026-03-20T15:00:00Z"
```

Max 365 days ahead. Use ISO-8601 format.

### Check post status

```bash
$UP status --request_id <REQUEST_ID>
```

### View upload history

```bash
$UP history --page 1 --limit 10
```

### View scheduled posts

```bash
$UP schedule
```

### Cancel scheduled post

```bash
$UP cancel --job_id <JOB_ID>
```

### Get analytics

```bash
$UP analytics
```

### Get recent posts from profile

```bash
$UP media
```

## Multi-Platform Publishing

To publish to multiple platforms at once, repeat `--platform`:

```bash
$UP text \
  --title "Cross-platform post" \
  --platform threads \
  --platform x \
  --platform linkedin
```

Platform-specific notes:
- **Facebook**: requires additional `--facebook_page_id <ID>`
- **Reddit**: requires `--subreddit <name>`
- **Pinterest**: requires `--pinterest_board_id <ID>`
- **X/Twitter**: long text auto-splits into thread (280 char limit per tweet)
- **Threads**: 500 char limit per post, max 10 images

## Queue System

Auto-schedule posts to next available slot:

```bash
$UP text --title "Queued post" --add_to_queue
```

Cannot combine with `--scheduled_date`.

Manage queue settings:

```bash
# View settings
$UP queue-settings

# Update settings
$UP queue-update \
  --queue_json '{"timezone": "Europe/Moscow", "slots": [{"hour": 10, "minute": 0}, {"hour": 14, "minute": 0}, {"hour": 19, "minute": 0}], "days_of_week": [0,1,2,3,4,5,6]}'
```

## Rate Limits

Free plan: 10 uploads per month. Counter resets monthly.

Check remaining usage in any upload response:
```json
{
  "usage": {
    "count": 1,
    "limit": 10,
    "last_reset": "2026-03-16T12:43:13"
  }
}
```

## Workflow

1. User says what to post and where
2. Compose the post text (respect platform character limits)
3. Confirm with user before publishing
4. Execute the script call
5. Return the post URL from the response

Always confirm post content with the user before publishing. Never auto-publish without approval.
