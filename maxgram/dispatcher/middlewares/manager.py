from __future__ import annotations

import functools
from typing import Any, Callable

from maxgram.dispatcher.middlewares.base import NextMiddleware


class MiddlewareManager:
    """Ordered middleware chain; first registered is outermost."""

    def __init__(self) -> None:
        self._middlewares: list[Any] = []

    def __call__(self, middleware: Any = None) -> Any:
        """Usable both as ``manager(mw)`` and as a decorator."""
        if middleware is None:
            return self.register
        return self.register(middleware)

    def register(self, middleware: Any) -> Any:
        self._middlewares.append(middleware)
        return middleware

    def unregister(self, middleware: Any) -> None:
        self._middlewares.remove(middleware)

    def __iter__(self):
        return iter(self._middlewares)

    def __len__(self) -> int:
        return len(self._middlewares)

    def wrap(self, handler: Callable[..., Any]) -> NextMiddleware:
        """Fold the chain around ``handler``.

        ``handler`` is called as ``handler(event, **data)``; middlewares receive
        ``(next, event, data)`` so they can mutate the data mapping in flight.
        """

        async def terminal(event: Any, data: dict[str, Any]) -> Any:
            return await handler(event, **data)

        chained: NextMiddleware = terminal
        for middleware in reversed(self._middlewares):
            chained = functools.partial(_apply, middleware, chained)  # type: ignore[assignment]
        return chained


async def _apply(middleware: Any, nxt: NextMiddleware, event: Any, data: dict[str, Any]) -> Any:
    return await middleware(nxt, event, data)
