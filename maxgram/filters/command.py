from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Pattern, Sequence

from maxgram.filters.base import Filter, FilterResult

DEFAULT_PREFIXES = "/"


@dataclass(slots=True)
class CommandObject:
    """Parsed command, injected into handlers as ``command``."""

    prefix: str
    command: str
    mention: str | None = None
    args: str | None = None

    @property
    def text(self) -> str:
        parts = [f"{self.prefix}{self.command}"]
        if self.mention:
            parts[0] += f"@{self.mention}"
        if self.args:
            parts.append(self.args)
        return " ".join(parts)

    def arg_list(self) -> list[str]:
        return self.args.split() if self.args else []


@dataclass(slots=True)
class CommandStart:
    """Marker for ``/start`` with an optional deep-link payload."""

    deep_link: str | None = None


class Command(Filter):
    """Match ``/command`` at the start of the message text.

    Accepts plain names, other names as aliases, or compiled regular expressions::

        @router.message(Command("start", "help"))
        @router.message(Command(re.compile(r"item_\\d+")))
    """

    def __init__(
        self,
        *commands: str | Pattern[str],
        prefix: str = DEFAULT_PREFIXES,
        ignore_case: bool = True,
        ignore_mention: bool = False,
        magic: Any = None,
    ) -> None:
        if not commands:
            raise ValueError("Command() requires at least one command name or pattern")
        self.commands: list[str | Pattern[str]] = []
        for command in commands:
            if isinstance(command, str):
                self.commands.append(command.lower() if ignore_case else command)
            else:
                self.commands.append(command)
        self.prefix = prefix
        self.ignore_case = ignore_case
        self.ignore_mention = ignore_mention
        self.magic = magic

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        text = _extract_text(event)
        if not text:
            return False

        head, _, args = text.partition(" ")
        if not head or head[0] not in self.prefix:
            return False

        prefix, body = head[0], head[1:]
        mention: str | None = None
        if "@" in body:
            body, _, mention = body.partition("@")
        if mention and not self.ignore_mention:
            bot = getattr(event, "_bot", None) or kwargs.get("bot")
            me = getattr(bot, "_me", None) if bot else None
            if me is not None and me.username and mention.lower() != me.username.lower():
                return False

        candidate = body.lower() if self.ignore_case else body
        if not self._matches(candidate):
            return False

        command = CommandObject(
            prefix=prefix, command=body, mention=mention, args=args.strip() or None
        )
        if self.magic is not None and not self.magic.resolve(command):
            return False
        return {"command": command}

    def _matches(self, candidate: str) -> bool:
        for expected in self.commands:
            if isinstance(expected, str):
                if candidate == expected:
                    return True
            elif expected.fullmatch(candidate):
                return True
        return False


class CommandStartFilter(Command):
    """``/start``, exposing the deep-link payload as ``command.args``."""

    def __init__(self, *, deep_link: bool = False) -> None:
        super().__init__("start")
        self.require_deep_link = deep_link

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        result = await super().__call__(event, **kwargs)
        if not result:
            # A `bot_started` event carries the payload in its own field instead
            # of the message text.
            payload = getattr(event, "payload", None)
            if payload is not None or type(event).__name__ == "BotStarted":
                if self.require_deep_link and not payload:
                    return False
                return {"command": CommandObject(prefix="/", command="start", args=payload)}
            return False
        if self.require_deep_link and isinstance(result, dict):
            if not result["command"].args:
                return False
        return result


@dataclass
class CommandPrefixes:
    """Container for a project-wide prefix set, e.g. ``"/!."``."""

    prefixes: str = DEFAULT_PREFIXES
    aliases: dict[str, Sequence[str]] = field(default_factory=dict)


def _extract_text(event: Any) -> str | None:
    text = getattr(event, "text", None)
    if isinstance(text, str):
        return text.strip()
    message = getattr(event, "message", None)
    if message is not None:
        return _extract_text(message)
    return None


__all__ = [
    "Command",
    "CommandObject",
    "CommandPrefixes",
    "CommandStart",
    "CommandStartFilter",
]
