---
name: youtube
description: >
  Manage a YouTube channel via a CLI script: upload videos, update metadata,
  set thumbnails, schedule publishing, manage privacy, playlists,
  comments, analytics, search. Use this skill whenever the user
  wants to do anything with YouTube — upload a video, set a thumbnail, make
  public, schedule release, view stats, find videos, add to playlist,
  post a comment. Trigger even if the user just says "upload to YouTube",
  "set thumbnail", "make public", "schedule it"
  or names a video file and mentions YouTube.
---

## Tool

The CLI ships in `scripts/` next to this `SKILL.md`: `scripts/youtube` (zsh
wrapper, auto-creates a venv with deps on first run) + `scripts/youtube_core.py`.
Substitute the right base path for your install scope:

- User scope: `~/.claude/skills/youtube/scripts/youtube`
- Project scope: `<project>/.claude/skills/youtube/scripts/youtube`

In the examples below, `youtube` stands for that full path (or add the
`scripts/` dir to PATH / symlink it to `/usr/local/bin/youtube`).

Config: `~/.config/youtube-cli/` — OAuth token and channel ID are stored there.

## One-time setup

1. In [Google Cloud Console](https://console.cloud.google.com/) create a
   project, enable **YouTube Data API v3** (and **YouTube Analytics API** for
   the `analytics` command).
2. Create an OAuth client (Desktop app), download the JSON and save it as
   `~/.config/youtube-cli/credentials.json`.
3. First run opens the browser for authorization; the token lands in
   `~/.config/youtube-cli/token.json`.
4. Set your channel: `youtube channel set UC...` (your channel ID).

If credentials are missing, the script prints these steps itself.

## Commands

### Upload a video
```bash
youtube upload <file> --title "Title" --description "Description" --tags "tag1,tag2" --category 22 --privacy private
youtube upload <file> --title "Title" --schedule "2026-03-15T12:00:00Z"  # scheduled publishing
```
Default privacy is `private`. Category 22 = People & Blogs.

### Metadata
```bash
youtube update <video_id> --title "New title"
youtube update <video_id> --description "Text" --tags "tag1,tag2"
youtube thumbnail <video_id> <path to image>   # JPG/PNG, max 2 MB
youtube privacy <video_id> public|unlisted|private
youtube schedule <video_id> "2026-03-15T12:00:00Z"
```

### Listing
```bash
youtube list --limit 20          # recent channel videos
youtube list                     # default 20 videos
```

### Playlists
```bash
youtube playlist list
youtube playlist create "Title" --privacy public
youtube playlist add <playlist_id> <video_id>
youtube playlist remove <playlist_id> <video_id>
```

### Comments
```bash
youtube comment list <video_id> --limit 20
youtube comment post <video_id> "Text"
youtube comment reply <thread_id> "Text"
youtube comment delete <comment_id>
```

### Analytics
```bash
youtube analytics --id <video_id>              # single video stats
youtube analytics                              # entire channel
youtube analytics --start 2026-01-01 --daily  # daily breakdown
```

### Search
```bash
youtube search "query" --limit 10 --order relevance
youtube trending --region RU --limit 10
```

### Miscellaneous
```bash
youtube quota        # API quota info
youtube categories   # list categories with IDs
youtube delete <video_id>
```

## Practical Notes

**Thumbnail size:** YouTube accepts max 2 MB. If the file is larger — compress with Pillow (the venv lives next to the script after first run):
```bash
<skill-dir>/scripts/venv/bin/pip install pillow -q
<skill-dir>/scripts/venv/bin/python3 -c "
from PIL import Image
img = Image.open('input.jpg')
img.save('output.jpg', 'JPEG', quality=75, optimize=True)
"
```

**Thumbnail generation:** Use the `generate-image` skill to create a cover, then upload via `youtube thumbnail`. 16:9 aspect ratio is ideal for YouTube.

**Video status:** After upload, the video is processed on YouTube servers (several minutes for long videos). `uploadStatus: processed` = ready.

**Video ID:** Always visible in the URL `youtube.com/watch?v=VIDEO_ID` and in the output of `youtube list`.

**API quota:** 10,000 units/day. Video upload = 1,600 units (~6 uploads/day).

**Time for `--schedule`:** ISO 8601 UTC format: `2026-03-15T12:00:00Z`. When using `--schedule` in `upload`, privacy is automatically set to `private` until the scheduled time.

## Typical Publishing Workflow

1. Upload as private: `youtube upload video.mp4 --title "..." --privacy private`
2. Generate a cover with the `generate-image` skill in 16:9 format
3. Set the thumbnail: `youtube thumbnail VIDEO_ID cover.jpg`
4. Update description/tags: `youtube update VIDEO_ID --description "..." --tags "..."`
5. Schedule or make public: `youtube schedule VIDEO_ID "..."` or `youtube privacy VIDEO_ID public`
