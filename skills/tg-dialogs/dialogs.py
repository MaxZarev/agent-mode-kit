#!/usr/bin/env python3
"""
Telegram dialog operations via Telethon (async, Python 3.14-compatible).

Commands:
  dialogs.py --find "name or keyword"
  dialogs.py --list [--limit N]
  dialogs.py --read TARGET [--limit N] [--search WORD] [--since YYYY-MM-DD]
  dialogs.py --send TARGET "Message text"
  dialogs.py --pin ALIAS TARGET
  dialogs.py --aliases

TARGET is any of: alias, @username, phone (+79..), contact/group title
(partial match also works — the first unique fuzzy hit is auto-pinned as alias).

Paths:
  - The script itself resolves via os.path.realpath(__file__), so it works
    identically whether invoked through a project's symlinked skills folder
    or directly from skills-hub.
  - Aliases (tg-dialogs.aliases.json) live next to the nearest CLAUDE.md above
    CWD — each scope is self-contained, no inheritance. See SKILL.md for
    layout and fallback rules.
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient

logging.basicConfig(level=logging.CRITICAL)

SKILL_DIR = os.path.dirname(os.path.realpath(__file__))
SKILLS_HUB = os.path.dirname(SKILL_DIR)

load_dotenv(os.path.join(SKILL_DIR, '.env'))


def aliases_path() -> str:
    """Path to tg-dialogs.aliases.json next to the nearest CLAUDE.md above CWD.

    Walks up from CWD; the first directory containing CLAUDE.md is the scope.
    File lives as <scope>/tg-dialogs.aliases.json — no inheritance, each scope
    is self-contained. Override with env TG_ALIASES_PATH.

    Fallback if no CLAUDE.md found anywhere above CWD:
    ~/.claude/tg-dialogs/aliases.json.
    """
    override = os.environ.get('TG_ALIASES_PATH')
    if override:
        return os.path.abspath(override)
    d = os.path.abspath(os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')):
            return os.path.join(d, 'tg-dialogs.aliases.json')
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return os.path.expanduser('~/.claude/tg-dialogs/aliases.json')


def load_aliases() -> dict:
    path = aliases_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_aliases(data: dict) -> None:
    path = aliases_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def alias_key(target: str) -> str:
    return target.strip().lower().lstrip('@')


def entity_ref(entity) -> dict:
    """Stable identifier for an entity: prefers username, falls back to peer id."""
    username = getattr(entity, 'username', None)
    if username:
        return {'username': username}
    dtype = type(entity).__name__
    peer_id = entity.id
    if dtype == 'Channel':
        peer_id = int(f'-100{entity.id}')
    return {'peer_id': peer_id}


def entity_name(entity) -> str:
    return (
        getattr(entity, 'title', None)
        or (getattr(entity, 'first_name', '') + ' ' + (getattr(entity, 'last_name', '') or ''))
    ).strip()

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
# Session file is shared with the tg-schedule skill when it is installed next
# to this one; otherwise a session in this skill's own dir is used.
# Override via TG_SESSION_PATH.
_SHARED_SESSION = os.path.join(SKILLS_HUB, 'tg-schedule', 'session')
SESSION = os.environ.get('TG_SESSION_PATH') or (
    _SHARED_SESSION if os.path.exists(_SHARED_SESSION + '.session')
    else os.path.join(SKILL_DIR, 'session')
)
MSK = timezone(timedelta(hours=3))


def make_client() -> TelegramClient:
    return TelegramClient(SESSION, API_ID, API_HASH)


class EntityNotFound(Exception):
    """Raised when --read/--send target can't be resolved unambiguously."""


async def _fuzzy_find(client, target: str):
    """Return list of dialogs whose name/username contains target substring."""
    q = target.lower().lstrip('@')
    matches = []
    async for d in client.iter_dialogs():
        name = (d.name or '').lower()
        username = (getattr(d.entity, 'username', None) or '').lower()
        if q in name or q in username:
            matches.append(d)
    return matches


async def resolve_entity(client, target: str, auto_pin: bool = True):
    """Resolve a target to a Telegram entity.

    Resolution order:
      1. Alias lookup (scope-local tg-dialogs.aliases.json).
      2. Direct `client.get_entity(target)` — fast path for @username/phone/exact name.
      3. Fuzzy substring match across `iter_dialogs`. If exactly 1 match and
         auto_pin=True, the alias is saved for next time.

    Raises EntityNotFound on 0 or >1 fuzzy matches.
    """
    aliases = load_aliases()
    key = alias_key(target)

    if key in aliases:
        entry = aliases[key]
        ref = entry.get('username') or entry.get('peer_id')
        if ref is not None:
            try:
                return await client.get_entity(f'@{ref}' if isinstance(ref, str) else ref)
            except (ValueError, TypeError):
                pass  # stale alias — fall through and re-resolve

    try:
        return await client.get_entity(target)
    except (ValueError, TypeError):
        pass

    matches = await _fuzzy_find(client, target)

    if len(matches) == 1:
        entity = matches[0].entity
        if auto_pin:
            aliases[key] = {**entity_ref(entity), 'name': entity_name(entity)}
            save_aliases(aliases)
            print(f'[pinned "{key}" → {entity_name(entity)} in {aliases_path()}]')
        return entity

    if not matches:
        print(f'No dialog found for "{target}".')
        print(f'Tip: run `--find "{target}"` to search across all dialogs.')
        raise EntityNotFound(target)

    print(f'Ambiguous target "{target}" — {len(matches)} matches:\n')
    for d in matches:
        print(f'  • {format_dialog(d)}')
    print('\nPass a more specific name (e.g. the full title) or an @username.')
    raise EntityNotFound(target)


def format_dialog(d) -> str:
    dtype = type(d.entity).__name__
    label = {
        'User': 'personal',
        'Chat': 'group',
        'Channel': 'channel/supergroup',
    }.get(dtype, dtype)
    username = getattr(d.entity, 'username', None)
    u = f' @{username}' if username else ''
    unread = f' [{d.unread_count} unread]' if d.unread_count else ''
    return f"{d.name}{u} — {label}{unread}"


async def cmd_find(query: str) -> None:
    q = query.lower().lstrip('@')
    results = []
    async with make_client() as client:
        async for d in client.iter_dialogs():
            name_match = q in (d.name or '').lower()
            username = getattr(d.entity, 'username', None) or ''
            username_match = q in username.lower()
            if name_match or username_match:
                results.append(d)

    if not results:
        print(f'No dialogs matching "{query}" found.')
        return

    print(f'Found {len(results)} dialog(s) for "{query}":\n')
    for d in results:
        print(f'  • {format_dialog(d)}')


async def cmd_list(limit: int = 50) -> None:
    dialogs = []
    async with make_client() as client:
        async for d in client.iter_dialogs(limit=limit):
            dialogs.append(d)

    print(f'Last {len(dialogs)} dialogs:\n')
    for d in dialogs:
        print(f'  • {format_dialog(d)}')


async def cmd_read(target: str, limit: int = 30, search: str | None = None, since: str | None = None) -> None:
    since_dt = None
    if since:
        since_dt = datetime.strptime(since, '%Y-%m-%d').replace(tzinfo=MSK)

    async with make_client() as client:
        try:
            entity = await resolve_entity(client, target)
        except EntityNotFound:
            return
        name = (
            getattr(entity, 'title', None)
            or (getattr(entity, 'first_name', '') + ' ' + (getattr(entity, 'last_name', '') or ''))
        ).strip()

        kwargs = {'limit': limit}
        if search:
            kwargs['search'] = search
        msgs = await client.get_messages(entity, **kwargs)

    if since_dt:
        msgs = [m for m in msgs if m.date and m.date.astimezone(MSK) >= since_dt]

    if not msgs:
        desc = f'matching "{search}"' if search else ''
        print(f'No messages {desc} found in "{name}".')
        return

    print(f'Messages from "{name}" ({len(msgs)} total):\n')
    for m in reversed(msgs):
        dt = m.date.astimezone(MSK).strftime('%d.%m %H:%M') if m.date else '?'
        sender_tag = ''
        s = getattr(m, 'sender', None)
        if s:
            who = getattr(s, 'username', None) or getattr(s, 'first_name', '') or ''
            if who:
                sender_tag = f' [{who}]'
        text = (m.text or '[media/file]').replace('\n', ' ')
        print(f'  {dt}{sender_tag}: {text}')


async def cmd_pin(alias: str, target: str) -> None:
    async with make_client() as client:
        try:
            entity = await resolve_entity(client, target, auto_pin=False)
        except EntityNotFound:
            return
        aliases = load_aliases()
        aliases[alias_key(alias)] = {**entity_ref(entity), 'name': entity_name(entity)}
        save_aliases(aliases)
    print(f'Pinned "{alias_key(alias)}" → {entity_name(entity)} in {aliases_path()}')


def cmd_aliases() -> None:
    path = aliases_path()
    aliases = load_aliases()
    if not aliases:
        print(f'No aliases in {path}')
        return
    print(f'Aliases from {path}:\n')
    for k, v in sorted(aliases.items()):
        ref = v.get('username')
        ref = f'@{ref}' if ref else v.get('peer_id')
        print(f'  {k} → {v.get("name", "?")} [{ref}]')


async def cmd_send(target: str, text: str) -> None:
    async with make_client() as client:
        try:
            entity = await resolve_entity(client, target)
        except EntityNotFound:
            return
        name = getattr(entity, 'title', None) or getattr(entity, 'first_name', '')
        await client.send_message(entity, text)

    print(f'OK: message sent to "{name}"')
    print(f'Text: {text[:80]}{"..." if len(text) > 80 else ""}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Telegram dialog operations')
    parser.add_argument('--find', metavar='QUERY', help='Find dialogs by name')
    parser.add_argument('--list', action='store_true', help='List dialogs')
    parser.add_argument('--read', metavar='TARGET', help='Read messages (alias, name, @username, phone number)')
    parser.add_argument('--send', nargs=2, metavar=('TARGET', 'TEXT'), help='Send a message')
    parser.add_argument('--pin', nargs=2, metavar=('ALIAS', 'TARGET'), help='Pin alias → target (saved to scope-local tg-dialogs.aliases.json)')
    parser.add_argument('--aliases', action='store_true', help='List aliases in current scope')
    parser.add_argument('--scope', metavar='DIR', help='Override alias scope: use DIR/tg-dialogs.aliases.json instead of auto-detecting via CLAUDE.md')
    parser.add_argument('--limit', type=int, default=30, help='Message/dialog limit (default 30)')
    parser.add_argument('--search', metavar='KEYWORD', help='Search by text within dialog')
    parser.add_argument('--since', metavar='DATE', help='Messages since date (YYYY-MM-DD)')

    args = parser.parse_args()

    if args.scope:
        os.environ['TG_ALIASES_PATH'] = os.path.join(os.path.abspath(args.scope), 'tg-dialogs.aliases.json')

    if args.find:
        asyncio.run(cmd_find(args.find))
    elif args.list:
        asyncio.run(cmd_list(limit=args.limit))
    elif args.read:
        asyncio.run(cmd_read(args.read, limit=args.limit, search=args.search, since=args.since))
    elif args.send:
        asyncio.run(cmd_send(args.send[0], args.send[1]))
    elif args.pin:
        asyncio.run(cmd_pin(args.pin[0], args.pin[1]))
    elif args.aliases:
        cmd_aliases()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
