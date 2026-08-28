from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from maxgram.filters.base import check_filter
from maxgram.filters.state import StateFilter
from maxgram.fsm.state import State, StatesGroup


@dataclass(slots=True)
class HandlerObject:
    """A registered callback plus the filters guarding it."""

    callback: Callable[..., Any]
    filters: list[Any] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    _spec: inspect.Signature | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._spec = _signature_of(self.callback)
        self.filters = [_normalize(f) for f in self.filters]

    @property
    def name(self) -> str:
        return getattr(self.callback, "__qualname__", repr(self.callback))

    async def check(self, event: Any, **kwargs: Any) -> tuple[bool, dict[str, Any]]:
        """Run every filter; the collected dict results become handler kwargs."""
        payload: dict[str, Any] = {}
        for f in self.filters:
            result = await check_filter(f, event, **{**kwargs, **payload})
            if not result:
                return False, {}
            if isinstance(result, dict):
                payload.update(result)
        return True, payload

    async def call(self, event: Any, **kwargs: Any) -> Any:
        accepted = self._filter_kwargs(kwargs)
        result = self.callback(event, **accepted)
        if inspect.isawaitable(result):
            return await result
        return result

    def _filter_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Dependency injection: hand over only what the handler declared."""
        spec = self._spec
        if spec is None:
            return {}
        params = spec.parameters
        # The first parameter receives the event positionally; never fill it again.
        event_param = next(iter(params), None)
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return {k: v for k, v in kwargs.items() if k != event_param}
        return {
            name: value
            for name, value in kwargs.items()
            if name in params
            and name != event_param
            and params[name].kind
            in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        }


def _normalize(f: Any) -> Any:
    """Let handlers take ``Form.name`` or a whole StatesGroup as a filter directly."""
    if isinstance(f, State):
        return StateFilter(f)
    if isinstance(f, type) and issubclass(f, StatesGroup):
        return StateFilter(f)
    return f


def _signature_of(callback: Callable[..., Any]) -> inspect.Signature | None:
    try:
        return inspect.signature(callback)
    except (TypeError, ValueError):  # builtins and some C callables
        return None
