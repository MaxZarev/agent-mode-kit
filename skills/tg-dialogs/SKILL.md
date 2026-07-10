---
name: tg-dialogs
description: Work with personal dialogs, groups, and chats in Telegram via Telethon. Use this skill when the user wants to find a conversation in Telegram, read messages from a chat or dialog, search for something in a conversation, find out what was written in a chat, send a message to a specific person or group, or says something like "find dialog", "what was written in", "read conversation", "send to X", "show messages from", "find in chat". Trigger even if the user doesn't call it a "dialog" — "what did Maria write me", "show our conversation with Andrey", "find the team group".
allowed-tools: Bash, Read
---

Work with dialogs, groups, and personal chats in Telegram via Telethon (your personal account).
Supported: dialog search, reading messages, text search, date filtering, sending messages.

## Files and paths

Everything ships next to this `SKILL.md`. Substitute the right base path for your install scope:

- User scope: `~/.claude/skills/tg-dialogs/`
- Project scope: `<project>/.claude/skills/tg-dialogs/`

Files:

- `dialogs.py` — CLI script (async, Python 3.14-compatible)
- `.env` — `TG_API_ID`, `TG_API_HASH` (copy `.env.example` and fill in)
- `auth.py` — one-time authorization (not needed if `tg-schedule` is installed next to this skill and already authorized — the Telethon session is shared automatically)

To override the session file: `TG_SESSION_PATH=/custom/path/session python3 dialogs.py ...`

## One-time setup

1. `pip install telethon python-dotenv`
2. At https://my.telegram.org → API development tools create an app, copy `api_id` and `api_hash` into `.env` (from `.env.example`).
3. Run `python3 auth.py` — enter the phone number and the code from Telegram. Skip if the `tg-schedule` skill next door is already authorized.

## CLI Operations

Replace `<SKILL>` below with the full path to `dialogs.py` for your install scope.

### Find dialogs by name

```bash
python3 <SKILL> --find "name or keyword"
```

Searches among all dialogs (personal chats, groups, channels) by substring in name or @username. Shows type and unread counter.

### List recent dialogs

```bash
python3 <SKILL> --list --limit 50
```

### Read messages from a dialog

```bash
# Last 30 messages
python3 <SKILL> --read "@username" --limit 30

# Server-side text search
python3 <SKILL> --read "Dialog Name" --search "meeting" --limit 50

# Messages since a date
python3 <SKILL> --read "@username" --since "2026-03-01"

# Combo: search + date
python3 <SKILL> --read "Team" --search "task" --since "2026-02-01" --limit 100
```

**Dialog identifier** — any of these formats:
- `@username` — Telegram username
- `"First Last"` / `"Group title"` — contact or group name (exact or partial; use `--find` first if unsure)
- `+79991234567` — phone number

### Send a message

```bash
python3 <SKILL> --send "@username" "Message text"
```

### Aliases (per-scope shortcuts)

Aliases let you refer to chats/people by a short name (e.g. `--read chat`, `--send partner "..."`) instead of typing full titles or usernames. They also avoid a slow `iter_dialogs` sweep on every call.

**Where aliases live.** `tg-dialogs.aliases.json` is stored next to the nearest `CLAUDE.md` above the current working directory — each CLAUDE.md scope is self-contained, no inheritance between scopes.

```
my-projects/
  CLAUDE.md
  tg-dialogs.aliases.json          ← root-project aliases (if any)
  clients/
    client-a/
      CLAUDE.md
      tg-dialogs.aliases.json      ← client-a-only aliases
    client-b/
      CLAUDE.md
      tg-dialogs.aliases.json      ← client-b-only aliases
```

Fallback if no `CLAUDE.md` found above CWD: `~/.claude/tg-dialogs/aliases.json`.

**Choosing a scope without `cd`.** Use `--scope <dir>` to explicitly point at a subproject's alias file — useful when the agent is working from the project root but wants to read/pin inside a client scope:

```bash
# From the project root, work with client-a's aliases
python3 <SKILL> --scope clients/client-a --read chat
python3 <SKILL> --scope clients/client-a --pin andrey "@andrey_username"
python3 <SKILL> --scope clients/client-a --aliases
```

`--scope DIR` makes the script use `DIR/tg-dialogs.aliases.json` regardless of CWD. Also available: env var `TG_ALIASES_PATH=/abs/path/to/file.json` (points at the file directly, not the directory). Without `--scope` or the env var, the script auto-detects via the nearest `CLAUDE.md` above CWD.

```bash
# Manual pin
python3 <SKILL> --pin chat "Client A: AI training"
python3 <SKILL> --pin partner "@partner_username"

# List aliases in current scope
python3 <SKILL> --aliases

# Use the alias anywhere target is expected
python3 <SKILL> --read chat --limit 50
python3 <SKILL> --send partner "Привет"
```

**Auto-pin.** When a fuzzy substring match resolves to exactly one dialog, the alias is saved automatically (keyed by the query). Next call with the same target hits the alias — no `iter_dialogs` sweep.

**Stale aliases.** If a pinned alias no longer resolves (e.g. username changed), the script silently falls back to the normal resolution chain (direct → fuzzy). The stale entry stays until overwritten by `--pin`.

## Inline Python (for complex tasks)

Python 3.14 removed the default event loop, so `telethon.sync` raises `RuntimeError: no running event loop`. Use the async client with `asyncio.run`.

```python
import os, asyncio, logging
from pathlib import Path
logging.basicConfig(level=logging.CRITICAL)
from dotenv import load_dotenv
from telethon import TelegramClient

SKILL = Path.home() / '.claude/skills/tg-dialogs'  # adjust for project scope
load_dotenv(SKILL / '.env')

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
# shared session from tg-schedule next door, or this skill's own one:
_shared = SKILL.parent / 'tg-schedule' / 'session'
SESSION = str(_shared if _shared.with_suffix('.session').exists() else SKILL / 'session')

async def main():
    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        # Iterate dialogs
        async for dialog in client.iter_dialogs(limit=50):
            print(dialog.name, type(dialog.entity).__name__)

        # Resolve entity
        entity = await client.get_entity('@username')

        # Read with search
        msgs = await client.get_messages(entity, search='keyword', limit=50)
        for m in msgs:
            print(m.date, m.sender_id, m.text)

        # Send
        await client.send_message(entity, 'Text')

asyncio.run(main())
```

Notes for group chats:
- To read a group you're in, prefer resolving by title (`client.iter_dialogs()` → match by `d.name`) rather than by raw `-100...` channel ID — the latter often fails with `Could not find the input entity` unless the channel is already in the session cache.
- `m.sender` may be `None` if sender info hasn't been fetched; use `await m.get_sender()` to fetch on demand.

## Workflow

1. **Clarify what's needed.** If the user said "find conversation with Max" — run `--find "Max"` first, show the hit list, confirm the right one.
2. **Pin once, reuse forever.** After confirming the right chat/person, `--pin <short-alias> <target>` so future calls use the alias directly — faster and unambiguous. For subproject work (`clients/<name>/`), `cd` into that directory so the alias lands in the client's scope, not the root.
3. **Read messages.** Default to the last 30. Narrow with `--search` for a topic or `--since` for a time window.
4. **Summarize.** Don't dump raw text — extract key points, agreements, open questions.
5. **Send replies only after confirmation.** Always show the exact text to the user and wait for approval — Telegram messages can't be silently recalled.

## Important

- If `tg-schedule` is installed next to this skill, the Telethon session is shared — no re-authorization needed.
- `iter_dialogs()` without a limit is slow on accounts with many chats — always set `--limit`.
- Server-side `--search` works in groups, channels, and personal chats that have server-stored history.
