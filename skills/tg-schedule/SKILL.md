---
name: tg-schedule
description: Schedule a post to a Telegram channel using Telethon (personal account, native Telegram scheduler). Triggers when the user asks to post, publish, schedule, or send something to Telegram, their channel, or mentions отложенный пост / запланировать пост / опубликовать в канале / редактировать пост / удалить пост.
allowed-tools: Bash, Read
---

Publishing posts to a Telegram channel via Telethon (personal account, native Telegram scheduler).
Supported: animated emoji from 11 packs, formatting, scheduled posts.

All paths below assume user scope (`~/.claude/skills/tg-schedule/`); for project
scope substitute `<project>/.claude/skills/tg-schedule/`.

## Files

- `~/.claude/skills/tg-schedule/post_helper.py` — main module
- `~/.claude/skills/tg-schedule/emoji_ids.json` — 1110 animated emoji from 11 packs
- `~/.claude/skills/tg-schedule/send.py` — CLI for simple posts without formatting
- `~/.claude/skills/tg-schedule/auth.py` — one-time authorization (creates `session.session`)
- `~/.claude/skills/tg-schedule/style.md` — the channel's voice/style (fill in for your channel)

## One-time setup

1. `pip install telethon python-dotenv`
2. At https://my.telegram.org → API development tools create an app, copy `api_id` and `api_hash`.
3. Copy `.env.example` to `.env` next to this file and fill in `TG_API_ID`, `TG_API_HASH`, `TG_CHANNEL` (your channel; the account must be its admin).
4. Run `python3 auth.py` — enter the phone number and the code from Telegram. The session is saved to `session.session` and is not needed again.

Note: animated (custom) emoji in posts require Telegram Premium on the posting account. Without Premium, posts still work — emoji just stay static.

## Credentials

Read credentials from `.env` next to this file: `TG_API_ID`, `TG_API_HASH`, `TG_CHANNEL`.
The Python scripts load them automatically via `dotenv`.

For inline Python code, use:
```python
import os
from pathlib import Path
from dotenv import load_dotenv

SKILL_DIR = Path.home() / '.claude/skills/tg-schedule'  # adjust for project scope
load_dotenv(SKILL_DIR / '.env')
API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
CHANNEL = os.environ['TG_CHANNEL']
SESSION = str(SKILL_DIR / 'session')
```

## How to send a post

Always use `post_helper.TgPost` — it automatically applies animated emoji and formatting.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.claude/skills/tg-schedule'))
from post_helper import TgPost

post = TgPost()  # default channel — TG_CHANNEL from .env
post.text = """POST TEXT"""

# Formatting (substring must exactly match the text)
post.bold('Post title')       # bold
post.italic('key phrase')     # italic
post.code('technical term')   # monospace
post.spoiler('hidden text')   # spoiler — tap to reveal
post.link('text', 'https://...')  # clickable link

# Sending
post.send()                              # immediately (no delay)
post.send(schedule="2026-03-10 18:30")  # scheduled (time in MSK), 10 sec delay after sending
post.send(schedule="...", delay=0)       # no delay (for a single post)
```

**Important:** emoji in text are applied **automatically** — just insert the desired emoji in the text, the helper will find it in `emoji_ids.json` and add the animated version.

## Post style

The channel's voice lives in `style.md` next to this file — read it before
writing or editing a post and follow it by default. If it is still the
unfilled template, ask the user about their channel's tone first (or offer to
fill `style.md` based on their recent posts).

## Workflow

### 1. Write the text

Help the user with the text — clarify topic, tone, length. Text is written normally, emoji are inserted directly. Follow the channel style (see above).

**Available animated emoji (from 11 packs, 1110 total):**
Most standard emoji have animated versions. Especially effective:
- Emotions: 🤩 😅 😭 🤬 😱 🥳 😏 🙄 😂 🤔 😴 😋
- Reactions: 👏 👍 👎 ✋ 👋 💪 👇
- Symbols: 🔥 ✨ 💎 ⭐️ 👑 💡 🎉 🥂
- News/content: 👀 🧠 📌 🔗 📈 📉 ⚡️ 🔔 ❗️ ✔️ ❌
- Kawaii/stickers: wide selection from @emoji1, Kawaii Emoji, Balloon Emoji packs

### 2. Define formatting

Typical post structure:
- **Bold** — title (entire first line including emoji) + subheadings within post before lists
- *Italic* — key numbers, important phrases, emotional accents (2-4 per post)
- `code` — technical terms, tool names (Cursor, Claude Code, n8n, etc.)
- ||Spoiler|| — intrigue, answer to a question, price
- [link](url) — CTA, channel/product mention

Formatting rules:
- Every post MUST use at least 2-3 formatting types — post should not be plain text
- Subheadings before lists and blocks — always bold
- Technical terms — always monospace
- Key numbers and results — italic
- Quotes/others' speech — separate line, italic or via "Says:" + direct speech
- Don't overload: no more than 1 bold subheading per 3-4 paragraphs

### 3. Determine the time

Parse time from the user's request:
- "tomorrow at 10" -> tomorrow 10:00 MSK
- "on Friday at 18:30" -> nearest Friday 18:30 MSK
- "in 2 hours" -> current time + 2 hours
- "March 10 at 9" -> 2026-03-10 09:00

Minimum 10 minutes in the future. Confirm: "Will schedule for **Friday, March 13 at 18:30 MSK**."

### 4. Send

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.claude/skills/tg-schedule'))
from post_helper import TgPost

post = TgPost()
post.text = """..."""
post.bold('...')
# ... remaining formatting
post.send(schedule="YYYY-MM-DD HH:MM")
# When batch-sending multiple posts, delay=10 (default) automatically prevents FloodWait.
# For a single post you can pass delay=0.
```

### 5. Confirm

On success, report the publication time (MSK) and that the post is visible in the channel's "Scheduled" section.

## Other operations

### List scheduled posts
```bash
python3 ~/.claude/skills/tg-schedule/send.py --list
```
Returns all scheduled posts including today's.

### Delete a scheduled post
```bash
python3 ~/.claude/skills/tg-schedule/send.py --delete <ID>
```

### Edit a scheduled post
```bash
python3 ~/.claude/skills/tg-schedule/send.py --edit <ID> "New text"
```
Edits plain text only. For formatting — delete and recreate via `TgPost`.

### Get published posts from the feed
```python
import sys, os, logging
from pathlib import Path
logging.basicConfig(level=logging.CRITICAL)
SKILL_DIR = Path.home() / '.claude/skills/tg-schedule'
sys.path.insert(0, str(SKILL_DIR))
from dotenv import load_dotenv
load_dotenv(SKILL_DIR / '.env')
from telethon.sync import TelegramClient

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
CHANNEL = os.environ['TG_CHANNEL']
SESSION = str(SKILL_DIR / 'session')

with TelegramClient(SESSION, API_ID, API_HASH) as client:
    msgs = client.get_messages(CHANNEL, limit=20)
    for m in msgs:
        print(f'ID={m.id} | {m.date} | {m.text[:100]}')
```

### Search posts by keyword (in published)
```python
with TelegramClient(SESSION, API_ID, API_HASH) as client:
    msgs = client.get_messages(CHANNEL, limit=200)
    for m in msgs:
        if m.text and 'keyword' in m.text.lower():
            print(f'ID={m.id} | {m.date} | {m.text[:150]}')
```

### Direct link to a post
```
https://t.me/<channel_name_without_@>/<ID>
```

### Different channel
```python
post = TgPost('@another_channel')
```

## Important: correct API methods for scheduled posts

`client.get_messages(channel, scheduled=True)` **does not return posts scheduled for today** — use only for future dates.

To get **all** scheduled posts (including today's) use `GetScheduledHistoryRequest`:
```python
from telethon.tl.functions.messages import GetScheduledHistoryRequest, DeleteScheduledMessagesRequest

with TelegramClient(SESSION, API_ID, API_HASH) as client:
    channel = client.get_entity(CHANNEL)
    result = client(GetScheduledHistoryRequest(peer=channel, hash=0))
    msgs = result.messages  # all scheduled, including today
    # post text: m.message (not m.text!)
```

To **delete** a scheduled post use `DeleteScheduledMessagesRequest` (not `delete_messages`!):
```python
client(DeleteScheduledMessagesRequest(peer=channel, id=[msg_id]))
```

## Adding new emoji packs

The user sends an emoji from a new pack to Saved Messages (Favorites).
Run the script to automatically extract the entire pack and update `emoji_ids.json`:

```python
import logging, json, os
from pathlib import Path
logging.basicConfig(level=logging.CRITICAL)
SKILL_DIR = Path.home() / '.claude/skills/tg-schedule'
from dotenv import load_dotenv
load_dotenv(SKILL_DIR / '.env')
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetCustomEmojiDocumentsRequest, GetStickerSetRequest
from telethon.tl.types import DocumentAttributeCustomEmoji, MessageEntityCustomEmoji, InputStickerSetID

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
SESSION = str(SKILL_DIR / 'session')

with TelegramClient(SESSION, API_ID, API_HASH) as client:
    msgs = client.get_messages('me', limit=10)
    all_doc_ids = set()
    for msg in msgs:
        if msg.entities:
            for e in msg.entities:
                if isinstance(e, MessageEntityCustomEmoji):
                    all_doc_ids.add(e.document_id)
    docs = client(GetCustomEmojiDocumentsRequest(document_id=list(all_doc_ids)))
    packs = {}
    for doc in docs:
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeCustomEmoji):
                ss = attr.stickerset
                if ss.id not in packs:
                    packs[ss.id] = ss.access_hash
    all_emoji = {}
    for set_id, access_hash in packs.items():
        stickerset = client(GetStickerSetRequest(
            stickerset=InputStickerSetID(id=set_id, access_hash=access_hash), hash=0))
        for doc in stickerset.documents:
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeCustomEmoji) and attr.alt not in all_emoji:
                    all_emoji[attr.alt] = doc.id

emoji_path = SKILL_DIR / 'emoji_ids.json'
with open(emoji_path) as f:
    existing = json.load(f)
existing.update(all_emoji)
with open(emoji_path, 'w') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print(f'Added new: {len(all_emoji)}, total: {len(existing)}')
```
