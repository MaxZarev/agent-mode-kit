#!/usr/bin/env bash
# Run GLM 5.2 (Z.ai GLM Coding Plan subscription) via OpenCode as a headless
# worker, so the main Claude session can delegate work or get a second opinion.
#
# Usage:
#   glm-run.sh implement --cwd <dir> [--model <id>] -- "<task prompt>"
#   glm-run.sh review    --cwd <dir> [--model <id>] -- "<review prompt>"
#
# Modes:
#   implement  -> OpenCode 'build' agent (can read AND edit files / run tools).
#                 The orchestrator MUST review GLM's diff afterwards.
#   review     -> OpenCode 'plan' agent (read-only: inspects, never edits).
#
# Output: GLM's response is streamed to stdout. Exit code is OpenCode's.
# The model's own auth lives in OpenCode's auth.json (`opencode auth login`).
# For the research MCP servers this script also sources a git-ignored .env next
# to it (ZAI_API_KEY) and exports it; no secret is hardcoded in any file.

set -euo pipefail

# --- resolve this script's real directory (it is usually invoked through a
#     symlink at ~/.claude/skills/glm/...; we want the canonical hub location so
#     the companion .env and opencode.json are always found). ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"

# --- load the Z.ai key used by the research MCP servers (web search / reader /
#     zread). The key lives ONLY in a git-ignored .env next to this script; it is
#     never hardcoded in opencode.json or the skill. `set -a` exports it so
#     OpenCode can read it via {env:ZAI_API_KEY}. Missing .env is fine — the MCP
#     servers just won't authenticate (research tools unavailable). ---
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a; . "$SCRIPT_DIR/.env"; set +a
fi

# --- point OpenCode at the skill-local config that registers the Z.ai research
#     MCP servers. Scoped via OPENCODE_CONFIG so these tools load ONLY for the
#     GLM worker, not for the user's other OpenCode usage. ---
if [ -f "$SCRIPT_DIR/opencode.json" ]; then
  export OPENCODE_CONFIG="$SCRIPT_DIR/opencode.json"
fi

# --- make `opencode` reachable even when PATH is minimal (Claude Code / cron) ---
# nvm installs node bins per-version; add every version dir so a node upgrade
# does not silently break this wrapper.
for d in "$HOME"/.nvm/versions/node/*/bin; do
  [ -d "$d" ] && PATH="$d:$PATH"
done
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$PATH"

MODEL="zai-coding-plan/glm-5.2"

[ "$#" -ge 1 ] || { echo "usage: glm-run.sh <implement|review> --cwd <dir> -- <prompt>" >&2; exit 2; }
MODE="$1"; shift

CWD="."
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cwd)   CWD="${2:-.}";      shift 2 ;;
    --model) MODEL="${2:-$MODEL}"; shift 2 ;;
    --)      shift; break ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

PROMPT="${*:-}"
[ -n "$PROMPT" ] || { echo "missing prompt (put it after --)" >&2; exit 2; }

command -v opencode >/dev/null 2>&1 || { echo "opencode not found on PATH" >&2; exit 127; }

case "$MODE" in
  implement) AGENT="build" ;;
  review)    AGENT="plan"  ;;
  *) echo "mode must be 'implement' or 'review'" >&2; exit 2 ;;
esac

[ -d "$CWD" ] || { echo "cwd does not exist: $CWD" >&2; exit 2; }

# Use OpenCode's explicit --dir (it resolves the project root from this, not
# from the OS cwd / $PWD), so this works no matter how the wrapper is invoked.
exec opencode run --dir "$CWD" --agent "$AGENT" --model "$MODEL" "$PROMPT"
