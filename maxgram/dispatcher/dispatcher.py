"""The root router: owns polling, FSM storage and error handling."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Sequence

from maxgram.client.bot import Bot
from maxgram.dispatcher.event.observer import UNHANDLED
from maxgram.dispatcher.middlewares.user_context import (
    FSMContextMiddleware,
    UserContextMiddleware,
)
from maxgram.dispatcher.router import Router
from maxgram.exceptions import CancelHandler, MaxNetworkError, MaxServerError
from maxgram.fsm.storage.base import BaseStorage
from maxgram.fsm.storage.memory import MemoryStorage
from maxgram.types import Update, bind_tree, parse_update

logger = logging.getLogger(__name__)


class Dispatcher(Router):
    """Root of the router tree and the entry point for running a bot.

    ``Dispatcher`` adds to :class:`~maxgram.dispatcher.router.Router`:

    * an update feed (``feed_update`` / ``feed_raw_update``),
    * long polling (``start_polling`` / ``run_polling``),
    * FSM storage wiring,
    * ``workflow_data`` - arbitrary objects injected into every handler.
    """

    def __init__(
        self,
        *,
        storage: BaseStorage | None = None,
        name: str = "dispatcher",
        **workflow_data: Any,
    ) -> None:
        super().__init__(name=name)
        self.storage = storage or MemoryStorage()
        self.workflow_data: dict[str, Any] = workflow_data
        self._running = False
        self._polling_task: asyncio.Task[None] | None = None

        self.outer_middleware.register(UserContextMiddleware())
        self.outer_middleware.register(FSMContextMiddleware(self.storage))

    def __getitem__(self, key: str) -> Any:
        return self.workflow_data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.workflow_data[key] = value

    # -- feeding ---------------------------------------------------------------

    async def feed_update(self, bot: Bot, update: Update, **kwargs: Any) -> Any:
        """Route one parsed update through the router tree."""
        data = {
            **self.workflow_data,
            **kwargs,
            "bot": bot,
            "dispatcher": self,
            "event_update": update,
        }
        event = _unwrap_event(update)
        try:
            result = await self.propagate_event(str(update.update_type), event, **data)
        except CancelHandler:
            return UNHANDLED
        except Exception as exc:  # noqa: BLE001 - handlers must not kill the poller
            handled = await self._handle_error(exc, update, data)
            if not handled:
                raise
            return UNHANDLED
        if result is UNHANDLED:
            logger.debug("Update %s was not handled", update.update_type)
        return result

    async def feed_raw_update(self, bot: Bot, raw: dict[str, Any], **kwargs: Any) -> Any:
        """Parse a raw JSON event (webhook body or polling item) and route it."""
        update = bind_tree(parse_update(raw), bot)
        return await self.feed_update(bot, update, **kwargs)

    async def _handle_error(
        self, exc: Exception, update: Update, data: dict[str, Any]
    ) -> bool:
        if not self.errors.handlers and not any(r.errors.handlers for r in self.chain_tail):
            logger.exception("Unhandled exception while processing %s", update.update_type)
            return True
        payload = {**data, "exception": exc, "event_update": update}
        for router in self.chain_tail:
            result = await router.errors.trigger(exc, **payload)
            if result is not UNHANDLED:
                return True
        logger.exception("Error handlers did not handle %s", type(exc).__name__)
        return True

    # -- polling ---------------------------------------------------------------

    async def start_polling(
        self,
        bot: Bot,
        *,
        allowed_updates: Sequence[str] | None = None,
        limit: int = 100,
        timeout: int = 30,
        marker: int | None = None,
        handle_signals: bool = False,
        **workflow_data: Any,
    ) -> None:
        """Long-poll ``GET /updates`` until cancelled.

        Each update is dispatched in its own task, so a slow handler never stalls
        the poll loop. Network failures back off and retry instead of exiting.
        """
        self.workflow_data.update(workflow_data)
        self._running = True

        me = await bot.get_me()
        logger.info("Start polling as @%s (id=%s)", me.username or me.first_name, me.user_id)
        await self.emit_startup(bot=bot, dispatcher=self, **self.workflow_data)

        if handle_signals:
            self._install_signal_handlers()

        backoff = 1.0
        tasks: set[asyncio.Task[Any]] = set()
        try:
            while self._running:
                try:
                    payload = await bot.get_updates(
                        limit=limit, timeout=timeout, marker=marker, types=allowed_updates
                    )
                    backoff = 1.0
                except (MaxNetworkError, MaxServerError) as exc:
                    logger.warning("Polling failed (%s), retrying in %.1fs", exc, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                    continue

                marker = payload.get("marker", marker)
                for raw in payload.get("updates", []):
                    task = asyncio.create_task(self._safe_feed(bot, raw))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
        except asyncio.CancelledError:
            logger.info("Polling cancelled")
            raise
        finally:
            self._running = False
            for task in list(tasks):
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await self.emit_shutdown(bot=bot, dispatcher=self, **self.workflow_data)
            await self.storage.close()

    async def _safe_feed(self, bot: Bot, raw: dict[str, Any]) -> None:
        try:
            await self.feed_raw_update(bot, raw)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - already reported by _handle_error
            logger.exception("Update processing crashed: %r", raw.get("update_type"))

    def run_polling(self, bot: Bot, **kwargs: Any) -> None:
        """Blocking wrapper around :meth:`start_polling` for ``__main__`` blocks."""

        async def runner() -> None:
            async with bot:
                await self.start_polling(bot, **kwargs)

        try:
            asyncio.run(runner())
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot stopped")

    def stop_polling(self) -> None:
        self._running = False

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop_polling)
            except (NotImplementedError, AttributeError):
                # Windows event loops do not implement add_signal_handler.
                pass

    # -- webhook helpers -------------------------------------------------------

    async def start_webhook(
        self,
        bot: Bot,
        url: str,
        *,
        allowed_updates: Sequence[str] | None = None,
        secret: str | None = None,
    ) -> bool:
        """Register the webhook and emit ``startup``."""
        await bot.get_me()
        await self.emit_startup(bot=bot, dispatcher=self, **self.workflow_data)
        return await bot.set_webhook(url, update_types=allowed_updates, secret=secret)


def _unwrap_event(update: Update) -> Any:
    """Hand handlers the object they care about.

    ``message_created`` and ``message_edited`` deliver the :class:`Message` itself,
    everything else the update object, so handler signatures stay obvious.
    """
    update_type = str(update.update_type)
    if update_type in ("message_created", "message_edited"):
        message = getattr(update, "message", None)
        if message is not None:
            return message
    return update
