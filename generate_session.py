from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 23136643               # your numeric API ID (from my.telegram.org)
API_HASH = "3296b8bbde6074a51be1eba7d294f985"     # your API hash (a string)
PHONE = "+40720868344"          # your phone number with country code


print("Connecting to Telegram...")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    client.start(phone=PHONE)
    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("SUCCESS! Copy the line below and save it as the")
    print("SESSION_STRING secret in Railway.")
    print("=" * 60)
    print(session_string)
    print("=" * 60 + "\n")
