---
name: yt2mp3
description: Download a YouTube video and convert it to MP3 using the bundled yt2mp3 script. Use this skill whenever the user wants to download audio from YouTube, convert a YouTube link to MP3, save a YouTube video as audio, or says things like "download from YouTube", "download video", "convert YouTube to MP3", "save audio from YouTube". Trigger even if the user just pastes a YouTube URL without explanation.
allowed-tools: Bash
---

Download YouTube audio as MP3 using the bundled `yt2mp3` script.

## Prerequisites

The script needs `yt-dlp` and `ffmpeg`:

```bash
# macOS
brew install yt-dlp ffmpeg

# Linux (apt)
sudo apt install yt-dlp ffmpeg
```

## Script location

The script ships next to this `SKILL.md`. The exact path depends on where the skill is installed:

- User scope: `~/.claude/skills/yt2mp3/yt2mp3`
- Project scope: `<project>/.claude/skills/yt2mp3/yt2mp3`

Make sure it is executable: `chmod +x <path>/yt2mp3`.

Default output: `~/Downloads/Audio from YouTube/`

## If YouTube says "Sign in to confirm you're not a bot"

YouTube increasingly blocks plain `yt-dlp` downloads. The script has two optional hooks (both off until you set them up):

1. **PO token provider** — clone [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) and put its `server/` directory at `~/.config/yt2mp3/bgutil-pot-provider/server` (or point `YT2MP3_POT_SERVER_HOME` at it). Also install the matching yt-dlp plugin per that repo's README.
2. **Cookies** — export cookies of a **dedicated throwaway Google account** (never your main one) from a private browser session into `~/.config/yt2mp3/cookies.txt` (or set `YT2MP3_COOKIES_FILE`). After exporting, don't reopen that browser session — YouTube rotates the tokens and the file goes stale.

The script also self-updates `yt-dlp` once a week (YouTube changes its defenses often).

## Workflow

### 1. Get the URL

Extract the YouTube URL from the user's message. Supported formats:
- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`
- `https://youtube.com/shorts/...`

### 2. Run the script in the background

```bash
~/.claude/skills/yt2mp3/yt2mp3 "<URL>" [output-dir]
```

- If the user didn't specify an output folder, omit the second argument (defaults to `~/Downloads/Audio from YouTube/`)
- Always run with `run_in_background: true` — downloads can take several minutes

### 3. Inform the user

Tell the user the download started and that you'll notify them when it's done.

### 4. When the task completes

Check the last few lines of output to confirm success, then report:
- File name
- File size
- Save location
