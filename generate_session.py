import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
PHONE = os.environ["PHONE"]

print("Connecting to Telegram...")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    client.start(phone=PHONE)
    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("SUCCESS! Copy the line below and save it as the")
    print("SESSION_STRING secret in Replit.")
    print("=" * 60)
    print(session_string)
    print("=" * 60 + "\n")
