import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from deep_translator import GoogleTranslator

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

SOURCE_CHAT_IDS = [
    -1001343549608,
    -1002013156572,
    -1001390922266,
    -1001999527634,
    -1001002338106,
    -1001346732056,
    -1001613270320,
    -1003388885861,
    -1002341229291,
    -1001115993302,
    -1002574501524,
    -1001906054294,
]

TARGET_CHAT_ID = -1004268679605

executor = ThreadPoolExecutor(max_workers=2)

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
    connection_retries=None,
    retry_delay=5,
    auto_reconnect=True,
)

_summary_entries = []
_summary_lock = asyncio.Lock()


def _translate_sync(text):
    try:
        result = GoogleTranslator(source="auto", target="en").translate(text)
        if result and result.strip().lower() != text.strip().lower():
            return result
    except Exception as e:
        print(f"[TRANSLATE ERROR] {e}")
    return None


@client.on(events.NewMessage())
async def handler(event):
    chat_id = event.chat_id
    if chat_id not in SOURCE_CHAT_IDS:
        return

    try:
        forwarded = await client.forward_messages(TARGET_CHAT_ID, event.message)
        print(f"[OK] Forwarded from {chat_id}")
    except Exception as e:
        print(f"[ERROR] Forward failed: {e}")
        return

    text = event.message.text or event.message.caption
    translation = None
    if text and text.strip():
        try:
            loop = asyncio.get_event_loop()
            translation = await loop.run_in_executor(executor, _translate_sync, text)
            if translation:
                fwd_msg = forwarded[0] if isinstance(forwarded, list) else forwarded
                await client.send_message(
                    TARGET_CHAT_ID,
                    f"English: {translation}",
                    reply_to=fwd_msg.id,
                )
                print(f"[OK] Sent translation as reply")
        except Exception as e:
            print(f"[ERROR] Translation failed: {e}")

    if text and text.strip():
        async with _summary_lock:
            _summary_entries.append(
                (datetime.utcnow(), chat_id, text, translation)
            )


async def hourly_summary():
    """
    Send a pinned summary at :05 past every hour.
    Format: English translation first, then Arabic below, entries separated by blank line.
    """
    # Calculate the first trigger time (next :05)
    now = datetime.utcnow()
    if now.minute < 5:
        next_run = now.replace(minute=5, second=0, microsecond=0)
    else:
        next_run = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)
    await asyncio.sleep((next_run - datetime.utcnow()).total_seconds())

    while True:
        async with _summary_lock:
            entries = _summary_entries[:]
            _summary_entries.clear()

        if entries:
            # Build lines with blank line separation between each entry
            lines = [" Hourly Summary\n"]  # Add an extra newline for spacing below header
            for i, (ts, chat_id, text, translation) in enumerate(entries):
                if translation:
                    en_text = (translation[:200] + "…") if len(translation) > 200 else translation
                    orig_text = (text[:100] + "…") if len(text) > 100 else text
                    entry_str = f"• {en_text}\n  {orig_text}"
                else:
                    orig_text = (text[:200] + "…") if len(text) > 200 else text
                    entry_str = f"• {orig_text}"

                lines.append(entry_str)
                # Add a blank line after each entry except the last one
                if i < len(entries) - 1:
                    lines.append("")

            msg_text = "\n".join(lines)

            try:
                sent_msg = await client.send_message(TARGET_CHAT_ID, msg_text)
                await client.pin_message(TARGET_CHAT_ID, sent_msg.id, notify=False)
                print("[SUMMARY] Hourly summary sent and pinned")
            except Exception as e:
                print(f"[SUMMARY ERROR] {e}")

        next_run += timedelta(hours=1)
        sleep_seconds = (next_run - datetime.utcnow()).total_seconds()
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)


async def keepalive():
    while True:
        await asyncio.sleep(60)
        try:
            await client.get_me()
            print("[PING] alive")
        except Exception as e:
            print(f"[PING ERROR] {e}")


async def main():
    await client.start()
    me = await client.get_me()
    print(f"[ONLINE] Logged in as {me.first_name} (@{me.username})")
    print(f"Watching {len(SOURCE_CHAT_IDS)} chats → {TARGET_CHAT_ID}")
    asyncio.create_task(keepalive())
    asyncio.create_task(hourly_summary())
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
