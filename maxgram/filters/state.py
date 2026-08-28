from __future__ import annotations

from typing import Any, Sequence

from maxgram.filters.base import Filter, FilterResult
from maxgram.fsm.state import State, StatesGroup


class StateFilter(Filter):
    """Match the current FSM state.

    Accepts :class:`State` objects, whole :class:`StatesGroup` classes, raw strings,
    ``None`` for "no state set", and ``"*"`` for "any state".
    """

    def __init__(self, *states: State | str | None | type[StatesGroup]) -> None:
        self.states: list[Any] = list(states)

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        context = kwargs.get("state")
        current = await context.get_state() if context is not None else None
        return self._matches(current)

    def _matches(self, current: str | None) -> bool:
        for expected in self.states:
            if expected is None:
                if current is None:
                    return True
            elif isinstance(expected, State):
                if expected.state == "*" or expected.state == current:
                    return True
            elif isinstance(expected, str):
                if expected == "*" or expected == current:
                    return True
            elif isinstance(expected, type) and issubclass(expected, StatesGroup):
                if current is not None and current in expected:
                    return True
        return False


def normalize_state_filter(
    value: State | str | None | type[StatesGroup] | Sequence[Any],
) -> StateFilter:
    if isinstance(value, (list, tuple, set)):
        return StateFilter(*value)
    return StateFilter(value)
