#!/usr/bin/env bash
# Run Codex (OpenAI GPT-5.5) via `codex exec` as a headless worker, so the main
# Claude session can delegate implementation work or get a second opinion.
#
# Usage:
#   codex-run.sh implement --cwd <dir> [--model <m>] [--effort <e>] -- "<task prompt>"
#   codex-run.sh review    --cwd <dir> [--model <m>] [--effort <e>] -- "<review prompt>"
#
# Modes:
#   implement  -> sandbox workspace-write (Codex can read AND edit files in cwd).
#                 The orchestrator MUST review Codex's diff afterwards.
#   review     -> sandbox read-only (inspects, never edits).
#
# Output: Codex's final message is printed to stdout (the event stream is
# discarded). Codex with gpt-5.5 + xhigh reasoning can take 3-10+ minutes —
# the orchestrator should run this in the background.
#
# Auth lives in Codex's own config (set once by running `codex` and logging in).

set -euo pipefail

for d in "$HOME"/.nvm/versions/node/*/bin; do [ -d "$d" ] && PATH="$d:$PATH"; done
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"

MODEL="gpt-5.5"
EFFORT="xhigh"

[ "$#" -ge 1 ] || { echo "usage: codex-run.sh <implement|review> --cwd <dir> -- <prompt>" >&2; exit 2; }
MODE="$1"; shift

CWD="."
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cwd)    CWD="${2:-.}";        shift 2 ;;
    --model)  MODEL="${2:-$MODEL}"; shift 2 ;;
    --effort) EFFORT="${2:-$EFFORT}"; shift 2 ;;
    --)       shift; break ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

PROMPT="${*:-}"
[ -n "$PROMPT" ] || { echo "missing prompt (put it after --)" >&2; exit 2; }

command -v codex >/dev/null 2>&1 || { echo "codex not found on PATH" >&2; exit 127; }

case "$MODE" in
  implement) SANDBOX="workspace-write" ;;
  review)    SANDBOX="read-only" ;;
  *) echo "mode must be 'implement' or 'review'" >&2; exit 2 ;;
esac

[ -d "$CWD" ] || { echo "cwd does not exist: $CWD" >&2; exit 2; }

OUT="$(mktemp -t codex-run.XXXXXX.md)"
trap 'rm -f "$OUT"' EXIT

# Prompt via stdin avoids shell-quoting issues; -o writes only the final
# message; the event stream on stdout is discarded, stderr stays for errors.
printf '%s' "$PROMPT" | codex exec \
  --skip-git-repo-check \
  -C "$CWD" \
  -m "$MODEL" \
  -c "model_reasoning_effort=\"$EFFORT\"" \
  -s "$SANDBOX" \
  -o "$OUT" \
  - > /dev/null

# Codex streams its reasoning / tool calls to stderr (visible for debugging and,
# in implement mode, to show the steps + applied patch). The clean final answer
# is written to $OUT via -o; print it after a clear delimiter so the orchestrator
# can locate it amid the event stream.
if [ -s "$OUT" ]; then
  printf '\n===== CODEX FINAL MESSAGE =====\n'
  cat "$OUT"
else
  echo "(codex produced no final message — check stderr / auth)" >&2
  exit 1
fi
