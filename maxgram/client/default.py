from __future__ import annotations

from dataclasses import dataclass

from maxgram.enums import TextFormat


@dataclass(slots=True)
class DefaultBotProperties:
    """Values applied to every outgoing call unless overridden per request.

    Mirrors ``aiogram.client.default.DefaultBotProperties`` so muscle memory carries
    over: set ``parse_mode`` once at construction instead of on each ``send_message``.
    """

    parse_mode: TextFormat | str | None = None
    disable_link_preview: bool | None = None
    notify: bool | None = None
    protect_content: bool | None = None
