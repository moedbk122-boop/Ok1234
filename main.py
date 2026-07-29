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

# ---- NEW: storage for hourly summaries ----
_summary_entries = []          # list of (timestamp, chat_id, text, translation)
_summary_lock = asyncio.Lock() # optional, not strictly needed in a single-threaded event loop
# -------------------------------------------


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

    # ---- NEW: record the event for the hourly summary ----
    if text and text.strip():
        async with _summary_lock:
            _summary_entries.append(
                (datetime.utcnow(), chat_id, text, translation)
            )
    # ------------------------------------------------------


# ---- NEW: hourly summary task ----
async def hourly_summary():
    """
    Every full hour, collect all recorded events, format a clean summary,
    and send it to TARGET_CHAT_ID. Only sends if there are events.
    """
    # align first run to the next full hour
    now = datetime.utcnow()
    next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    await asyncio.sleep((next_run - now).total_seconds())

    while True:
        # snapshot and clear the list safely
        async with _summary_lock:
            entries = _summary_entries[:]
            _summary_entries.clear()

        if entries:
            lines = ["📋 Hourly Summary"]
            for ts, chat_id, text, translation in entries:
                # truncate original text to 100 chars
                snippet = (text[:100] + "…") if len(text) > 100 else text
                line = f"• [{chat_id}] {snippet}"
                if translation:
                    # show a short version of the translation
                    en = (translation[:50] + "…") if len(translation) > 50 else translation
                    line += f"  (EN: {en})"
                lines.append(line)
            msg = "\n".join(lines)
            try:
                await client.send_message(TARGET_CHAT_ID, msg)
                print("[SUMMARY] Hourly summary sent")
            except Exception as e:
                print(f"[SUMMARY ERROR] {e}")

        # schedule next run in exactly one hour
        next_run += timedelta(hours=1)
        now = datetime.utcnow()
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)
# -----------------------------------


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
    # ---- NEW: start the hourly summary task ----
    asyncio.create_task(hourly_summary())
    # --------------------------------------------
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
