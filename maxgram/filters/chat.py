from __future__ import annotations

from typing import Any, Sequence

from maxgram.enums import ChatType
from maxgram.filters.base import Filter, FilterResult


def _chat_type_of(event: Any) -> str | None:
    value = getattr(event, "chat_type", None)
    if value is not None:
        return str(value)
    message = getattr(event, "message", None)
    if message is not None:
        inner = getattr(message, "chat_type", None)
        return str(inner) if inner is not None else None
    if getattr(event, "is_channel", None) is True:
        return str(ChatType.CHANNEL)
    return None


class ChatTypeFilter(Filter):
    """Restrict a handler to dialogs, group chats or channels."""

    def __init__(self, chat_type: str | ChatType | Sequence[str | ChatType]) -> None:
        types = [chat_type] if isinstance(chat_type, (str, ChatType)) else list(chat_type)
        self.types = {str(t) for t in types}

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        return _chat_type_of(event) in self.types


class IsDialog(ChatTypeFilter):
    def __init__(self) -> None:
        super().__init__(ChatType.DIALOG)


class IsChannel(ChatTypeFilter):
    def __init__(self) -> None:
        super().__init__(ChatType.CHANNEL)


class IsGroup(ChatTypeFilter):
    def __init__(self) -> None:
        super().__init__(ChatType.CHAT)


class IsAdmin(Filter):
    """Check the sender against a static allow-list of user ids."""

    def __init__(self, user_ids: Sequence[int]) -> None:
        self.user_ids = set(user_ids)

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        user = getattr(event, "from_user", None) or getattr(event, "sender", None)
        if user is None:
            user = getattr(event, "user", None)
        user_id = getattr(user, "user_id", None)
        return user_id in self.user_ids


class IsBot(Filter):
    """Match messages authored by bots (or, inverted, by humans)."""

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        user = getattr(event, "from_user", None) or getattr(event, "sender", None)
        return bool(getattr(user, "is_bot", False))
