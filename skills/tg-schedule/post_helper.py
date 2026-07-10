"""
Helper for sending formatted posts to Telegram via Telethon.

Usage:
    from post_helper import TgPost

    post = TgPost("@your_channel")   # or TgPost() with TG_CHANNEL set in .env
    post.text = "..."
    post.bold("Title")
    post.italic("accent")
    post.code("code")
    post.spoiler("hidden text")
    post.link("link text", "https://t.me/your_channel")
    post.send()                          # immediately
    post.send(schedule="2026-03-10 18:30")  # scheduled (MSK)
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(level=logging.CRITICAL)
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntitySpoiler, MessageEntityTextUrl, MessageEntityCustomEmoji,
    MessageEntityUnderline, MessageEntityStrike,
)

SKILL_DIR = Path(__file__).parent
load_dotenv(SKILL_DIR / '.env')

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
SESSION = str(SKILL_DIR / 'session')
DEFAULT_CHANNEL = os.environ.get('TG_CHANNEL', '')
MSK = timezone(timedelta(hours=3))

with open(SKILL_DIR / 'emoji_ids.json') as f:
    EMOJI_IDS = json.load(f)


def utf16_len(s: str) -> int:
    return len(s.encode('utf-16-le')) // 2


def utf16_offset(text: str, pos: int) -> int:
    return utf16_len(text[:pos])


def find_emoji_entities(text: str) -> list:
    """Automatically finds all animated emoji in text and creates entities."""
    entities = []
    i = 0
    utf16_pos = 0
    while i < len(text):
        matched = None
        for length in [4, 3, 2, 1]:
            chunk = text[i:i+length]
            if chunk in EMOJI_IDS:
                matched = (chunk, length)
                break
        if matched:
            emoji_char, char_len = matched
            ul = utf16_len(emoji_char)
            entities.append(MessageEntityCustomEmoji(
                offset=utf16_pos, length=ul,
                document_id=EMOJI_IDS[emoji_char]
            ))
            utf16_pos += ul
            i += char_len
        else:
            utf16_pos += utf16_len(text[i])
            i += 1
    return entities


class TgPost:
    def __init__(self, channel: str = None):
        self.channel = channel or DEFAULT_CHANNEL
        if not self.channel:
            raise ValueError(
                "No channel: pass TgPost('@your_channel') "
                "or set TG_CHANNEL in .env next to this script")
        self.text = ''
        self._entities = []

    def _add(self, entity_cls, substring: str, **kwargs):
        idx = self.text.find(substring)
        if idx == -1:
            raise ValueError(f"Substring not found in text: {repr(substring)}")
        off = utf16_offset(self.text, idx)
        length = utf16_len(substring)
        self._entities.append(entity_cls(offset=off, length=length, **kwargs))
        return self

    def bold(self, s: str):
        return self._add(MessageEntityBold, s)

    def italic(self, s: str):
        return self._add(MessageEntityItalic, s)

    def code(self, s: str):
        return self._add(MessageEntityCode, s)

    def underline(self, s: str):
        return self._add(MessageEntityUnderline, s)

    def strike(self, s: str):
        return self._add(MessageEntityStrike, s)

    def spoiler(self, s: str):
        return self._add(MessageEntitySpoiler, s)

    def link(self, s: str, url: str):
        return self._add(MessageEntityTextUrl, s, url=url)

    def _build_entities(self):
        return self._entities + find_emoji_entities(self.text)

    def preview(self):
        """Prints list of all entities for verification."""
        entities = self._build_entities()
        print(f"Text ({len(self.text)} chars):")
        print(self.text)
        print(f"\nEntities ({len(entities)}):")
        for e in entities:
            name = type(e).__name__.replace('MessageEntity', '')
            if hasattr(e, 'document_id'):
                chunk = self.text.encode('utf-16-le')[e.offset*2:(e.offset+e.length)*2].decode('utf-16-le')
                print(f"  {name}: {repr(chunk)} id={e.document_id}")
            elif hasattr(e, 'url'):
                chunk = self.text.encode('utf-16-le')[e.offset*2:(e.offset+e.length)*2].decode('utf-16-le')
                print(f"  {name}: {repr(chunk)} → {e.url}")
            else:
                chunk = self.text.encode('utf-16-le')[e.offset*2:(e.offset+e.length)*2].decode('utf-16-le')
                print(f"  {name}: {repr(chunk)}")

    def _validate(self):
        """Checks text for typical style errors. Raises ValueError if critical issues found."""
        errors = []
        if '\u2014' in self.text:
            count = self.text.count('\u2014')
            lines = [l.strip() for l in self.text.splitlines() if '\u2014' in l]
            errors.append(
                f"STOP. Em dash (\u2014): {count} found.\n"
                f"   This is the main AI marker — immediately obvious the text is model-generated.\n"
                f"   Replace with colon, comma, or just remove:\n   " +
                "\n   ".join(lines)
            )
        if errors:
            raise ValueError("\n\n".join(errors))

    def send(self, schedule: str = None, delay: int = 10):
        """
        schedule: string "YYYY-MM-DD HH:MM" in MSK, or None for immediate send.
        delay: delay in seconds after sending (default 10 sec, FloodWait protection).
               Pass delay=0 if sending a single post.
        """
        self._validate()
        entities = self._build_entities()
        dt = None
        if schedule:
            dt = datetime.strptime(schedule, "%Y-%m-%d %H:%M").replace(tzinfo=MSK)
            now = datetime.now(tz=timezone.utc)
            if (dt.timestamp() - now.timestamp()) < 600:
                raise ValueError(f"Time must be at least 10 minutes in the future: {dt}")

        with TelegramClient(SESSION, API_ID, API_HASH) as client:
            client.send_message(self.channel, self.text,
                                formatting_entities=entities,
                                schedule=dt)

        if dt:
            print(f"OK: scheduled for {dt.strftime('%d %B %Y %H:%M')} MSK → {self.channel}")
        else:
            print(f"OK: sent → {self.channel}")

        if delay > 0:
            time.sleep(delay)
