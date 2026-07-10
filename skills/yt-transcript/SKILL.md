---
name: yt-transcript
description: >
  Get a transcript or summary of a YouTube video WITHOUT downloading it — the
  video is processed server-side by Gemini API (works even when yt-dlp is
  blocked by YouTube bot-checks or a VPN/datacenter IP). Use whenever the user
  wants the text/content/transcript/summary of a YouTube video: "сделай
  транскрипт видео", "о чём это видео", "конспект ролика", "расшифруй ютуб",
  "transcribe this YouTube video", "what does this video say", or when a
  YouTube URL needs to be ingested into a wiki/knowledge base as text. Prefer
  this over yt2mp3+transcription when the goal is text, not an audio file.
allowed-tools: Bash, Read
---

Transcribe or summarize a YouTube video via Gemini API. Google's servers fetch
and process the video — the local network/IP is never a factor, so this works
behind VPNs and on IPs where YouTube blocks yt-dlp ("Sign in to confirm you're
not a bot").

## Script

The script `yt_transcript.py` ships next to this `SKILL.md`. Substitute the
right base path for your install scope:

- User scope: `~/.claude/skills/yt-transcript/yt_transcript.py`
- Project scope: `<project>/.claude/skills/yt-transcript/yt_transcript.py`

```
python3 <skill-dir>/yt_transcript.py <url> [options]
```

No dependencies (stdlib only). API key: `GEMINI_API_KEY` in `.env` next to the
script — copy `.env.example` to `.env` and fill it in (never read the real
`.env`; if the key is missing the script says so — the key comes from
https://aistudio.google.com/apikey, free tier is enough).

## Options

| Flag | Meaning |
|---|---|
| (none) | verbatim transcript with `[MM:SS]` timecodes → stdout |
| `--out file.md` | save to file instead of stdout |
| `--mode summary` | detailed summary instead of verbatim transcript |
| `--prompt "..."` | custom prompt (e.g. "list all tools mentioned with timestamps") |
| `--model <id>` | override model (default `gemini-3.5-flash`, free tier) |

## Workflow

1. Take the YouTube URL (watch/youtu.be/shorts all work; video must be public).
2. Run the script with `--out` into a scratch/temp file; long videos take a
   while — for videos over ~20 minutes run in background.
3. Read the output file and use it. Tell the user it is a machine
   transcription: wording may be slightly off, on-screen text appears as
   `[на экране: ...]` inserts.

## Limits and fallbacks

- Free tier: up to 8 hours of YouTube video per day; HTTP 429 means the daily
  quota or rate limit is hit — tell the user, do not retry in a loop.
- Transcript language follows the video; the default prompt asks for the
  original language. Russian videos come back in Russian.
- If Gemini cannot access the video (private/unlisted/region-locked), fall
  back to the `yt2mp3` skill (download audio) + `deepgram-transcribe` skill —
  that path needs a non-blocked IP or cookies.
- Default behavior not enough (different output format, chunking a very long
  video, another API parameter)? Read the script first — it is short and
  self-contained: `yt_transcript.py` next to this `SKILL.md`.

## Related skills — do not confuse

- `yt2mp3` — downloads audio as MP3 (use when the user wants the file).
- `deepgram-transcribe` — transcribes local audio/video files, with speaker
  diarization (use for files on disk, Zoom recordings, higher accuracy needs).
- `youtube` — manages the user's own YouTube channel (upload, thumbnails).
