#!/usr/bin/env python3
"""
One-time Telethon authorization for tg-dialogs.
Run: python3 auth.py
Enter your phone number and the code from Telegram.

If the tg-schedule skill is installed next to this one and already has an
authorized session, this step is not needed — the session is shared.
"""
import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient

SKILL_DIR = os.path.dirname(os.path.realpath(__file__))
load_dotenv(os.path.join(SKILL_DIR, '.env'))

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']

_shared = os.path.join(os.path.dirname(SKILL_DIR), 'tg-schedule', 'session')
SESSION = os.environ.get('TG_SESSION_PATH') or (
    _shared if os.path.exists(_shared + '.session')
    else os.path.join(SKILL_DIR, 'session')
)

with TelegramClient(SESSION, API_ID, API_HASH) as client:
    me = client.get_me()
    print(f'Authorized: {me.first_name} @{me.username}')
    print(f'Session saved to {SESSION}.session. You can close this.')
