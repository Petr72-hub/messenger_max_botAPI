from __future__ import annotations

import logging
from typing import Any, Callable

from maxgram.dispatcher.event.handler import HandlerObject
from maxgram.dispatcher.middlewares.manager import MiddlewareManager
from maxgram.exceptions import SkipHandler

logger = logging.getLogger(__name__)

UNHANDLED = object()
"""Sentinel returned when no handler in this observer matched."""


class TelegramLikeObserver:
    """Ordered list of handlers for one event type.

    Registration mirrors aiogram: call the observer as a decorator with filters,
    or use ``.register(callback, *filters)``.
    """

    def __init__(self, event_name: str) -> None:
        self.event_name = event_name
        self.handlers: list[HandlerObject] = []
        self.outer_middleware = MiddlewareManager()
        self.middleware = MiddlewareManager()

    def __call__(self, *filters: Any, **flags: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(callback: Callable[..., Any]) -> Callable[..., Any]:
            self.register(callback, *filters, **flags)
            return callback

        return decorator

    def register(
        self, callback: Callable[..., Any], *filters: Any, **flags: Any
    ) -> Callable[..., Any]:
        self.handlers.append(
            HandlerObject(callback=callback, filters=list(filters), flags=flags)
        )
        return callback

    def unregister(self, callback: Callable[..., Any]) -> None:
        self.handlers = [h for h in self.handlers if h.callback is not callback]

    async def dispatch(self, event: Any, **kwargs: Any) -> Any:
        """Run outer middlewares (always), then the handler search."""
        if not len(self.outer_middleware):
            return await self.trigger(event, **kwargs)
        wrapped = self.outer_middleware.wrap(
            lambda ev, **data: self.trigger(ev, **data)
        )
        return await wrapped(event, kwargs)

    async def trigger(self, event: Any, **kwargs: Any) -> Any:
        """Run the first handler whose filters pass, with inner middlewares around it."""
        for handler in self.handlers:
            matched, payload = await handler.check(event, **kwargs)
            if not matched:
                continue
            merged = {**kwargs, **payload, "handler": handler}
            try:
                wrapped = self.middleware.wrap(handler.call)
                return await wrapped(event, merged)
            except SkipHandler:
                continue
        return UNHANDLED

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Observer {self.event_name!r} handlers={len(self.handlers)}>"


EventObserver = TelegramLikeObserver
