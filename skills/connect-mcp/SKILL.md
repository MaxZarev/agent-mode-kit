---
name: connect-mcp
description: Connect / add an MCP server to Claude Code for the user, end-to-end, without making them touch the terminal — handles no-auth servers, OAuth servers (browser opens by itself), and servers that need a static API key/token (collected via the secret-input skill so the key never appears in chat). Works on macOS and Windows. Invoke it even if you already know `claude mcp add` — that command alone can't do the OAuth browser sign-in (which needs a real terminal), skips choosing scope, and would leak a pasted key, so the skill's flow is what actually gets the server connected safely. Use this whenever the user wants to add, connect, hook up, install, or set up an MCP server / connector / integration, or pastes an MCP URL like https://…/mcp or https://…/sse and asks to connect it — e.g. «подключи mcp», «подключи этот сервер», «добавь коннектор», «подключи todoist/notion/sentry mcp», «connect this mcp», «add an mcp server», «hook up this connector», «set up mcp». Do NOT use it merely to USE an already-connected server's tools (creating a Todoist task, querying a DB) — only for the act of connecting/authenticating one.
---

# connect-mcp — hook up an MCP server for a non-technical user

Your goal: take whatever the user gives you (usually just a URL, sometimes a
command), get the MCP server registered in Claude Code, get it **Connected**,
and do all of it **for** them — they should never open a terminal, and any
secret they type must go through a private page, never the chat.

Keep every message to the user in plain, non-technical language. Describe things
they can *see* ("a browser tab will open", "a small page will appear"), not
infrastructure ("spawning a PTY", "writing to ~/.claude.json").

---

## The big picture

There are only three kinds of MCP server, and the difference is **how they
authenticate**. You often don't know which kind you have until you try, so the
flow is: add it, check the status, then branch.

```
        add the server
              │
        claude mcp get <name>  ──►  status?
              │
   ┌──────────┼─────────────────────────────┐
   ▼          ▼                              ▼
 Connected   Needs authentication      needs a static
 (no auth)   = OAuth                    API key / token
   │          │                              │
  done   browser sign-in              collect key via
         (mcp_login.py)               secret-input, then
                                      re-add with the key
```

Work through the steps below in order.

> **Placeholders used below:** `<name>` — the short server name you pick;
> `<skill-dir>` — the folder that contains *this* SKILL.md (where `scripts/`
> lives); `<tmp>` — a scratchpad/temp folder **outside** the user's project (use
> the session scratchpad dir if you have one). Substitute real values; never
> leave the angle brackets in a command.

---

## Step 1 — Understand what you were given

- A URL ending in `/mcp` or containing `/mcp` → a **streamable HTTP** server
  (`--transport http`). This is the common case (Todoist, Notion, Sentry,
  Linear, most hosted connectors).
- A URL ending in `/sse` → an **SSE** server (`--transport sse`).
- A shell command like `npx -y some-mcp-server` or a path to a local program →
  a **stdio** server (runs locally). Rarer for non-technical users; usually
  needs Node/Python installed and often an API key as an environment variable.

If the user only says a product name ("connect my Notion") and you don't know
the URL, ask them for the MCP link from that product's docs / integrations page,
or search for the official one — don't guess an endpoint.

While you're at it, check whether the service also offers a **static API
token** (a key from its dashboard) as an alternative to OAuth. If it does,
prefer that path (Step 4c): it has far fewer moving parts — no browser
sign-in, no terminal tricks — which especially matters on Windows.

> Some setups route **local stdio** servers through a central MCP hub/registry
> instead of adding them directly. If the project has such a convention, follow
> it for stdio servers. Hosted **HTTP/SSE** connectors are added directly, as
> below.

## Step 2 — Choose the scope (ask)

Always ask the user, in plain terms, before adding:

> "Should this be available in **all** your projects, or **only this one**?"

- All projects → `--scope user` (global).
- Only this project → `--scope local`.

Pick a short, lowercase, memorable `<name>` (e.g. `todoist`, `notion`,
`sentry`). If a server with that name already exists (`claude mcp get <name>`
succeeds), reuse or ask before overwriting.

## Step 3 — Add the server

First make sure the name is free: `claude mcp get <name>` should say "No MCP
server named …". If it already exists, reuse it or pick another name (adding over
an existing name isn't reliable).

Then run the matching command yourself (Bash tool), using the scope from Step 2.

**HTTP:**
```
claude mcp add --transport http --scope <user|local> <name> <url>
```
**SSE:**
```
claude mcp add --transport sse --scope <user|local> <name> <url>
```
**stdio (no key):**
```
claude mcp add --scope <user|local> <name> -- <command> [args...]
```

Add it **without any secret first**, even if the user already handed you a key.
Adding it plain and reading the status (Step 4) is the reliable way to learn
whether the server wants OAuth or a static key — they're handled differently.

Shortcut: if the user or the server's docs have already made clear it uses a
**static API key/token**, skip straight to Step 4c and add it with the key in one
go — no need for the plain add first.

## Step 4 — Check the status and branch

```
claude mcp get <name>
```

Read the **Status** line and branch:

### 4a. `✔ Connected` → done
No authentication needed. Go to Step 5.

### 4b. `! Needs authentication` → OAuth (browser sign-in)

This server uses OAuth: the user signs in through their browser and approves
access. The catch: the built-in `claude mcp login` refuses to run without a real
terminal, which you don't have. Use the bundled helper, which gets it a real
terminal so the browser flow works unattended.

1. Tell the user first, plainly:
   > "A browser tab will open so you can sign in to <service> and allow access.
   > After you approve, it finishes automatically — nothing to paste here."

   On **Windows** add one more sentence: "A small black console window will
   also appear — that's part of the sign-in, don't close it; it goes away by
   itself." A surprise console window looks like a virus to a non-technical
   user.

2. Run the helper **in the background** (it blocks until the user finishes in the
   browser):
   ```
   python3 <skill-dir>/scripts/mcp_login.py <name> --timeout 300
   ```
   Use `python3` on macOS/Linux and `python` on Windows if `python3` is missing.

3. Poll the helper's output file for these markers:
   - `CLI_VERSION: <v>` — preflight info; nothing to do, but useful in reports.
   - `CLI_TOO_OLD` — the installed Claude Code CLI has no `mcp login` command
     (old versions didn't; the raw failure is a cryptic `unknown command
     'login'`). **Update the CLI yourself and re-run the helper**: native
     install → `claude update`; npm install → `npm i -g
     @anthropic-ai/claude-code@latest`. Tell the user in plain words ("your
     Claude Code needed a quick update — done, continuing").
   - `AUTH_URL: <url>` — the sign-in link. **Immediately relay it to the user**
     as a clickable fallback: "If the tab didn't open, click here: <url>". This
     matters — on some machines (Windows especially) the auto-open silently
     fails and a non-technical user is otherwise stuck.
   - `LOGIN_OK` — success. Continue to Step 5.
   - `LOGIN_TIMEOUT` — they ran out of time; offer to run it again.
   - `NO_PTY` (Windows only) — the helper couldn't open a console window and has
     no fallback left; it prints one short line for the user to run in their own
     terminal. Relay exactly that line and stay with them through it.

   The real sign of success is `✔ Connected` in `claude mcp list` — the helper
   checks that itself on Windows (the login window may still say "Waiting…"
   after the connection is already live). If the helper dies without a clear
   marker, run `claude mcp list` before declaring failure.

Why the helper instead of `claude mcp login` directly: without a real terminal
the plain command dies with "stdin isn't a terminal". The helper gets it one —
a pseudo-terminal via Python's `pty` on macOS/Linux; on Windows it launches the
login in a **new console window** through a temporary `.bat` file, with the
output redirected to a file it watches (`winpty` is only a fallback — it needs
a console itself, so it can't help from a consoleless agent shell). Either way
the same official flow runs — nothing about the OAuth is replaced or faked.

### 4c. Needs a static API key / token → collect it privately

Some servers authenticate with a fixed key or token (from the service's
dashboard) sent as a header (HTTP) or an environment variable (stdio). You'll
usually know because the user has an API key, or the server's docs say so, or the
status shows a connection/auth error that isn't the OAuth "Needs authentication".

**Never take the key through the chat.** Use the **secret-input** skill — it
opens a small local page where the user types the value; it's written to a file
and never shown back. Then feed it into the config *without printing it*.

1. Find out the exact auth shape from the service's docs (header name, `Bearer`
   vs raw, or which env var). Ask the user if unclear.
2. Use the **secret-input** skill to collect the value into a **temporary** env
   file in the scratchpad (NOT the user's project), under a variable name you
   choose — use the same name when collecting and when reading it back. For
   example, have secret-input write `MCP_TOKEN` to `<tmp>/mcp.env` by passing an
   absolute path to its `--env-path` (e.g. `--env-path <tmp>/mcp.env`).
3. Re-add the server with the key read from that file into a shell variable, so
   the value is never typed or printed. The `sed` strips the surrounding quotes
   secret-input adds only when a value contains spaces (normal API keys don't):

   **HTTP with a bearer token (match the header to the server's docs):**
   ```
   TOKEN=$(grep '^MCP_TOKEN=' <tmp>/mcp.env | cut -d= -f2- | sed 's/^"//; s/"$//')
   claude mcp add --transport http --scope <user|local> <name> <url> \
     --header "Authorization: Bearer $TOKEN"
   ```
   **stdio with an env-var key:**
   ```
   KEY=$(grep '^MCP_TOKEN=' <tmp>/mcp.env | cut -d= -f2- | sed 's/^"//; s/"$//')
   claude mcp add --scope <user|local> <name> -e MCP_API_KEY=$KEY -- <command> [args...]
   ```
   `claude mcp add` redacts the header/env value in its own confirmation output,
   and the variable assignment prints nothing — so the key stays out of the
   transcript. (If you already did a plain add in Step 3, `claude mcp remove
   <name> -s <scope>` first, then re-add with the key.)
4. Delete the temp file (`rm -f <tmp>/mcp.env`). Then tell the user honestly that
   the key now lives in Claude Code's own config so the server can connect —
   that's expected and required; it just never passed through the chat.

## Step 5 — Verify and tell the user

1. Confirm it worked:
   ```
   claude mcp list
   ```
   Find `<name>` in the list and check it shows `✔ Connected`.

   The verify command matters for privacy: for **no-auth and OAuth** servers,
   `claude mcp get <name>` is also fine and prints a clear Status line. But if you
   configured the server with a **secret** (a `--header` token or an `-e` env var
   from Step 4c), do NOT run `claude mcp get <name>` — it prints those values back
   in plaintext and leaks the key into the transcript. `claude mcp list` shows
   only the URL and status, so it's always safe.
2. Tell the user in plain words that it's connected, and this important detail:
   **the new server's tools become available in a *new* Claude session, not the
   current one** — so they should start a fresh chat to use it. (An already-open
   session won't see it.)
3. Mention how to undo, in case they want it later:
   - Sign out: `claude mcp logout <name>`
   - Remove entirely: `claude mcp remove <name> -s <user|local>`

---

## Talking to non-technical users — quick rules

- Announce the visible thing *before* it happens ("a page will open", "a tab will
  open"). Surprise browser tabs feel like something broke.
- Always give the AUTH_URL as a clickable fallback during OAuth.
- Never ask them to paste a key into the chat. If they do anyway, warn them the
  value is now in the conversation and suggest rotating it later.
- Don't narrate internals (PTY, config file paths, JSON). Report outcomes:
  "connected", "signed in", "done".

## Cross-platform notes

- **macOS / Linux:** everything runs directly; `mcp_login.py` uses the built-in
  `pty` module (no install).
- **Windows:** `mcp_login.py` opens the OAuth sign-in in a **new console
  window** (via a temp `.bat`, output captured to a file) — that's the path
  that actually works from a consoleless agent shell. Expect these Windows
  specifics:
  - warn the user about the extra console window before it appears (Step 4b);
  - an old CLI is the #1 real-world failure — the helper preflights it and
    emits `CLI_TOO_OLD`; update (`claude update` / npm) and re-run;
  - never build `cmd /c "…"` commands inline with quotes yourself — cmd's
    quote-stripping silently breaks redirects (the helper already does it
    right via the `.bat`);
  - `winpty` (Git for Windows) is only a last-ditch fallback, not a
    requirement.
- `grep`/`cut` piping in Step 4c works in bash, including Git Bash on Windows.
- If Node is missing when secret-input needs it, secret-input handles the
  offer-to-install / manual fallback itself.

## Command cheatsheet

| Goal | Command |
| --- | --- |
| Add HTTP (global) | `claude mcp add --transport http --scope user <name> <url>` |
| Add HTTP (this project) | `claude mcp add --transport http --scope local <name> <url>` |
| Add SSE | `claude mcp add --transport sse --scope <user\|local> <name> <url>` |
| Add stdio | `claude mcp add --scope <user\|local> <name> -- <command> [args]` |
| Add with header token | `claude mcp add --transport http --scope <s> <name> <url> --header "Authorization: Bearer $TOKEN"` |
| Check status (no-auth / OAuth) | `claude mcp get <name>` |
| Check status (server has a secret) | `claude mcp list`  — `get` would print the key |
| List all | `claude mcp list` |
| OAuth sign-in (no terminal) | `python3 <skill-dir>/scripts/mcp_login.py <name>` |
| Update an outdated CLI | `claude update` (native) / `npm i -g @anthropic-ai/claude-code@latest` (npm) |
| Sign out | `claude mcp logout <name>` |
| Remove | `claude mcp remove <name> -s <user\|local>` |
