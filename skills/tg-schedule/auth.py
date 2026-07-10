#!/usr/bin/env python3
"""
One-time Telethon authorization.
Run: python3 auth.py
Enter your phone number and the code from Telegram.
The session will be saved to session.session — won't be needed again.
"""
import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

API_ID = int(os.environ['TG_API_ID'])
API_HASH = os.environ['TG_API_HASH']
SESSION = os.path.join(os.path.dirname(__file__), 'session')

with TelegramClient(SESSION, API_ID, API_HASH) as client:
    me = client.get_me()
    print(f'Authorized: {me.first_name} @{me.username}')
    print('Session saved. You can close this.')
