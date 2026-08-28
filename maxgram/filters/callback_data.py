"""Typed callback payloads, the maxgram counterpart of ``aiogram.filters.callback_data``."""

from __future__ import annotations

from typing import Any, ClassVar, Self

from pydantic import BaseModel

from maxgram.filters.base import Filter, FilterResult

SEPARATOR = ":"
MAX_PAYLOAD = 1024


class CallbackData(BaseModel):
    """Serialise button payloads into a compact ``prefix:field:field`` string.

    Declare once, then pack into buttons and unpack in handlers::

        class Vote(CallbackData, prefix="vote"):
            post_id: int
            choice: str

        button = CallbackButton(text="Yes", payload=Vote(post_id=7, choice="yes").pack())

        @router.callback_query(Vote.filter())
        async def on_vote(event: MessageCallback, callback_data: Vote): ...
    """

    __prefix__: ClassVar[str] = ""
    __separator__: ClassVar[str] = SEPARATOR

    def __init_subclass__(cls, /, prefix: str | None = None, sep: str | None = None, **kwargs: Any):
        super().__init_subclass__(**kwargs)
        if prefix is not None:
            cls.__prefix__ = prefix
        if sep is not None:
            cls.__separator__ = sep
        if not cls.__prefix__:
            raise ValueError(f"{cls.__name__} must declare a prefix, e.g. class X(CallbackData, prefix='x')")

    def pack(self) -> str:
        parts = [self.__prefix__]
        for name in type(self).model_fields:
            value = getattr(self, name)
            encoded = "" if value is None else str(value)
            if self.__separator__ in encoded:
                raise ValueError(
                    f"value of {name!r} contains the separator {self.__separator__!r}"
                )
            parts.append(encoded)
        payload = self.__separator__.join(parts)
        if len(payload.encode("utf-8")) > MAX_PAYLOAD:
            raise ValueError(f"callback payload is too long: {len(payload)} chars")
        return payload

    @classmethod
    def unpack(cls, value: str) -> Self:
        prefix, *parts = value.split(cls.__separator__)
        names = list(cls.model_fields)
        if prefix != cls.__prefix__:
            raise ValueError(f"bad prefix: expected {cls.__prefix__!r}, got {prefix!r}")
        if len(parts) != len(names):
            raise ValueError(
                f"expected {len(names)} values for {cls.__name__}, got {len(parts)}"
            )
        payload = {
            name: (None if raw == "" else raw) for name, raw in zip(names, parts, strict=True)
        }
        return cls(**payload)

    @classmethod
    def filter(cls, rule: Any = None) -> "CallbackDataFilter":
        return CallbackDataFilter(cls, rule)


class CallbackDataFilter(Filter):
    """Matches a callback whose payload unpacks into ``factory``."""

    def __init__(self, factory: type[CallbackData], rule: Any = None) -> None:
        self.factory = factory
        self.rule = rule

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        payload = getattr(event, "data", None)
        if payload is None:
            payload = getattr(getattr(event, "callback", None), "payload", None)
        if not isinstance(payload, str):
            return False
        try:
            parsed = self.factory.unpack(payload)
        except (ValueError, TypeError):
            return False
        if self.rule is not None and not self.rule.resolve(parsed):
            return False
        return {"callback_data": parsed}
