#!/usr/bin/env bash
# Assemble a lightweight "problem pack" for multi-opinion. Several models are
# asked to PROPOSE solution approaches for an open problem (NOT to review an
# existing artifact). The orchestrator supplies the problem context.
#
# Usage:
#   build-opinion-pack.sh <context_root> <problem_file>
#
#   context_root  Directory the advisors may inspect read-only (the repo/area
#                 the problem lives in). Use "-" if there is no codebase.
#   problem_file  A file the orchestrator wrote describing: what we are solving,
#                 what has been tried, what works / what does not, constraints,
#                 and which files are most relevant.
#
# Writes /tmp/multi-opinion/{context_root.txt,problem.md,prompt.md}.

set -euo pipefail

WORKDIR="/tmp/multi-opinion"
CONTEXT_ROOT="${1:-}"
PROBLEM_FILE="${2:-}"

if [ -z "$CONTEXT_ROOT" ] || [ -z "$PROBLEM_FILE" ] || [ ! -f "$PROBLEM_FILE" ]; then
  echo "usage: build-opinion-pack.sh <context_root|-> <problem_file>" >&2
  echo "  problem_file must exist" >&2
  exit 2
fi

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

# Resolve the directory advisors may inspect.
NO_CODE=0
if [ "$CONTEXT_ROOT" = "-" ]; then
  # No codebase: hand advisors a dedicated dir, never the orchestrator's cwd, so
  # they cannot read unrelated local files.
  NO_CODE=1
  CONTEXT_ROOT="$WORKDIR/no-code"
  mkdir -p "$CONTEXT_ROOT"
elif [ ! -d "$CONTEXT_ROOT" ]; then
  echo "context_root is not a directory: $CONTEXT_ROOT (use '-' if there is no codebase)" >&2
  exit 2
fi
CONTEXT_ROOT="$(cd "$CONTEXT_ROOT" && pwd -P)"
printf '%s\n' "$CONTEXT_ROOT" > "$WORKDIR/context_root.txt"

# Raw problem text (used as supplemental stdin for CLIs that cannot read files).
cp "$PROBLEM_FILE" "$WORKDIR/problem.md"

# Build the advisor prompt: preamble + the problem context.
{
  cat <<'PREAMBLE'
You are ONE of several independent senior engineers asked to PROPOSE how to
solve a problem. This is NOT a code review — do not hunt for unrelated bugs.
Your job is to propose concrete solution approaches for the problem below.

Ground rules:
- The relevant code is in the directory you were started in. Inspect it
  READ-ONLY to make your proposal specific and correct. DO NOT edit any file,
  run mutating commands, or install anything.
- Reference real files / functions from THIS codebase, not generic advice.
- If an approach was already tried and failed, say whether it failed for a
  fixable reason or is a genuine dead end.

Produce:
1. One or two concrete approaches. For each: the core idea, why it fits this
   codebase, the key implementation steps, trade-offs, risks, and how you would
   verify it works.
2. If you see a clearly best option, say which and why. If you are unsure, say so.
3. Keep it tight — no filler, no restating the problem back.

--- PROBLEM CONTEXT (what we are solving, what has been tried, what works / what does not) ---
PREAMBLE
  cat "$WORKDIR/problem.md"
} > "$WORKDIR/prompt.md"

# Best-effort secret redaction in anything we generated.
if command -v perl >/dev/null 2>&1; then
  perl -i -pe '
    s/\bsk-[A-Za-z0-9_-]{12,}\b/[REDACTED]/g;             # OpenAI (incl. sk-proj-, sk-svcacct-)
    s/\b(?:AKIA|ASIA)[0-9A-Z]{12,}\b/[REDACTED]/g;        # AWS access keys (incl. temp ASIA)
    s/\bgh[posu]_[A-Za-z0-9]{20,}\b/[REDACTED]/g;         # GitHub PAT / oauth / user / server
    s/\bgithub_pat_[A-Za-z0-9_]{20,}\b/[REDACTED]/g;      # GitHub fine-grained PAT
    s/\bgl(?:pat|pt)-[A-Za-z0-9_-]{10,}\b/[REDACTED]/g;   # GitLab tokens
    s/\bxox[abprs]-[A-Za-z0-9-]{10,}\b/[REDACTED]/g;      # Slack tokens
    s/\bey[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/[REDACTED]/g;  # JWT
    s/((?i:authorization)\s*:\s*bearer\s+)\S+/${1}[REDACTED]/gi;
    s/((?i:api[_-]?key|secret|token|password)\s*[:=]\s*)\S+/${1}[REDACTED]/g;
  ' "$WORKDIR/prompt.md" "$WORKDIR/problem.md" 2>/dev/null || true
fi

# No-code mode: also place copies of the (redacted) problem/prompt INSIDE the
# context root. Sandboxed advisors (GLM via OpenCode) hard-reject reads outside
# their granted dir; without these copies GLM burns its turn on auto-rejected
# attempts to open problem.md/prompt.md one level up and exits with no answer.
if [ "$NO_CODE" = "1" ]; then
  cp "$WORKDIR/problem.md" "$WORKDIR/prompt.md" "$CONTEXT_ROOT/"
fi

echo "multi-opinion pack ready:"
echo "  context_root: $CONTEXT_ROOT"
echo "  prompt:       $WORKDIR/prompt.md"
echo "  problem:      $WORKDIR/problem.md"
