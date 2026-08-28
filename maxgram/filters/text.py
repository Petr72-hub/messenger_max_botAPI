from __future__ import annotations

import re
from typing import Any, Pattern, Sequence

from maxgram.filters.base import Filter, FilterResult


def _text_of(event: Any) -> str | None:
    text = getattr(event, "text", None)
    if isinstance(text, str):
        return text
    data = getattr(event, "data", None)
    if isinstance(data, str):
        return data
    message = getattr(event, "message", None)
    if message is not None:
        inner = getattr(message, "text", None)
        if isinstance(inner, str):
            return inner
    return None


class Text(Filter):
    """Exact / prefix / suffix / substring match on the event text."""

    def __init__(
        self,
        text: str | Sequence[str] | None = None,
        *,
        startswith: str | Sequence[str] | None = None,
        endswith: str | Sequence[str] | None = None,
        contains: str | Sequence[str] | None = None,
        ignore_case: bool = False,
    ) -> None:
        if all(v is None for v in (text, startswith, endswith, contains)):
            raise ValueError("Text() needs one of text/startswith/endswith/contains")
        self.ignore_case = ignore_case
        self.text = _as_tuple(text, ignore_case)
        self.startswith = _as_tuple(startswith, ignore_case)
        self.endswith = _as_tuple(endswith, ignore_case)
        self.contains = _as_tuple(contains, ignore_case)

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        value = _text_of(event)
        if value is None:
            return False
        if self.ignore_case:
            value = value.lower()
        if self.text and value in self.text:
            return True
        if self.startswith and value.startswith(self.startswith):
            return True
        if self.endswith and value.endswith(self.endswith):
            return True
        if self.contains and any(part in value for part in self.contains):
            return True
        return False


class Regexp(Filter):
    """Regular-expression match; the :class:`re.Match` lands in ``match``."""

    def __init__(self, pattern: str | Pattern[str], *, search: bool = True) -> None:
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.search = search

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        value = _text_of(event)
        if value is None:
            return False
        match = self.pattern.search(value) if self.search else self.pattern.match(value)
        return {"match": match} if match else False


class ContentType(Filter):
    """Match on the first attachment kind, or ``"text"`` for plain messages."""

    def __init__(self, *types: str) -> None:
        self.types = {str(t) for t in types}

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        message = event if hasattr(event, "content_type") else getattr(event, "message", None)
        if message is None:
            return False
        return getattr(message, "content_type", None) in self.types


class HasAttachment(Filter):
    """True when the message carries at least one attachment of the given kinds."""

    def __init__(self, *types: str) -> None:
        self.types = {str(t) for t in types}

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        message = event if hasattr(event, "attachments") else getattr(event, "message", None)
        attachments = getattr(message, "attachments", None) or []
        if not attachments:
            return False
        if not self.types:
            return True
        return any(str(getattr(a, "type", "")) in self.types for a in attachments)


def _as_tuple(value: str | Sequence[str] | None, ignore_case: bool) -> tuple[str, ...]:
    if value is None:
        return ()
    items = (value,) if isinstance(value, str) else tuple(value)
    return tuple(i.lower() for i in items) if ignore_case else items
