#!/usr/bin/env python3
"""
Image generator backed by Codex CLI's built-in `image_generation` tool.

No API key required — uses the user's ChatGPT subscription via `codex login`.

Usage:
    python3 generate.py "prompt" output.png [16:9] \\
        [--quality low|medium|high|auto] \\
        [--format png|jpeg|webp] \\
        [--size WIDTHxHEIGHT] \\
        [--ref ref1.png ref2.jpg ...]

Aspect ratio is optional and order-independent. Reference images, if given,
are forwarded to Codex via `codex exec -i ...` and the prompt is augmented to
treat them as visual references / edit sources.

Quality / format / size are forwarded inline in the prompt — Codex's image
tool (gpt-image-2) reads them and passes to its underlying tool call.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


ASPECT_RATIOS = [
    "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
    "4:5", "5:4", "21:9", "1:4", "4:1", "1:8", "8:1",
]

# Aspect ratios with a directly-supported size on gpt-image-1/2.
# Other ratios fall through to free-form prompt-only guidance.
ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
}

IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}

EXT_TO_FORMAT = {
    ".png": "png",
    ".webp": "webp",
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
}

QUALITY_CHOICES = ("low", "medium", "high", "auto")
FORMAT_CHOICES = ("png", "jpeg", "webp")
SIZE_RE = re.compile(r"^(\d+)x(\d+)$")

# Generation can take 60–120s on the OpenAI side. low quality returns in
# 10-30s; high may run >60s. Hard cap to bound runaway requests.
CODEX_TIMEOUT_SEC = 300


def codex_generated_dir() -> Path:
    home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return Path(home) / "generated_images"


def find_new_image(after_ts: float) -> Path | None:
    base = codex_generated_dir()
    if not base.exists():
        return None
    candidates: list[Path] = []
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
            try:
                if p.stat().st_mtime > after_ts:
                    candidates.append(p)
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def convert_with_sips(src: Path, dst: Path) -> bool:
    fmt = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}.get(dst.suffix.lower())
    if not fmt or not shutil.which("sips"):
        return False
    result = subprocess.run(
        ["sips", "-s", "format", fmt, str(src), "--out", str(dst)],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and dst.exists()


def parse_extras(extras: list[str]) -> tuple[str | None, list[str]]:
    """Pull aspect ratio + `--ref <paths...>` out of free-form extras.

    Recognised flags (`--quality`, `--format`, `--size`) are already consumed
    by argparse, so they will not appear here. Anything else that isn't an
    aspect ratio or `--ref` is silently ignored for backwards compatibility.
    """
    aspect_ratio: str | None = None
    ref_images: list[str] = []
    i = 0
    while i < len(extras):
        a = extras[i]
        if a == "--ref":
            i += 1
            while i < len(extras) and not extras[i].startswith("--") and extras[i] not in ASPECT_RATIOS:
                ref_images.append(extras[i])
                i += 1
            continue
        if a in ASPECT_RATIOS:
            aspect_ratio = a
        i += 1
    return aspect_ratio, ref_images


def resolve_size(aspect_ratio: str | None, explicit_size: str | None) -> str | None:
    """Pick the size string to pass to image_generation.

    Priority: explicit --size > aspect-ratio mapping > None (let model decide).
    """
    if explicit_size:
        return explicit_size
    if aspect_ratio and aspect_ratio in ASPECT_TO_SIZE:
        return ASPECT_TO_SIZE[aspect_ratio]
    return None


def resolve_format(explicit_format: str | None, output_path: Path) -> str | None:
    """Pick output_format for image_generation.

    Priority: explicit --format > derive from output extension > None.
    """
    if explicit_format:
        return explicit_format
    return EXT_TO_FORMAT.get(output_path.suffix.lower())


def build_prompt(
    user_prompt: str,
    aspect_ratio: str | None,
    has_refs: bool,
    quality: str,
    output_format: str | None,
    size: str | None,
) -> str:
    """Build the Codex prompt with explicit image_generation parameters.

    Codex CLI's image_generation tool reads quality/size/format from the
    natural-language prompt — there are no flags on `codex exec` itself.
    """
    tool_args: list[str] = [f"quality='{quality}'"]
    if size:
        tool_args.append(f"size='{size}'")
    if output_format:
        tool_args.append(f"output_format='{output_format}'")

    parts = [
        "Use your built-in `image_generation` tool to create the image described below.",
        f"Call the tool with: {', '.join(tool_args)}.",
        "Do not run any shell commands and do not try to save or move the file yourself.",
        "Just call the tool once and stop — the file will be picked up from your generated_images directory.",
        "",
        f"Description: {user_prompt}",
    ]
    if aspect_ratio and not size:
        # Only mention aspect ratio in plain language if we couldn't map it
        # to an explicit size — otherwise size already encodes it.
        parts.append(f"Aspect ratio: {aspect_ratio}")
    if has_refs:
        parts.append("The attached image(s) are visual references — match their style/subject or edit them as described.")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate an image via Codex CLI (ChatGPT subscription).",
        usage=(
            'generate.py "prompt" output.png [16:9] '
            '[--quality low|medium|high|auto] [--format png|jpeg|webp] '
            '[--size WxH] [--ref ref1.png ref2.jpg ...]'
        ),
    )
    parser.add_argument("prompt", help="Image description")
    parser.add_argument(
        "output",
        help="Output file path (extension determines default format; .jpg/.webp converted via sips on macOS if Codex returned a different format)",
    )
    parser.add_argument(
        "--quality",
        choices=QUALITY_CHOICES,
        default="medium",
        help=(
            "Rendering quality. low ≈ 4× faster + 15× cheaper than high; "
            "medium is the default — adequate for thumbnails, social images, "
            "drafts. Use high only when fine detail matters. (default: medium)"
        ),
    )
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        dest="image_format",
        default=None,
        help=(
            "output_format for image_generation. If omitted, derived from the "
            "output filename extension (.png → png, .jpg → jpeg, .webp → webp). "
            "jpeg is recommended for photo-style outputs and YouTube thumbnails "
            "(≤2 MB limit)."
        ),
    )
    parser.add_argument(
        "--size",
        default=None,
        help=(
            "Explicit size as WIDTHxHEIGHT (e.g. 1536x1024). Overrides the "
            "aspect-ratio-derived size. Native gpt-image-2 supports arbitrary "
            "values where both dims are multiples of 16 and aspect is between "
            "1:3 and 3:1."
        ),
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help=(
            "Auto-retry count on retryable failures (timeout, no image "
            "returned, rate limit). Total attempts = 1 + retries. "
            "Non-retryable failures (auth, invalid args) never retry. "
            "(default: 1)"
        ),
    )
    parser.add_argument(
        "--retry-cooldown",
        type=int,
        default=10,
        help="Seconds to wait between retry attempts (default: 10)",
    )
    parser.add_argument(
        "--ref",
        nargs="+",
        dest="ref_images",
        default=[],
        metavar="IMG",
        help=(
            "Reference image path(s) for style/subject matching, e.g. "
            "--ref style.png subject.jpg. Tip: put any aspect ratio BEFORE "
            "--ref so it is not swallowed as a path."
        ),
    )
    parser.add_argument(
        "extras",
        nargs="*",
        help="Optional aspect ratio (e.g. 16:9). A bare `--ref <paths...>` is also accepted here for back-compat.",
    )
    args = parser.parse_args()

    if args.retries < 0:
        print(f"ERROR: --retries must be >= 0, got {args.retries}", file=sys.stderr)
        return 2

    if args.size and not SIZE_RE.match(args.size):
        print(f"ERROR: --size must be WIDTHxHEIGHT (e.g. 1536x1024), got {args.size!r}", file=sys.stderr)
        return 2

    if shutil.which("codex") is None:
        print("ERROR: `codex` CLI not found in PATH. Install: https://github.com/openai/codex", file=sys.stderr)
        return 1

    # `--ref` is now a real flag (args.ref_images); parse_extras still pulls the
    # aspect ratio out of the positional extras (and tolerates a legacy bare
    # `--ref` left there). Merge both sources.
    aspect_ratio, extra_refs = parse_extras(args.extras)
    ref_images = list(args.ref_images) + extra_refs
    # nargs="+" is greedy: `--ref a.png 16:9` swallows the aspect ratio as a path.
    # Recover any aspect token that landed in refs, and drop it from the ref list.
    if aspect_ratio is None:
        for tok in ref_images:
            if tok in ASPECT_RATIOS:
                aspect_ratio = tok
                break
    ref_images = [r for r in ref_images if r not in ASPECT_RATIOS]

    for ref in ref_images:
        if not Path(ref).is_file():
            print(f"ERROR: reference image not found: {ref}", file=sys.stderr)
            return 1

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    size = resolve_size(aspect_ratio, args.size)
    output_format = resolve_format(args.image_format, output_path)

    full_prompt = build_prompt(
        args.prompt,
        aspect_ratio,
        bool(ref_images),
        quality=args.quality,
        output_format=output_format,
        size=size,
    )

    cmd = [
        "codex", "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    # NOTE: codex >=0.136 makes `-i/--image` variadic (`<FILE>...`), so a trailing
    # prompt placed after `-i <ref>` gets swallowed as another image file and codex
    # then reports "No prompt provided via stdin". Put the prompt BEFORE the refs.
    cmd.append(full_prompt)
    for ref in ref_images:
        cmd += ["-i", ref]

    short_prompt = args.prompt if len(args.prompt) <= 80 else args.prompt[:77] + "..."
    print(f"Prompt: {short_prompt}")
    print(f"Quality: {args.quality}")
    print(f"Size: {size or '(model default)'}")
    print(f"Format: {output_format or '(model default)'}")
    print(f"Aspect ratio: {aspect_ratio or '(none — using size only)' if size else aspect_ratio or '1:1 (default)'}")
    for r in ref_images:
        print(f"Reference: {r}")
    print(f"Output: {output_path}")
    print(f"Running codex (low ≈ 30-60s · medium ≈ 60-90s · high ≈ 90-180s, hard cap {CODEX_TIMEOUT_SEC}s)...")

    src: Path | None = None
    total_attempts = args.retries + 1
    for attempt in range(1, total_attempts + 1):
        if attempt > 1:
            print(
                f"Retrying after {args.retry_cooldown}s cooldown "
                f"(attempt {attempt}/{total_attempts})...",
                file=sys.stderr,
            )
            time.sleep(args.retry_cooldown)
        elif total_attempts > 1:
            print(f"Attempt {attempt}/{total_attempts}")

        start_ts = time.time() - 2  # small margin against clock skew / fs mtime rounding

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CODEX_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            print(f"WARN: codex exec timed out after {CODEX_TIMEOUT_SEC}s", file=sys.stderr)
            if attempt < total_attempts:
                continue
            print("ERROR: out of retries after repeated timeouts", file=sys.stderr)
            return 1

        if proc.returncode != 0:
            stderr_tail = proc.stderr or ""
            is_rate_limit = any(
                marker in stderr_tail.lower()
                for marker in ("rate limit", "rate_limit", "429", "too many requests")
            )
            print(f"WARN: codex exec exited with code {proc.returncode}", file=sys.stderr)
            if stderr_tail:
                print("--- stderr (tail) ---", file=sys.stderr)
                print(stderr_tail[-2000:], file=sys.stderr)
            if proc.stdout:
                print("--- stdout (tail) ---", file=sys.stderr)
                print(proc.stdout[-2000:], file=sys.stderr)
            # Rate-limit-like exits are retryable; auth / bad-arg failures are not.
            if is_rate_limit and attempt < total_attempts:
                continue
            return proc.returncode

        src = find_new_image(start_ts)
        if src is None:
            print("WARN: no new image found in", codex_generated_dir(), file=sys.stderr)
            print("--- codex stdout (tail) ---", file=sys.stderr)
            print(proc.stdout[-1500:], file=sys.stderr)
            if attempt < total_attempts:
                continue
            print("ERROR: out of retries — codex never produced an image", file=sys.stderr)
            return 1

        # Success — exit retry loop.
        break

    assert src is not None  # guarded by the return paths above

    if src.suffix.lower() == output_path.suffix.lower():
        shutil.copy2(src, output_path)
    elif convert_with_sips(src, output_path):
        pass
    else:
        # Could not convert — keep source extension so file is still valid.
        fallback = output_path.with_suffix(src.suffix.lower())
        shutil.copy2(src, fallback)
        print(
            f"WARNING: requested {output_path.suffix} but Codex produced {src.suffix}; "
            f"saved as {fallback}",
            file=sys.stderr,
        )
        output_path = fallback

    size_kb = output_path.stat().st_size // 1024
    print(f"Saved: {output_path} ({size_kb} KB)")
    print(f"Source: {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
