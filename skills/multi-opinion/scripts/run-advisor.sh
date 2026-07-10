#!/usr/bin/env bash
# Run one external advisor CLI with a fixed timeout and failure isolation.
#
# Usage:
#   run-advisor.sh <advisor-name> --cwd <dir> [--stdin <file>] -- <command> [args...]
#
# No environment variables are read. The working directory is always
# /tmp/multi-opinion and the per-advisor timeout is always 900 seconds.
# Results are written to <advisor>.out / .status / .meta inside the working
# directory. The wrapper always exits 0 so one failed advisor does not cancel
# the others.

set -euo pipefail

usage() {
  echo "Usage: run-advisor.sh <advisor-name> --cwd <dir> [--stdin <file>] -- <command> [args...]" >&2
  exit 2
}

[ "$#" -ge 1 ] || usage
ADVISOR_NAME="$1"
shift

ADVISOR_CWD=""
STDIN_FILE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cwd) ADVISOR_CWD="${2:-}"; shift 2 ;;
    --stdin) STDIN_FILE="${2:-}"; shift 2 ;;
    --) shift; break ;;
    *) echo "Unknown argument: $1" >&2; usage ;;
  esac
done

if [ "$#" -eq 0 ]; then
  echo "Missing advisor command" >&2
  exit 2
fi

WORKDIR="/tmp/multi-opinion"
TIMEOUT_SECONDS=900

mkdir -p "$WORKDIR"

PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  printf 'no_python\n' > "$WORKDIR/$ADVISOR_NAME.status"
  printf 'python3/python not found on PATH; run this advisor CLI directly without the wrapper.\n' \
    > "$WORKDIR/$ADVISOR_NAME.out"
  echo "$ADVISOR_NAME: no_python — call the CLI directly (no timeout wrapper available)" >&2
  exit 0
fi

"$PYTHON_BIN" - "$TIMEOUT_SECONDS" "$WORKDIR" "$ADVISOR_NAME" "$ADVISOR_CWD" "$STDIN_FILE" "$@" <<'PY'
import os
import re
import shlex
import signal
import subprocess
import sys
import time

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TOOL_LINE_RE = re.compile(r"^\s*[⚙✗✓→⏺│┃%]")
TOOL_NOISE = ("permission requested", "auto-rejecting", "mcp error",
              "tool call", "running tool")

def looks_like_tool_log_only(text):
    """True when rc-0 output is only CLI tool-log lines with no prose answer."""
    prose_chars = 0
    for line in ANSI_RE.sub("", text).splitlines():
        s = line.strip()
        if not s or TOOL_LINE_RE.match(s):
            continue
        low = s.lower()
        if any(marker in low for marker in TOOL_NOISE):
            continue
        prose_chars += len(s)
    return prose_chars < 200

timeout_seconds = int(sys.argv[1])
workdir = sys.argv[2]
advisor_name = sys.argv[3]
advisor_cwd = sys.argv[4]
stdin_file = sys.argv[5]
command = sys.argv[6:]

out_path = os.path.join(workdir, f"{advisor_name}.out")
status_path = os.path.join(workdir, f"{advisor_name}.status")
meta_path = os.path.join(workdir, f"{advisor_name}.meta")

started = time.time()
status = "ok"
returncode = 0
output = ""

def write_result():
    elapsed = int(time.time() - started)

    with open(out_path, "w", encoding="utf-8", errors="replace") as handle:
        handle.write(output)

    with open(status_path, "w", encoding="utf-8") as handle:
        handle.write(status + "\n")

    with open(meta_path, "w", encoding="utf-8") as handle:
        handle.write(f"advisor={advisor_name}\n")
        handle.write(f"status={status}\n")
        handle.write(f"returncode={returncode}\n")
        handle.write(f"elapsed_seconds={elapsed}\n")
        handle.write(f"timeout_seconds={timeout_seconds}\n")
        if stdin_file:
            handle.write(f"stdin_file={stdin_file}\n")
        if advisor_cwd:
            handle.write(f"cwd={advisor_cwd}\n")
        handle.write("command=" + shlex.join(command) + "\n")

    print(f"{advisor_name}: {status} ({elapsed}s), output: {out_path}")

try:
    stdin_data = None
    if stdin_file:
        if not os.path.isfile(stdin_file):
            returncode = 126
            status = "stdin_missing"
            output = f"stdin file does not exist: {stdin_file}\n"
            write_result()
            sys.exit(0)
        else:
            with open(stdin_file, "r", encoding="utf-8", errors="replace") as handle:
                stdin_data = handle.read()

    # start_new_session=True puts the child in its own process group, so on
    # timeout we can kill the whole descendant tree (advisor CLIs spawn helpers
    # that would otherwise survive and keep burning model budget).
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=advisor_cwd or None,
        start_new_session=True,
    )
    try:
        output, _ = proc.communicate(input=stdin_data, timeout=timeout_seconds)
        returncode = proc.returncode
        if returncode != 0:
            status = f"exit_{returncode}"
        elif not output.strip():
            # Exited cleanly (rc 0) but produced no text: the advisor ended
            # without writing an answer (e.g. stuck on a flaky tool call).
            # Don't let it pass as "ok" — the orchestrator must notice it.
            status = "empty_output"
        elif looks_like_tool_log_only(output):
            # Exited cleanly WITH text, but it is only tool-call/permission log
            # noise and no actual prose answer (e.g. sandbox auto-rejects or a
            # stuck web tool). Flag it so the orchestrator retries once or skips.
            status = "no_answer"
    except subprocess.TimeoutExpired:
        status = "timeout"
        returncode = 124
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        try:
            output, _ = proc.communicate(timeout=10)
        except Exception:
            output = output or ""
except FileNotFoundError as exc:
    returncode = 127
    status = "not_found"
    output = str(exc)
except Exception as exc:  # PermissionError, OSError, ... — never crash the wrapper
    returncode = 126
    status = "spawn_error"
    output = f"{type(exc).__name__}: {exc}\n"

write_result()
sys.exit(0)
PY
