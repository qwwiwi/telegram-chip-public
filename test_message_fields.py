"""Offline test: GET /chats/{id}/messages/{id} exposes `out` and `sender_id` (fake Telethon client).

No real Telegram calls. Run: .venv/bin/python -m unittest test_message_fields -v
"""

import asyncio
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from telethon.tl.types import User

import api
import telegram_core as tc


class FakeClient:
    def __init__(self, message):
        self.message = message

    async def get_entity(self, cid):
        return User(id=int(cid), first_name="u", access_hash=1)

    async def get_messages(self, entity, ids=None):
        return self.message


def _message(out: bool, sender_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        out=out,
        sender_id=sender_id,
        sender=SimpleNamespace(first_name="Ivan", last_name=""),
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        message="hi",
        reply_to=None,
        media=None,
        views=None,
        forwards=None,
        reactions=None,
        entities=None,
    )


class MessageFieldsTests(unittest.TestCase):
    def _get(self, message):
        t = tc.telegram
        t.client = FakeClient(message)
        t._started = True
        t._last_request_time = None
        t._rate_lock = asyncio.Lock()
        t.min_request_delay = 0.0
        try:
            r = TestClient(api.app).get("/chats/1/messages/7")
        finally:
            t.min_request_delay = 0.2
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["success"], body)
        data = body["data"]
        return json.loads(data) if isinstance(data, str) else data

    def test_incoming_message(self):
        data = self._get(_message(out=False, sender_id=42))
        self.assertIs(data["out"], False)
        self.assertEqual(data["sender_id"], 42)

    def test_outgoing_message(self):
        data = self._get(_message(out=True, sender_id=99))
        self.assertIs(data["out"], True)
        self.assertEqual(data["sender_id"], 99)


if __name__ == "__main__":
    unittest.main()
