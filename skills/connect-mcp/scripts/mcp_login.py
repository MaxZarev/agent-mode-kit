#!/usr/bin/env python3
"""
Browser OAuth sign-in for a Claude Code MCP server, WITHOUT an interactive shell.

Why this exists:
    `claude mcp login <name>` refuses to run unless its stdin is a real terminal
    (TTY) — it errors with "stdin isn't a terminal". Agents and the Bash tool do
    not provide a TTY, so the plain command fails. This wrapper allocates a
    pseudo-terminal so the login runs unattended: `claude` opens the browser
    itself, the user approves access, and the local callback finishes the flow.

What it does:
    - macOS / Linux: uses Python's built-in `pty` module (no dependencies).
    - Windows: uses `winpty` (ships with Git for Windows) if present. If there is
      no way to allocate a PTY, it prints a clear NO_PTY message plus the exact
      one-line command the user can run in a normal terminal instead.
    - Streams the login output so the caller can read progress.
    - Prints these easy-to-grep markers on their own lines:
        AUTH_URL: <url>   once the authorization link appears (relay it to the
                          user in case the browser did not open on its own)
        LOGIN_OK          on success (exit code 0)
        LOGIN_FAILED ...  on failure
        LOGIN_TIMEOUT     if the user did not finish in time
        NO_PTY            (Windows only) no PTY available; fallback printed

Usage:
    python3 mcp_login.py <server-name> [--timeout SECONDS] [--claude PATH]

Run it in the background (it blocks until the user finishes in the browser) and
poll its output for AUTH_URL / LOGIN_OK.
"""

import argparse
import os
import re
import shutil
import sys
import time

# Matches an http(s) URL, stopping at whitespace, quotes, angle brackets, ESC,
# or BEL. Because ESC/BEL are excluded, this pulls a clean URL straight out of
# raw terminal output even when it is wrapped in OSC-8 hyperlink escapes.
URL_RE = re.compile(rb"""https?://[^\s\x1b\x07"'<>]+""")

# Query params that only ever appear in an OAuth authorization URL — used to pick
# the auth link out of any other URLs the CLI might print.
_OAUTH_HINTS = ("code_challenge", "redirect_uri", "client_id", "authorize", "oauth")


def emit(msg):
    """Print a marker/status line and flush immediately (background-friendly)."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def find_auth_url(buf):
    """Return the OAuth authorization URL from raw output, or None.

    Only accepts a match that is followed by at least one more byte, so a URL cut
    off at the current read boundary is not returned half-formed.
    """
    for m in URL_RE.finditer(buf):
        if m.end() >= len(buf):
            continue  # possibly truncated at the buffer edge; wait for more
        url = m.group(0).decode("utf-8", "replace")
        if any(h in url for h in _OAUTH_HINTS):
            return url
    return None


def _write_raw(data):
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def run_unix(claude_cmd, timeout):
    """Run the login inside a real PTY via the built-in pty module."""
    import pty
    import select
    import signal
    import subprocess

    master, slave = pty.openpty()
    proc = subprocess.Popen(
        claude_cmd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        preexec_fn=os.setsid,  # own process group so we can kill the whole tree
    )
    os.close(slave)

    buf = bytearray()
    url_found = False
    start = time.time()
    try:
        while True:
            rlist, _, _ = select.select([master], [], [], 0.5)
            if master in rlist:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    data = b""
                if data:
                    buf.extend(data)
                    _write_raw(data)
                    if not url_found:
                        url = find_auth_url(bytes(buf))
                        if url:
                            url_found = True
                            emit("\nAUTH_URL: " + url)
                else:
                    break  # EOF on the master side
            if proc.poll() is not None:
                # Drain anything still buffered before exiting.
                try:
                    while True:
                        rest = os.read(master, 4096)
                        if not rest:
                            break
                        buf.extend(rest)
                        _write_raw(rest)
                except OSError:
                    pass
                break
            if timeout and (time.time() - start) > timeout:
                emit("\nLOGIN_TIMEOUT")
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except Exception:
                    proc.terminate()
                return 2
    finally:
        try:
            os.close(master)
        except Exception:
            pass
    return proc.wait()


def run_windows(claude_cmd, timeout):
    """Run the login on Windows through winpty (Git for Windows)."""
    import subprocess
    import threading

    winpty = shutil.which("winpty")
    name = claude_cmd[-1]
    if not winpty:
        emit("NO_PTY")
        emit(
            "This Windows shell can't allocate a terminal for the sign-in "
            "(no 'winpty' found — it normally ships with Git for Windows)."
        )
        emit("Ask the user to open a normal terminal (PowerShell / Windows "
             "Terminal) and run this one line, then finish in the browser:")
        emit("    claude mcp login " + name)
        return 3

    # A .cmd/.bat launcher (npm shim) must be run through cmd.exe; a real .exe
    # can be launched directly under winpty.
    claude_path = claude_cmd[0]
    if claude_path.lower().endswith((".cmd", ".bat")):
        inner = ["cmd", "/c"] + claude_cmd
    else:
        inner = claude_cmd
    cmd = [winpty] + inner

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0
    )
    buf = bytearray()
    state = {"url_found": False}

    def reader():
        while True:
            data = proc.stdout.read(256)
            if not data:
                break
            buf.extend(data)
            _write_raw(data)
            if not state["url_found"]:
                url = find_auth_url(bytes(buf))
                if url:
                    state["url_found"] = True
                    emit("\nAUTH_URL: " + url)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    start = time.time()
    while proc.poll() is None:
        if timeout and (time.time() - start) > timeout:
            proc.terminate()
            emit("\nLOGIN_TIMEOUT")
            return 2
        time.sleep(0.5)
    thread.join(timeout=2)
    return proc.returncode


def main():
    ap = argparse.ArgumentParser(description="Browser OAuth sign-in for an MCP server without a TTY.")
    ap.add_argument("name", help="MCP server name as registered in Claude Code")
    ap.add_argument("--timeout", type=int, default=300,
                    help="seconds to wait for the user to finish (default 300)")
    ap.add_argument("--claude", default=None,
                    help="path to the claude CLI (default: found on PATH)")
    args = ap.parse_args()

    claude = args.claude or shutil.which("claude") or "claude"
    claude_cmd = [claude, "mcp", "login", args.name]

    emit("Starting browser sign-in for MCP server '%s'…" % args.name)
    emit("A browser window should open. If it doesn't, use the AUTH_URL below.")

    if sys.platform == "win32":
        rc = run_windows(claude_cmd, args.timeout)
    else:
        rc = run_unix(claude_cmd, args.timeout)

    if rc == 0:
        emit("\nLOGIN_OK")
    elif rc not in (2, 3):
        emit("\nLOGIN_FAILED (exit %s)" % rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()
