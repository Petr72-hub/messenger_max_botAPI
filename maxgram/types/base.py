from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from maxgram.client.bot import Bot


class MaxObject(BaseModel):
    """Base for every MAX API entity.

    Objects carry a reference to the :class:`~maxgram.client.bot.Bot` that produced
    them, which is what makes shortcuts such as ``message.answer(...)`` possible.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )

    _bot: "Bot | None" = PrivateAttr(default=None)

    @property
    def bot(self) -> "Bot":
        if self._bot is None:
            raise RuntimeError(
                f"{type(self).__name__} is detached from a Bot instance; "
                "shortcuts are unavailable. Use Bot methods directly."
            )
        return self._bot

    def as_(self, bot: "Bot | None") -> "MaxObject":
        """Bind this object (and, lazily, its children) to ``bot``."""
        self._bot = bot
        return self

    def model_post_init(self, __context: Any) -> None:
        # Propagate the bot reference down the tree when the parent is bound later.
        pass

    def _bind_children(self, bot: "Bot | None") -> None:
        for value in self.__dict__.values():
            _bind(value, bot)


def _bind(value: Any, bot: "Bot | None") -> None:
    if isinstance(value, MaxObject):
        value._bot = bot
        value._bind_children(bot)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _bind(item, bot)
    elif isinstance(value, dict):
        for item in value.values():
            _bind(item, bot)


def bind_tree(obj: Any, bot: "Bot | None") -> Any:
    """Attach ``bot`` to ``obj`` and everything nested inside it."""
    _bind(obj, bot)
    return obj


class MutableMaxObject(MaxObject):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
        validate_assignment=True,
    )
