"""LIVE diagnostic (needs network and real credentials in .env): checks whether the account is under FloodWait.

Not a unit test: it only runs via `python test_floodwait.py`. Importing it (unittest discovery) does nothing.
"""

import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession


async def check() -> None:
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    session_string = os.environ["TELEGRAM_SESSION_STRING"]

    print("Connecting...")
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    await client.connect()
    print("Connected!")

    try:
        print("Getting dialogs...")
        dialogs = await client.get_dialogs()
        print(f"Got {len(dialogs)} dialogs")
    except FloodWaitError as e:
        print(f"FloodWait: need to wait {e.seconds} seconds")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(check())
