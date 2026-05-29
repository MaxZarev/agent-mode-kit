---
name: generate-image
description: "Generate an image (illustrations, YouTube thumbnails, lesson covers, social previews, hero shots, mockups). Configurable quality/size/format. Triggers: 'generate/draw/create/make an image', 'нарисуй / сгенерируй / сделай картинку / обложку / иллюстрацию', 'thumbnail для YouTube', 'обложка урока', 'превью для поста'. Supports reference images via --ref for style match. Don't use for: editing existing photo files in place, screenshots, OCR, or generating diagrams from data (use a charting tool)."
argument-hint: <prompt> [filename.png] [16:9|1:1|9:16|...] [--quality low|medium|high|auto] [--format png|jpeg|webp] [--size WxH] [--retries N] [--ref ref1.png ref2.jpg ...]
disable-model-invocation: false
allowed-tools: Bash
---

Generate an image based on this request: $ARGUMENTS

Current directory: !`pwd`

## Steps

1. Parse `$ARGUMENTS`:
   - Main text = image prompt
   - If a filename like `foo.png` is present — use it as output
   - If an aspect ratio like `16:9` is present — pass it to the script
   - If reference images are provided after `--ref` — pass their paths
   - Quality / format / size — pass through if user specified, otherwise let defaults apply
   - Otherwise: generate filename from prompt in snake_case, save to current directory

2. Run the generator (all flags optional and order-independent):
```bash
python3 ~/.claude/skills/generate-image/generate.py "PROMPT" "OUTPUT_FILE" \
  [16:9] \
  [--quality low|medium|high|auto] \
  [--format png|jpeg|webp] \
  [--size WIDTHxHEIGHT] \
  [--ref REF1.png REF2.jpg]
```

3. On success — show the saved path and ask if the user wants to embed it into the HTML presentation.

4. On error — if codex is missing, prompt the user to install Codex CLI and run `codex login`. If generation timed out, retry once.

## Quality / size / format — when to override

Defaults: `--quality medium` (sufficient for thumbnails, social images, drafts), format derived from output extension, size derived from aspect ratio (when one of `1:1`/`16:9`/`9:16`).

Override when:

| Need | Flag |
|---|---|
| Fastest + cheapest draft, OK if details are rough | `--quality low` |
| Highest fidelity for hero shots, marketing, print | `--quality high` |
| YouTube thumbnail / web hero — guarantee ≤ 2 MB | `--format jpeg` (output to `.jpg` does the same) |
| Custom resolution for gpt-image-2 (arbitrary W×H, multiples of 16, aspect 1:3 → 3:1) | `--size 1280x720` etc. |

Approximate cost / latency tiers (per OpenAI's `gpt-image-2` rates, 16:9):

| Quality | Output tokens (≈) | Relative cost | Latency |
|---|---|---|---|
| low | ~400 | 1× | ~10-30s |
| medium | ~1600 | ~4× low | ~30-60s |
| high | ~6200 | ~15× low | ~60-120s |

`auto` lets the model pick — usually behaves like high. Specify a level explicitly to keep usage predictable.

## Notes

- Backed by `codex exec` + the stable `image_generation` feature (gpt-image-2). Billed via the user's ChatGPT subscription (no `OPENAI_API_KEY` / `OPENROUTER_API_KEY` required).
- `codex` must be installed and authenticated (`codex login` once).
- Aspect ratio mapping (`1:1 → 1024x1024`, `16:9 → 1536x1024`, `9:16 → 1024x1536`) is honoured exactly. Other ratios are forwarded as natural language — Codex tries to match but framing is best-effort.
- gpt-image-2 supports arbitrary sizes if both dims are multiples of 16 and the ratio is between 1:3 and 3:1 — use `--size 1280x720` for YouTube-native thumbnails.
- Codex saves the raw output under `$CODEX_HOME/generated_images/<session>/ig_*.png`; the script copies the freshest file (newer than the run's start time) to the requested output path.
- If the requested output extension differs from what Codex produced (almost always `.png`), the script converts via `sips` on macOS; otherwise it falls back to writing the original extension and prints a warning.
- Hard timeout in the script is 300s. low/medium almost never hit it; high+complex prompts occasionally do — the script **auto-retries once by default** on timeout, rate-limit (HTTP 429), or empty-output. Tune with `--retries N` (default 1, max attempts = N+1) and `--retry-cooldown SECONDS` (default 10). Auth / bad-arg failures never retry — those need a human fix (e.g. `codex login`).

## Aspect ratios

`1:1` (default), `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `4:5`, `5:4`, `21:9`, `1:4`, `4:1`, `1:8`, `8:1`

Only `1:1`, `16:9`, `9:16` map to native gpt-image-1/2 sizes. The rest are passed as natural language — accuracy varies.
