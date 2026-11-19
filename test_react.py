"""Offline tests for POST /messages/react and its guard (fake Telethon client).

No real Telegram calls. Run: .venv/bin/python -m unittest test_react -v
"""

import asyncio
import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel, ChatPhotoEmpty, User

import api
import telegram_core as tc


def _user(uid, is_self=False, bot=False):
    return User(id=uid, is_self=is_self, bot=bot, first_name=f"u{uid}", access_hash=1)


def _channel(cid):
    return Channel(id=cid, title="g", photo=ChatPhotoEmpty(), date=None, megagroup=True, access_hash=1)


class FakeClient:
    def __init__(self, entities, messages):
        self.entities = entities  # chat_id -> entity
        self.messages = messages  # (chat id, message id) -> message
        self.requests = []
        self.flood_once = False

    async def get_entity(self, cid):
        if int(cid) not in self.entities:
            raise ValueError("Could not find the input entity")
        return self.entities[int(cid)]

    async def get_messages(self, entity, ids=None):
        return self.messages.get((entity.id, ids))

    async def __call__(self, request):
        if self.flood_once:
            self.flood_once = False
            raise FloodWaitError(request=None, capture=0)
        self.requests.append(request)
        return SimpleNamespace()


class ReactTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient(
            entities={1: _user(1), 3: _channel(3), 4: _user(4, is_self=True), 5: _user(5, bot=True)},
            messages={(1, 10): SimpleNamespace(id=10, out=False), (1, 11): SimpleNamespace(id=11, out=True),
                      (3, 10): SimpleNamespace(id=10, out=False)},
        )
        t = tc.telegram
        t.client = self.client
        t._started = True
        t._last_request_time = None
        t._rate_lock = asyncio.Lock()
        t._last_message_time_per_chat = {}
        t.min_request_delay = 0.0
        self.api = TestClient(api.app)

    def tearDown(self):
        tc.telegram.min_request_delay = 0.2

    def _refused(self, r, code):
        self.assertEqual(r.status_code, code, r.text)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertTrue(body["error"].startswith("reaction refused"), body)
        self.assertEqual(self.client.requests, [])

    def test_incoming_message_gets_fire_by_default(self):
        r = self.api.post("/messages/react", json={"chat_id": 1, "message_id": 10})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["success"], r.text)
        (req,) = self.client.requests
        self.assertEqual(req.msg_id, 10)
        self.assertEqual([x.emoticon for x in req.reaction], ["🔥"])
        self.assertEqual(req.peer.user_id, 1)

    def test_custom_emoji(self):
        r = self.api.post("/messages/react", json={"chat_id": "1", "message_id": 10, "emoji": "👍"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.client.requests[0].reaction[0].emoticon, "👍")

    def test_own_message_refused(self):
        self._refused(self.api.post("/messages/react", json={"chat_id": 1, "message_id": 11}), 403)

    def test_missing_message_refused(self):
        self._refused(self.api.post("/messages/react", json={"chat_id": 1, "message_id": 99}), 404)

    def test_no_dialog_refused(self):
        self._refused(self.api.post("/messages/react", json={"chat_id": 777, "message_id": 10}), 404)

    def test_groups_bots_and_saved_messages_refused(self):
        for cid in (3, 4, 5):
            self._refused(self.api.post("/messages/react", json={"chat_id": cid, "message_id": 10}), 403)

    def test_bad_input_rejected(self):
        self.assertEqual(self.api.post("/messages/react", json={"chat_id": 1, "message_id": 0}).status_code, 422)
        self.assertEqual(self.api.post("/messages/react", json={"chat_id": 1, "message_id": 10, "emoji": ""}).status_code, 422)
        self._refused(self.api.post("/messages/react", json={"chat_id": "a b", "message_id": 10}), 400)

    def test_flood_wait_retried_once(self):
        self.client.flood_once = True
        r = self.api.post("/messages/react", json={"chat_id": 1, "message_id": 10})
        self.assertTrue(r.json()["success"], r.text)
        self.assertEqual(len(self.client.requests), 1)


if __name__ == "__main__":
    unittest.main()
