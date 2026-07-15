#!/usr/bin/env python3
"""
Browser OAuth sign-in for a Claude Code MCP server, WITHOUT an interactive shell.

Why this exists:
    `claude mcp login <name>` refuses to run unless its stdin is a real terminal
    (TTY) — it errors with "stdin isn't a terminal". Agents and the Bash tool do
    not provide a TTY, so the plain command fails. This wrapper gets the login a
    real terminal so it runs unattended: `claude` opens the browser itself, the
    user approves access, and the local callback finishes the flow.

What it does:
    - Preflight (all platforms): logs `claude --version` and verifies the CLI
      actually HAS the `mcp login` command. Old CLIs don't, and without this
      check that failure surfaces as a cryptic exit 1.
    - macOS / Linux: runs the login inside a pseudo-terminal via the built-in
      `pty` module (no dependencies).
    - Windows: writes a tiny .bat file and starts it in a NEW console window —
      a real terminal for stdin — with all output redirected into a temp file
      that this script polls. This works from consoleless agent shells, where
      winpty cannot (winpty itself needs a console on stdin and dies with
      "stdin is not a tty"). winpty is kept only as a fallback if the new
      console cannot be opened; a manual one-liner is the last resort.
    - On Windows, success is detected by polling `claude mcp list` until the
      server shows "Connected" — the login window can still show "Waiting…"
      after the config has already switched to Connected.
    - Cleans up its temp files (.bat / output .txt) when done.
    - Prints these easy-to-grep markers on their own lines:
        CLI_VERSION: <v>  claude CLI version (preflight)
        CLI_TOO_OLD       the CLI has no `mcp login`; update it, then re-run
                          (native install: `claude update`; npm install:
                          `npm i -g @anthropic-ai/claude-code@latest`)
        CLI_ERROR: …      the claude CLI could not be run at all
        AUTH_URL: <url>   the authorization link (relay it to the user in case
                          the browser did not open on its own)
        LOGIN_OK          on success
        LOGIN_FAILED ...  on failure (the raw login output precedes it)
        LOGIN_TIMEOUT     if the user did not finish in time
        NO_PTY            no way to give the login a terminal; a one-line
                          manual command for the user follows

Usage:
    python3 mcp_login.py <server-name> [--timeout SECONDS] [--claude PATH]

Run it in the background (it blocks until the user finishes in the browser) and
poll its output for AUTH_URL / LOGIN_OK / CLI_TOO_OLD.
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


def find_auth_url(buf, allow_tail=False):
    """Return the OAuth authorization URL from raw output, or None.

    By default a match at the very end of the buffer is skipped (it may be cut
    off at the read boundary); pass allow_tail=True once the output has settled
    and a trailing URL is known to be complete.
    """
    for m in URL_RE.finditer(buf):
        if m.end() >= len(buf) and not allow_tail:
            continue  # possibly truncated at the buffer edge; wait for more
        url = m.group(0).decode("utf-8", "replace")
        if any(h in url for h in _OAUTH_HINTS):
            return url
    return None


def _write_raw(data):
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def run_claude(claude, args, timeout=60):
    """Run the claude CLI synchronously (no TTY), return (rc, combined output).

    An npm .cmd/.bat shim can't be exec'd directly on Windows — wrap it in
    cmd /c. Output is decoded as UTF-8 regardless of the console codepage.
    """
    import subprocess

    cmd = [claude] + list(args)
    if sys.platform == "win32" and claude.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c"] + cmd
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except Exception as e:
        return -1, str(e)
    out = (p.stdout or b"") + (p.stderr or b"")
    return p.returncode, out.decode("utf-8", "replace")


def _emit_update_hint(claude):
    emit("This Claude Code CLI has no 'mcp login' command — it is too old.")
    if claude.lower().endswith((".cmd", ".bat")) or "npm" in claude.lower():
        emit("Looks like an npm install. Update with:")
        emit("    npm i -g @anthropic-ai/claude-code@latest")
    else:
        emit("Update with:")
        emit("    claude update")
        emit("(npm installs instead: npm i -g @anthropic-ai/claude-code@latest)")
    emit("Then re-run this script.")


def preflight(claude):
    """Log the CLI version and make sure `claude mcp login` exists at all."""
    rc, out = run_claude(claude, ["--version"], timeout=45)
    if rc != 0:
        emit("CLI_ERROR: could not run '%s --version': %s" % (claude, out.strip()[:300]))
        return False
    first = out.strip().splitlines()[0] if out.strip() else "unknown"
    emit("CLI_VERSION: " + first)

    rc, out = run_claude(claude, ["mcp", "--help"], timeout=45)
    if "login" not in out:
        emit("CLI_TOO_OLD")
        _emit_update_hint(claude)
        return False
    return True


def check_connected(claude, name):
    """True once `claude mcp list` shows this server as Connected."""
    rc, out = run_claude(claude, ["mcp", "list"], timeout=90)
    if rc != 0:
        return False
    for line in out.splitlines():
        line = line.strip()
        if line.startswith(name + ":") and "Connected" in line:
            return True
    return False


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


def _kill_tree(proc):
    """Best-effort kill of a Windows process and its children."""
    import subprocess

    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True, timeout=15,
        )
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def run_windows(claude, name, timeout):
    """Windows: run the login in a NEW console window via a .bat file.

    The new window gives the login a real terminal on stdin (its TTY check
    passes), while `> file` on stdout does NOT break that check — so we still
    capture the output, including AUTH_URL. All quoting lives inside the .bat:
    building the same command inline via `cmd /c "…"` trips over cmd's
    quote-stripping rules and silently runs nothing.
    """
    import subprocess
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="mcp-login-")
    out_path = os.path.join(tmpdir, "login-output.txt")
    bat_path = os.path.join(tmpdir, "login.bat")

    # `call` works for both a real claude.exe and an npm .cmd shim. The file is
    # written as UTF-8 and switches the console to codepage 65001 first, so
    # non-ASCII paths (e.g. a Cyrillic user-profile dir) survive.
    bat = (
        "@echo off\r\n"
        ">nul chcp 65001\r\n"
        + 'call "%s" mcp login %s > "%s" 2>&1\r\n' % (claude, name, out_path)
        + 'echo EXIT_CODE=%%ERRORLEVEL%% >> "%s"\r\n' % out_path
    )
    with open(bat_path, "w", encoding="utf-8", newline="") as f:
        f.write(bat)

    CREATE_NEW_CONSOLE = 0x00000010
    proc = None
    launched = False
    try:
        proc = subprocess.Popen(
            ["cmd.exe", "/c", bat_path], creationflags=CREATE_NEW_CONSOLE
        )
        launched = True
    except Exception:
        proc = None
    if not launched:
        ps = "Start-Process -FilePath cmd.exe -ArgumentList '/c','\"%s\"'" % bat_path
        for shell in ("powershell", "pwsh"):
            if shutil.which(shell):
                try:
                    subprocess.Popen([shell, "-NoProfile", "-Command", ps])
                    launched = True
                    break
                except Exception:
                    continue
    if not launched:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return run_winpty(claude, name, timeout)

    start = time.time()
    seen = 0
    stable_polls = 0
    url_found = False
    next_status_check = start + 8
    try:
        while True:
            time.sleep(1.0)
            try:
                with open(out_path, "rb") as f:
                    data = f.read()
            except OSError:
                data = b""

            if len(data) > seen:
                _write_raw(data[seen:])
                seen = len(data)
                stable_polls = 0
            else:
                stable_polls += 1

            text = data.decode("utf-8", "replace")

            if not url_found:
                # A trailing URL is accepted only after the output has settled,
                # so a half-written line is never relayed.
                url = find_auth_url(data, allow_tail=stable_polls >= 2)
                if url:
                    url_found = True
                    emit("\nAUTH_URL: " + url)

            if "unknown command" in text and "login" in text:
                emit("\nCLI_TOO_OLD")
                _emit_update_hint(claude)
                return 4

            m = re.search(r"^EXIT_CODE=(\d+)", text, re.M)
            if m:
                return int(m.group(1))

            now = time.time()
            if now >= next_status_check:
                next_status_check = now + 10
                if check_connected(claude, name):
                    # The config already says Connected; the login window may
                    # still say "Waiting…" — close it, the flow is done.
                    if proc is not None:
                        _kill_tree(proc)
                    return 0

            if timeout and (time.time() - start) > timeout:
                emit("\nLOGIN_TIMEOUT")
                if proc is not None:
                    _kill_tree(proc)
                return 2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_winpty(claude, name, timeout):
    """Fallback: run the login through winpty (Git for Windows).

    Only reachable when a new console window could not be opened. Note winpty
    itself needs a console on stdin, so from a consoleless agent shell it
    usually fails too — hence fallback, not the primary path.
    """
    import subprocess
    import threading

    winpty = shutil.which("winpty")
    if not winpty:
        emit("NO_PTY")
        emit(
            "Couldn't open a console window for the sign-in on this machine, "
            "and there is no 'winpty' to fall back on."
        )
        emit("Ask the user to open a normal terminal (PowerShell / Windows "
             "Terminal) and run this one line, then finish in the browser:")
        emit("    claude mcp login " + name)
        emit("Afterwards, verify with: claude mcp list")
        return 3

    claude_cmd = [claude, "mcp", "login", name]
    # A .cmd/.bat launcher (npm shim) must be run through cmd.exe; a real .exe
    # can be launched directly under winpty.
    if claude.lower().endswith((".cmd", ".bat")):
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

    if not preflight(claude):
        sys.exit(4)

    emit("Starting browser sign-in for MCP server '%s'…" % args.name)
    emit("A browser window should open. If it doesn't, use the AUTH_URL below.")

    if sys.platform == "win32":
        rc = run_windows(claude, args.name, args.timeout)
    else:
        rc = run_unix([claude, "mcp", "login", args.name], args.timeout)

    if rc == 0:
        emit("\nLOGIN_OK")
    elif rc not in (2, 3, 4):
        emit("\nLOGIN_FAILED (exit %s)" % rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()
