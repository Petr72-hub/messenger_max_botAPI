"""Declarative FSM states, mirroring ``aiogram.fsm.state``."""

from __future__ import annotations

from typing import Any, Iterator


class State:
    """One step of a conversation.

    States declared inside a :class:`StatesGroup` get a qualified name of
    ``GroupName:state_name``, which is what the storage persists.
    """

    def __init__(self, state: str | None = None, group_name: str | None = None) -> None:
        self._state = state
        self._group_name = group_name
        self._group: type[StatesGroup] | None = None

    @property
    def group(self) -> "type[StatesGroup]":
        if self._group is None:
            raise RuntimeError(f"State {self._state!r} does not belong to a StatesGroup")
        return self._group

    @property
    def state(self) -> str | None:
        if self._state is None or self._state == "*":
            return self._state
        if self._group_name is None and self._group is not None:
            self._group_name = self._group.__name__
        return f"{self._group_name}:{self._state}" if self._group_name else self._state

    def set_parent(self, group: "type[StatesGroup]") -> None:
        self._group = group
        self._group_name = group.__name__

    def __set_name__(self, owner: Any, name: str) -> None:
        if self._state is None:
            self._state = name
        if isinstance(owner, type) and issubclass(owner, StatesGroup):
            self._group_name = owner.__name__

    def __str__(self) -> str:
        return f"<State {self.state!r}>"

    __repr__ = __str__

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, State):
            return self.state == other.state
        if isinstance(other, str):
            return self.state == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.state)

    async def set(self, context: Any) -> None:
        await context.set_state(self)


class StatesGroupMeta(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]):
        cls = super().__new__(mcs, name, bases, namespace)
        states: list[State] = []
        for key, value in namespace.items():
            if isinstance(value, State):
                value.set_parent(cls)  # type: ignore[arg-type]
                states.append(value)
        cls.__states__ = tuple(states)  # type: ignore[attr-defined]
        return cls

    def __iter__(cls) -> Iterator[State]:
        return iter(cls.__states__)  # type: ignore[attr-defined]

    def __contains__(cls, item: Any) -> bool:
        value = item.state if isinstance(item, State) else item
        return any(s.state == value for s in cls.__states__)  # type: ignore[attr-defined]

    @property
    def states(cls) -> tuple[State, ...]:
        return cls.__states__  # type: ignore[attr-defined]

    @property
    def state_names(cls) -> tuple[str, ...]:
        return tuple(s.state for s in cls.__states__ if s.state)  # type: ignore[attr-defined]


class StatesGroup(metaclass=StatesGroupMeta):
    """Namespace for related states::

    class Post(StatesGroup):
        waiting_text = State()
        waiting_photo = State()
    """

    __states__: tuple[State, ...] = ()


any_state = State("*")
"""Wildcard matching every state, including "no state"."""

default_state = State(None)
"""The implicit state a user starts in."""
