#!/usr/bin/env python3
"""
Manage scheduled posts in Telegram via Telethon.

Commands:
  send.py "Text" "2026-03-10 18:30" [@channel]   — create a scheduled post
  send.py --file /tmp/post.txt "2026-03-10 18:30" — post from file
  send.py --list [@channel]                        — list scheduled posts
  send.py --edit <id> "New text" [@channel]         — edit a post
  send.py --delete <id> [@channel]                 — delete a post

Default channel: TG_CHANNEL from .env next to this script.
Time in MSK (UTC+3).
"""

import os
import sys
import logging
logging.basicConfig(level=logging.CRITICAL)

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetScheduledHistoryRequest, DeleteScheduledMessagesRequest

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
SESSION = os.path.join(os.path.dirname(__file__), 'session')
DEFAULT_CHANNEL = os.environ.get('TG_CHANNEL', '')
MSK = timezone(timedelta(hours=3))


def require_channel(channel):
    if not channel:
        print("Error: no channel. Pass @channel as the last argument "
              "or set TG_CHANNEL in .env next to this script.")
        sys.exit(1)
    return channel


def get_client():
    return TelegramClient(SESSION, API_ID, API_HASH)


def cmd_send(text, dt_str, channel):
    dt_msk = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=MSK)
    now = datetime.now(tz=timezone.utc)

    if (dt_msk.timestamp() - now.timestamp()) < 600:
        print(f"Error: time must be at least 10 minutes in the future.")
        print(f"Scheduled: {dt_msk.strftime('%Y-%m-%d %H:%M MSK')}")
        sys.exit(1)

    with get_client() as client:
        msg = client.send_message(channel, text, schedule=dt_msk)

    print(f"OK: post scheduled for {dt_msk.strftime('%d %B %Y %H:%M')} MSK")
    print(f"Channel: {channel}")


def cmd_list(channel):
    with get_client() as client:
        channel_entity = client.get_entity(channel)
        result = client(GetScheduledHistoryRequest(peer=channel_entity, hash=0))
        msgs = result.messages

    if not msgs:
        print(f"No scheduled posts in {channel}")
        return

    print(f"Scheduled posts in {channel}:\n")
    for m in msgs:
        dt_msk = m.date.astimezone(MSK)
        text = getattr(m, 'message', None) or getattr(m, 'text', None)
        preview = text[:60].replace('\n', ' ') if text else '[media]'
        print(f"  ID {m.id} | {dt_msk.strftime('%d %b %H:%M MSK')} | {preview}")


def cmd_edit(msg_id, new_text, channel):
    with get_client() as client:
        channel_entity = client.get_entity(channel)
        result = client(GetScheduledHistoryRequest(peer=channel_entity, hash=0))
        msgs = result.messages
        target = next((m for m in msgs if m.id == msg_id), None)

        if not target:
            print(f"Error: post with ID {msg_id} not found in {channel}")
            print("Use --list to see post IDs")
            sys.exit(1)

        client.edit_message(channel, msg_id, new_text, schedule=target.date)

    dt_msk = target.date.astimezone(MSK)
    print(f"OK: post ID {msg_id} edited")
    print(f"Scheduled for: {dt_msk.strftime('%d %B %Y %H:%M')} MSK")


def cmd_delete(msg_id, channel):
    with get_client() as client:
        channel_entity = client.get_entity(channel)
        result = client(GetScheduledHistoryRequest(peer=channel_entity, hash=0))
        msgs = result.messages
        target = next((m for m in msgs if m.id == msg_id), None)

        if not target:
            print(f"Error: post with ID {msg_id} not found in {channel}")
            sys.exit(1)

        client(DeleteScheduledMessagesRequest(peer=channel_entity, id=[msg_id]))

    dt_msk = target.date.astimezone(MSK)
    print(f"OK: post ID {msg_id} deleted (was scheduled for {dt_msk.strftime('%d %B %Y %H:%M')} MSK)")


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    # --list
    if args[0] == '--list':
        channel = require_channel(args[1] if len(args) > 1 else DEFAULT_CHANNEL)
        cmd_list(channel)

    # --edit <id> "text" [@channel]
    elif args[0] == '--edit':
        if len(args) < 3:
            print("Usage: send.py --edit <id> \"New text\" [@channel]")
            sys.exit(1)
        msg_id = int(args[1])
        new_text = args[2]
        channel = require_channel(args[3] if len(args) > 3 else DEFAULT_CHANNEL)
        cmd_edit(msg_id, new_text, channel)

    # --delete <id> [@channel]
    elif args[0] == '--delete':
        if len(args) < 2:
            print("Usage: send.py --delete <id> [@channel]")
            sys.exit(1)
        msg_id = int(args[1])
        channel = require_channel(args[2] if len(args) > 2 else DEFAULT_CHANNEL)
        cmd_delete(msg_id, channel)

    # --file <path> "date" [@channel]
    elif args[0] == '--file':
        if len(args) < 3:
            print("Usage: send.py --file <path> \"YYYY-MM-DD HH:MM\" [@channel]")
            sys.exit(1)
        with open(args[1], 'r', encoding='utf-8') as f:
            text = f.read().strip()
        dt_str = args[2]
        channel = require_channel(args[3] if len(args) > 3 else DEFAULT_CHANNEL)
        if not text:
            print("Error: file is empty")
            sys.exit(1)
        cmd_send(text, dt_str, channel)

    # "text" "date" [@channel]
    else:
        if len(args) < 2:
            print("Usage: send.py \"Text\" \"YYYY-MM-DD HH:MM\" [@channel]")
            sys.exit(1)
        text = args[0]
        dt_str = args[1]
        channel = require_channel(args[2] if len(args) > 2 else DEFAULT_CHANNEL)
        cmd_send(text, dt_str, channel)


if __name__ == '__main__':
    main()
