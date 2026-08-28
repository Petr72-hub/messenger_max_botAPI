from __future__ import annotations

from typing import Any

from maxgram.dispatcher.middlewares.base import BaseMiddleware, NextMiddleware
from maxgram.fsm.context import FSMContext
from maxgram.fsm.storage.base import BaseStorage, StorageKey


class UserContextMiddleware(BaseMiddleware):
    """Publishes ``event_from_user`` / ``event_chat_id`` for every event type."""

    async def __call__(
        self, handler: NextMiddleware, event: Any, data: dict[str, Any]
    ) -> Any:
        user = (
            getattr(event, "from_user", None)
            or getattr(event, "sender", None)
            or getattr(event, "user", None)
        )
        if user is None:
            message = getattr(event, "message", None)
            user = getattr(message, "sender", None) if message is not None else None

        data["event_from_user"] = user
        data["event_chat_id"] = _chat_id_of(event)
        return await handler(event, data)


class FSMContextMiddleware(BaseMiddleware):
    """Builds the per-conversation :class:`FSMContext` and injects it as ``state``."""

    def __init__(self, storage: BaseStorage, *, isolate_events: bool = False) -> None:
        self.storage = storage
        self.isolate_events = isolate_events

    async def __call__(
        self, handler: NextMiddleware, event: Any, data: dict[str, Any]
    ) -> Any:
        bot = data.get("bot")
        user = data.get("event_from_user")
        chat_id = data.get("event_chat_id")
        bot_id = getattr(getattr(bot, "_me", None), "user_id", 0) or 0

        key = StorageKey(
            bot_id=bot_id,
            chat_id=chat_id,
            user_id=getattr(user, "user_id", None),
        )
        context = FSMContext(storage=self.storage, key=key)
        data["state"] = context
        data["raw_state"] = await context.get_state()
        return await handler(event, data)


def _chat_id_of(event: Any) -> int | None:
    chat_id = getattr(event, "chat_id", None)
    if isinstance(chat_id, int):
        return chat_id
    message = getattr(event, "message", None)
    if message is not None:
        recipient = getattr(message, "recipient", None)
        if recipient is not None:
            return getattr(recipient, "chat_id", None)
    chat = getattr(event, "chat", None)
    if chat is not None:
        return getattr(chat, "chat_id", None)
    return None
