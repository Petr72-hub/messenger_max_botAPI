from __future__ import annotations

from typing import Any

import pytest

from maxgram import Bot
from maxgram.client.session import BaseSession


class FakeSession(BaseSession):
    """Records outgoing calls and replays canned answers."""

    def __init__(self, responses: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None, Any]] = []
        self.responses = responses or {}

    async def request(self, method, path, *, params=None, json_body=None):
        self.calls.append((method, path, dict(params or {}), json_body))
        key = f"{method} {path}"
        if key in self.responses:
            return self.responses[key]
        if path == "/me":
            return {"user_id": 1, "first_name": "TestBot", "username": "testbot", "is_bot": True}
        if path == "/messages" and method == "POST":
            return {
                "message": {
                    "recipient": {"chat_id": params.get("chat_id"), "chat_type": "chat"},
                    "timestamp": 1,
                    "body": {"mid": "mid.sent", "seq": 1, "text": (json_body or {}).get("text")},
                }
            }
        return {"success": True}

    async def close(self) -> None:
        return None


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


@pytest.fixture
def bot(session: FakeSession) -> Bot:
    return Bot("test-token", session=session)


def message_update(text: str, *, chat_id: int = 100, user_id: int = 42) -> dict[str, Any]:
    return {
        "update_type": "message_created",
        "timestamp": 1700000000000,
        "message": {
            "sender": {"user_id": user_id, "first_name": "Ann", "username": "ann"},
            "recipient": {"chat_id": chat_id, "chat_type": "chat"},
            "timestamp": 1700000000000,
            "body": {"mid": "mid.1", "seq": 1, "text": text},
        },
    }


def callback_update(payload: str, *, chat_id: int = 100) -> dict[str, Any]:
    return {
        "update_type": "message_callback",
        "timestamp": 1700000000000,
        "callback": {
            "timestamp": 1700000000000,
            "callback_id": "cb-1",
            "payload": payload,
            "user": {"user_id": 42, "first_name": "Ann"},
        },
        "message": {
            "recipient": {"chat_id": chat_id, "chat_type": "chat"},
            "timestamp": 1700000000000,
            "body": {"mid": "mid.2", "seq": 2, "text": "menu"},
        },
    }
