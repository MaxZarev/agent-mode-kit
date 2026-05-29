---
name: deepgram-transcribe
description: Transcribe audio or video files using the Deepgram cloud API (nova-3 model) with optional speaker diarization. Use this skill whenever the user wants cloud-based transcription, speaker separation/diarization, needs specific output formats (srt, vtt, json, markdown), or asks for higher accuracy than local models. Triggers on: "transcribe with deepgram", "transcribe with speaker breakdown", "make subtitles", "transcribe with diarization", "who said what", file paths dropped with a request to transcribe, or any mention of Deepgram. ALWAYS use this skill instead of the local transcribe skill when the user wants speaker labels or multiple output formats.
allowed-tools: Bash, Read
---

Transcribe audio/video using Deepgram nova-3 (cloud API). Supports speaker diarization and 8 output formats.

## Prerequisites

1. **Deepgram API key.** Sign up at https://console.deepgram.com/ (free $200 credit). Copy `.env.example` to `.env` in this skill directory and fill in `DEEPGRAM_API_KEY`.
2. **Python venv with deps.** First-time setup:

```bash
SKILL_DIR="$(dirname "$(readlink -f ~/.claude/skills/deepgram-transcribe/SKILL.md 2>/dev/null || echo ~/.claude/skills/deepgram-transcribe/SKILL.md)")"
cd "$SKILL_DIR"
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

3. **ffmpeg** on PATH (needed for video files): `brew install ffmpeg` / `apt install ffmpeg`.

## Script & venv location

Both ship next to this `SKILL.md`. Substitute the right base path depending on install scope:

- User scope: `~/.claude/skills/deepgram-transcribe/`
- Project scope: `<project>/.claude/skills/deepgram-transcribe/`

**Important — always invoke with the venv-python**, not system `python3`. Running with system `python3` fails with `ModuleNotFoundError: No module named 'dotenv'`.

The script auto-loads `.env` from the directory it lives in (via `python-dotenv`), so once `.env` is filled in there's nothing else to configure.

## Output formats

| Flag | Result |
|---|---|
| `txt` | Plain text |
| `txt-speaker` | Speaker 1: ... (with merged utterances) |
| `txt-time` | [MM:SS] text |
| `txt-full` | [MM:SS] Speaker 1: text |
| `srt` | SRT subtitles |
| `vtt` | WebVTT subtitles |
| `md` | Markdown with metadata |
| `json` | Raw JSON from Deepgram |
| `-A` | All formats at once |

## Workflow

### 1. Identify the file and intent

- The file can be any audio/video format (mp3, mp4, mkv, wav, m4a, mov, etc.)
- Video is automatically converted via ffmpeg — just pass the path
- If the path contains spaces — wrap it in quotes

### 2. Choose format and mode

**Default** (just "transcribe"):
- Format: `txt` — plain text
- No diarization

**If speakers are needed** ("who said what", "break down by speakers", "with diarization"):
- Flag: `--diarize`
- Format: `txt-speaker` (merged utterances by speaker)

**If subtitles are needed**:
- `--format srt` or `--format vtt`

**If everything at once is needed**:
- `-A` (`--all-formats`)

### 3. Run the script

```bash
~/.claude/skills/deepgram-transcribe/venv/bin/python3 \
  ~/.claude/skills/deepgram-transcribe/deepgram_transcribe.py \
  "<path to file>" \
  [--diarize] \
  [--format txt|txt-speaker|txt-time|txt-full|srt|vtt|md|json] \
  [--output-dir <directory>] \
  [--language ru|en|multi]
```

By default, the result is saved next to the source file. Use `--output-dir` if you need to save to a different location.

### 4. Example commands

```bash
PY=~/.claude/skills/deepgram-transcribe/venv/bin/python3
SCRIPT=~/.claude/skills/deepgram-transcribe/deepgram_transcribe.py

# Simple transcription
$PY $SCRIPT "recording.mp3"

# With speaker breakdown
$PY $SCRIPT "meeting.mp4" --diarize --format txt-speaker

# SRT subtitles
$PY $SCRIPT "video.mp4" --format srt --output-dir ~/Desktop/

# All formats at once
$PY $SCRIPT "lecture.mp4" -A --output-dir ./results/

# Multiple formats
$PY $SCRIPT "call.mp3" --diarize --format txt-speaker srt

# Mixed language (Russian + English)
$PY $SCRIPT "mixed.mp3" --language multi --diarize
```

### 5. Report the result

- Indicate where the file was saved
- Show the first 10-15 lines of the result so the user can verify quality
- If something looks off (one speaker instead of several, fragments) — suggest trying `--language multi` or a different format

## Languages

- `ru` — Russian (default)
- `en` — English
- `multi` — auto-detect, suitable for mixed speech (ru+en)

## Additional parameters

- `--model nova-3` — default model, best available
- `--keyterms "term1,term2"` — help recognize specific words (names, terminology)
