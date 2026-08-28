"""A compact re-implementation of aiogram's ``F`` magic filter.

``F`` builds a lazy expression tree out of attribute access and operators, then
evaluates it against the incoming event::

    F.text == "/start"
    F.text.lower().startswith("hi")
    F.chat_type.in_({"chat", "channel"})
    (F.text.is_not_none()) & (F.sender.is_bot == False)  # noqa: E712

Expressions are truthy filters: the dispatcher treats a falsy result as "no match".
"""

from __future__ import annotations

import operator
import re
from typing import Any, Callable, Iterable


class MagicFilter:
    """Node of a lazy expression tree."""

    __slots__ = ("_operations",)

    def __init__(self, operations: tuple[Callable[[Any, Any], Any], ...] = ()) -> None:
        self._operations = operations

    # -- construction ----------------------------------------------------------

    def _extend(self, op: Callable[[Any, Any], Any]) -> "MagicFilter":
        return MagicFilter(self._operations + (op,))

    def __getattr__(self, item: str) -> "MagicFilter":
        # Underscore-prefixed names stay real attribute lookups; intercepting them
        # would make every ``getattr(expr, "_x", default)` silently return a node.
        if item.startswith("_"):
            raise AttributeError(item)
        return self._extend(lambda value, event, _name=item: _resolve_attr(value, _name))

    def __getitem__(self, item: Any) -> "MagicFilter":
        return self._extend(lambda value, event, _key=item: _resolve_item(value, _key))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Either evaluate the chain (one positional arg) or call the resolved value."""
        if len(args) == 1 and not kwargs and not isinstance(args[0], MagicFilter):
            return self.resolve(args[0])
        return self._extend(
            lambda value, event, _a=args, _kw=kwargs: value(*_a, **_kw)  # type: ignore[misc]
        )

    # -- evaluation ------------------------------------------------------------

    def resolve(self, event: Any) -> Any:
        value: Any = event
        for op in self._operations:
            value = op(value, event)
        return value

    async def __acall__(self, event: Any) -> Any:  # pragma: no cover - alias
        return self.resolve(event)

    # -- comparisons -----------------------------------------------------------

    def _compare(self, other: Any, op: Callable[[Any, Any], Any]) -> "MagicFilter":
        return self._extend(
            lambda value, event, _other=other, _op=op: _op(value, _unwrap(_other, event))
        )

    def __eq__(self, other: Any) -> "MagicFilter":  # type: ignore[override]
        return self._compare(other, operator.eq)

    def __ne__(self, other: Any) -> "MagicFilter":  # type: ignore[override]
        return self._compare(other, operator.ne)

    def __lt__(self, other: Any) -> "MagicFilter":
        return self._compare(other, operator.lt)

    def __le__(self, other: Any) -> "MagicFilter":
        return self._compare(other, operator.le)

    def __gt__(self, other: Any) -> "MagicFilter":
        return self._compare(other, operator.gt)

    def __ge__(self, other: Any) -> "MagicFilter":
        return self._compare(other, operator.ge)

    def __hash__(self) -> int:
        return id(self)

    # -- logic -----------------------------------------------------------------

    def __and__(self, other: Any) -> "MagicFilter":
        return MagicFilter(
            (lambda value, event, _s=self, _o=other: bool(_s.resolve(event)) and bool(_eval(_o, event)),)
        )

    def __or__(self, other: Any) -> "MagicFilter":
        return MagicFilter(
            (lambda value, event, _s=self, _o=other: bool(_s.resolve(event)) or bool(_eval(_o, event)),)
        )

    def __invert__(self) -> "MagicFilter":
        return MagicFilter((lambda value, event, _s=self: not bool(_s.resolve(event)),))

    # -- helpers ---------------------------------------------------------------

    def in_(self, collection: Iterable[Any]) -> "MagicFilter":
        items = set(collection) if not isinstance(collection, (set, frozenset)) else collection
        return self._extend(lambda value, event, _c=items: value in _c)

    def not_in(self, collection: Iterable[Any]) -> "MagicFilter":
        items = set(collection) if not isinstance(collection, (set, frozenset)) else collection
        return self._extend(lambda value, event, _c=items: value not in _c)

    def contains(self, item: Any) -> "MagicFilter":
        return self._extend(
            lambda value, event, _i=item: bool(value) and _unwrap(_i, event) in value
        )

    def startswith(self, prefix: str) -> "MagicFilter":
        return self._extend(
            lambda value, event, _p=prefix: isinstance(value, str) and value.startswith(_p)
        )

    def endswith(self, suffix: str) -> "MagicFilter":
        return self._extend(
            lambda value, event, _s=suffix: isinstance(value, str) and value.endswith(_s)
        )

    def regexp(self, pattern: str | re.Pattern[str]) -> "MagicFilter":
        compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
        return self._extend(
            lambda value, event, _p=compiled: bool(isinstance(value, str) and _p.search(value))
        )

    def lower(self) -> "MagicFilter":
        return self._extend(lambda value, event: value.lower() if isinstance(value, str) else value)

    def upper(self) -> "MagicFilter":
        return self._extend(lambda value, event: value.upper() if isinstance(value, str) else value)

    def len(self) -> "MagicFilter":
        return self._extend(lambda value, event: len(value) if value is not None else 0)

    def is_none(self) -> "MagicFilter":
        return self._extend(lambda value, event: value is None)

    def is_not_none(self) -> "MagicFilter":
        return self._extend(lambda value, event: value is not None)

    def func(self, callback: Callable[[Any], Any]) -> "MagicFilter":
        return self._extend(lambda value, event, _f=callback: _f(value))

    def cast(self, factory: Callable[[Any], Any]) -> "MagicFilter":
        return self._extend(lambda value, event, _f=factory: _f(value))

    def as_(self, name: str) -> "MagicFilter":
        """Publish the resolved value to handlers under ``name`` (aiogram parity)."""
        return _NamedMagic(self._operations, name)


class _NamedMagic(MagicFilter):
    """Expression whose value is published to handlers under a chosen name."""

    __slots__ = ("_name",)

    def __init__(self, operations: tuple[Callable[[Any, Any], Any], ...], name: str) -> None:
        super().__init__(operations)
        object.__setattr__(self, "_name", name)


def result_name_of(expression: Any) -> str | None:
    """Name requested via ``.as_(...)``, or ``None`` for a plain expression."""
    if isinstance(expression, _NamedMagic):
        return expression._name  # type: ignore[attr-defined]
    return None


def _resolve_attr(value: Any, name: str) -> Any:
    """Missing links collapse to ``None`` so ``F.a.b.c`` never raises mid-chain."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _resolve_item(value: Any, key: Any) -> Any:
    if value is None:
        return None
    try:
        return value[key]
    except (KeyError, IndexError, TypeError):
        return None


def _unwrap(value: Any, event: Any) -> Any:
    return value.resolve(event) if isinstance(value, MagicFilter) else value


def _eval(value: Any, event: Any) -> Any:
    if isinstance(value, MagicFilter):
        return value.resolve(event)
    if callable(value):
        return value(event)
    return value


F = MagicFilter()
"""Entry point for magic expressions, e.g. ``F.text.startswith("/")``."""
