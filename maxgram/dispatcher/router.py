from __future__ import annotations

import logging
from typing import Any, Iterator

from maxgram.dispatcher.event.observer import UNHANDLED, EventObserver
from maxgram.dispatcher.middlewares.manager import MiddlewareManager
from maxgram.enums import UpdateType

logger = logging.getLogger(__name__)

#: Friendly observer name -> MAX ``update_type``.
OBSERVER_ALIASES: dict[str, str] = {
    "message": UpdateType.MESSAGE_CREATED.value,
    "edited_message": UpdateType.MESSAGE_EDITED.value,
    "deleted_message": UpdateType.MESSAGE_REMOVED.value,
    "callback_query": UpdateType.MESSAGE_CALLBACK.value,
    "chat_created": UpdateType.MESSAGE_CHAT_CREATED.value,
    "bot_added": UpdateType.BOT_ADDED.value,
    "bot_removed": UpdateType.BOT_REMOVED.value,
    "bot_started": UpdateType.BOT_STARTED.value,
    "bot_stopped": UpdateType.BOT_STOPPED.value,
    "user_added": UpdateType.USER_ADDED.value,
    "user_removed": UpdateType.USER_REMOVED.value,
    "chat_title_changed": UpdateType.CHAT_TITLE_CHANGED.value,
    "dialog_cleared": UpdateType.DIALOG_CLEARED.value,
    "dialog_removed": UpdateType.DIALOG_REMOVED.value,
    "dialog_muted": UpdateType.DIALOG_MUTED.value,
    "dialog_unmuted": UpdateType.DIALOG_UNMUTED.value,
    "comment_created": UpdateType.COMMENT_CREATED.value,
    "comment_edited": UpdateType.COMMENT_EDITED.value,
    "comment_removed": UpdateType.COMMENT_REMOVED.value,
}


class Router:
    """A group of handlers that can be nested inside another router.

    Routers let a project split handlers across modules and still resolve them in
    a deterministic order: a parent tries its own handlers first, then each child
    in registration order, stopping at the first match.
    """

    def __init__(self, *, name: str | None = None) -> None:
        self.name = name or hex(id(self))
        self.parent_router: "Router | None" = None
        self.sub_routers: list["Router"] = []

        self.observers: dict[str, EventObserver] = {
            update_type: EventObserver(update_type) for update_type in OBSERVER_ALIASES.values()
        }
        #: Fires for every event regardless of type, before the typed observers.
        self.update = EventObserver("update")
        #: Handlers for exceptions raised while processing an event.
        self.errors = EventObserver("error")

        self.startup = EventObserver("startup")
        self.shutdown = EventObserver("shutdown")

        #: Middlewares applied to every event this router sees, matched or not.
        #: For handler-scoped middlewares use ``router.message.middleware``.
        self.outer_middleware = MiddlewareManager()

    # -- named observers -------------------------------------------------------

    def __getattr__(self, item: str) -> EventObserver:
        alias = OBSERVER_ALIASES.get(item)
        if alias is None:
            raise AttributeError(f"{type(self).__name__!r} has no observer {item!r}")
        return self.observers[alias]

    def observer(self, update_type: str | UpdateType) -> EventObserver:
        """Observer for a raw ``update_type``, created on demand."""
        key = str(update_type)
        if key not in self.observers:
            self.observers[key] = EventObserver(key)
        return self.observers[key]

    # -- composition -----------------------------------------------------------

    def include_router(self, router: "Router") -> "Router":
        if not isinstance(router, Router):
            raise TypeError(f"include_router expects a Router, got {type(router).__name__}")
        if router is self:
            raise RuntimeError("a router cannot include itself")
        if router.parent_router is not None:
            raise RuntimeError(f"router {router.name!r} is already attached to another router")
        parent: Router | None = self
        while parent is not None:
            if parent is router:
                raise RuntimeError("circular router reference")
            parent = parent.parent_router
        router.parent_router = self
        self.sub_routers.append(router)
        return router

    def include_routers(self, *routers: "Router") -> None:
        for router in routers:
            self.include_router(router)

    @property
    def chain_head(self) -> Iterator["Router"]:
        router: Router | None = self
        while router is not None:
            yield router
            router = router.parent_router

    @property
    def chain_tail(self) -> Iterator["Router"]:
        yield self
        for child in self.sub_routers:
            yield from child.chain_tail

    # -- dispatching -----------------------------------------------------------

    async def propagate_event(self, update_type: str, event: Any, **kwargs: Any) -> Any:
        """Try this router, then its children, returning the first real result."""
        kwargs = {**kwargs, "event_router": self}

        wrapped = self.outer_middleware.wrap(
            lambda ev, **data: self._propagate_inner(update_type, ev, **data)
        )
        return await wrapped(event, kwargs)

    async def _propagate_inner(self, update_type: str, event: Any, **kwargs: Any) -> Any:
        catch_all = await self.update.dispatch(event, **kwargs)
        if catch_all is not UNHANDLED:
            return catch_all

        observer = self.observers.get(update_type)
        if observer is not None:
            result = await observer.dispatch(event, **kwargs)
            if result is not UNHANDLED:
                return result

        for router in self.sub_routers:
            result = await router.propagate_event(update_type, event, **kwargs)
            if result is not UNHANDLED:
                return result

        return UNHANDLED

    async def emit_startup(self, **kwargs: Any) -> None:
        await self.startup.trigger(None, **kwargs)
        for router in self.sub_routers:
            await router.emit_startup(**kwargs)

    async def emit_shutdown(self, **kwargs: Any) -> None:
        for router in self.sub_routers:
            await router.emit_shutdown(**kwargs)
        await self.shutdown.trigger(None, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Router {self.name!r}>"
