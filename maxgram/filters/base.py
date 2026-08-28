from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Union

from maxgram.filters.magic import MagicFilter, result_name_of

FilterResult = Union[bool, dict[str, Any], None]


class Filter(ABC):
    """Base for class-based filters.

    Returning a ``dict`` both matches and injects its keys as handler kwargs, the
    same contract aiogram uses.
    """

    @abstractmethod
    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        raise NotImplementedError

    def __invert__(self) -> "Filter":
        return _Invert(self)

    def __and__(self, other: Any) -> "Filter":
        return _And(self, other)

    def __or__(self, other: Any) -> "Filter":
        return _Or(self, other)


class _Invert(Filter):
    def __init__(self, target: Any) -> None:
        self.target = target

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        return not bool(await check_filter(self.target, event, **kwargs))


class _And(Filter):
    def __init__(self, *targets: Any) -> None:
        self.targets = targets

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        payload: dict[str, Any] = {}
        for target in self.targets:
            result = await check_filter(target, event, **{**kwargs, **payload})
            if not result:
                return False
            if isinstance(result, dict):
                payload.update(result)
        return payload or True


class _Or(Filter):
    def __init__(self, *targets: Any) -> None:
        self.targets = targets

    async def __call__(self, event: Any, **kwargs: Any) -> FilterResult:
        for target in self.targets:
            result = await check_filter(target, event, **kwargs)
            if result:
                return result
        return False


async def check_filter(target: Any, event: Any, **kwargs: Any) -> FilterResult:
    """Evaluate anything usable as a filter: magic expression, callable, or bool."""
    if isinstance(target, MagicFilter):
        result = target.resolve(event)
        name = result_name_of(target)
        if name and result:
            return {name: result}
        return bool(result)

    if isinstance(target, bool):
        return target

    if callable(target):
        result = _call_with_supported_kwargs(target, event, kwargs)
        if inspect.isawaitable(result):
            result = await result
        return result  # type: ignore[return-value]

    raise TypeError(f"{target!r} is not usable as a filter")


def _call_with_supported_kwargs(
    target: Callable[..., Any], event: Any, kwargs: dict[str, Any]
) -> Any | Awaitable[Any]:
    """Pass only the keyword arguments the callable actually declares."""
    func = target.__call__ if not inspect.isfunction(target) and hasattr(target, "__call__") else target
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return target(event)

    params = signature.parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return target(event, **kwargs)

    accepted = {
        name: value
        for name, value in kwargs.items()
        if name in params
        and params[name].kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return target(event, **accepted)
