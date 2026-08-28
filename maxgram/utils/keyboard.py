"""Fluent keyboard construction, in the spirit of ``aiogram.utils.keyboard``."""

from __future__ import annotations

from typing import Any, Iterable, Self

from maxgram.enums import Intent
from maxgram.types.keyboard import (
    AnyButton,
    CallbackButton,
    ChatButton,
    InlineKeyboardMarkup,
    LinkButton,
    MessageButton,
    RequestContactButton,
    RequestGeoLocationButton,
)


class InlineKeyboardBuilder:
    """Collect buttons, then lay them out into rows.

    ::

        kb = InlineKeyboardBuilder()
        kb.button(text="Yes", payload="vote:yes", intent=Intent.POSITIVE)
        kb.button(text="No", payload="vote:no", intent=Intent.NEGATIVE)
        kb.url("Source", "https://example.com")
        kb.adjust(2, 1)
        await message.answer("Vote?", reply_markup=kb.as_markup())
    """

    def __init__(self, markup: Iterable[Iterable[AnyButton]] | None = None) -> None:
        self._rows: list[list[AnyButton]] = [list(row) for row in markup] if markup else []
        self._pending: list[AnyButton] = []

    # -- adding ---------------------------------------------------------------

    def add(self, *buttons: AnyButton) -> Self:
        self._pending.extend(buttons)
        return self

    def button(
        self,
        *,
        text: str,
        payload: str | None = None,
        url: str | None = None,
        intent: Intent | str = Intent.DEFAULT,
        **kwargs: Any,
    ) -> Self:
        """Add a callback button, or a link button when ``url`` is given."""
        if url is not None:
            return self.add(LinkButton(text=text, url=url, **kwargs))
        if payload is None:
            raise ValueError("a callback button needs a payload")
        return self.add(CallbackButton(text=text, payload=payload, intent=Intent(intent)))

    def url(self, text: str, url: str) -> Self:
        return self.add(LinkButton(text=text, url=url))

    def request_contact(self, text: str) -> Self:
        return self.add(RequestContactButton(text=text))

    def request_location(self, text: str, *, quick: bool = False) -> Self:
        return self.add(RequestGeoLocationButton(text=text, quick=quick))

    def open_chat(self, text: str, *, title: str | None = None, **kwargs: Any) -> Self:
        return self.add(ChatButton(text=text, chat_title=title, **kwargs))

    def message(self, text: str) -> Self:
        return self.add(MessageButton(text=text))

    # -- layout ---------------------------------------------------------------

    def row(self, *buttons: AnyButton) -> Self:
        """Flush pending buttons, then append these as their own row."""
        self._flush()
        if buttons:
            self._rows.append(list(buttons))
        return self

    def adjust(self, *sizes: int, repeat_last: bool = True) -> Self:
        """Reflow every button into rows of the given widths."""
        buttons = [b for row in self._rows for b in row] + self._pending
        self._rows, self._pending = [], []
        if not sizes:
            sizes = (1,)

        index = 0
        size_index = 0
        while index < len(buttons):
            size = sizes[min(size_index, len(sizes) - 1)] if repeat_last else sizes[size_index % len(sizes)]
            size = max(1, size)
            self._rows.append(buttons[index : index + size])
            index += size
            size_index += 1
        return self

    def _flush(self) -> None:
        if self._pending:
            self._rows.append(self._pending)
            self._pending = []

    def as_markup(self) -> InlineKeyboardMarkup:
        self._flush()
        return InlineKeyboardMarkup(buttons=self._rows)

    def export(self) -> list[list[AnyButton]]:
        self._flush()
        return self._rows

    def __len__(self) -> int:
        return sum(len(row) for row in self._rows) + len(self._pending)


def inline_keyboard(*rows: Iterable[AnyButton]) -> InlineKeyboardMarkup:
    """One-liner for a static keyboard."""
    return InlineKeyboardMarkup(buttons=[list(row) for row in rows])
