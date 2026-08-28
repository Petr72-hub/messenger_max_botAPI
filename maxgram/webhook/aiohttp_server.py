"""Receive MAX events over HTTP instead of polling."""

from __future__ import annotations

import asyncio
import hmac
import logging
from typing import Any

from aiohttp import web

from maxgram.client.bot import Bot
from maxgram.dispatcher.dispatcher import Dispatcher

logger = logging.getLogger(__name__)


class WebhookRequestHandler:
    """aiohttp view that feeds incoming events into a :class:`Dispatcher`."""

    def __init__(
        self,
        dispatcher: Dispatcher,
        bot: Bot,
        *,
        secret: str | None = None,
        handle_in_background: bool = True,
    ) -> None:
        self.dispatcher = dispatcher
        self.bot = bot
        self.secret = secret
        self.handle_in_background = handle_in_background

    async def handle(self, request: web.Request) -> web.Response:
        if not self._verify(request):
            logger.warning("Rejected webhook call with a bad secret from %s", request.remote)
            return web.json_response({"ok": False}, status=401)

        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - malformed body
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)

        if self.handle_in_background:
            # Answer immediately; MAX retries anything it considers timed out.
            tasks: set[asyncio.Task[None]] = request.app["background"]
            task = asyncio.create_task(self._feed(payload))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            return web.json_response({"ok": True})

        await self._feed(payload)
        return web.json_response({"ok": True})

    async def _feed(self, payload: dict[str, Any]) -> None:
        try:
            await self.dispatcher.feed_raw_update(self.bot, payload)
        except Exception:  # noqa: BLE001 - never break the HTTP layer
            logger.exception("Webhook update failed")

    def _verify(self, request: web.Request) -> bool:
        if not self.secret:
            return True
        provided = request.headers.get("X-Max-Bot-Api-Secret", "")
        return hmac.compare_digest(provided, self.secret)


def setup_application(
    app: web.Application,
    dispatcher: Dispatcher,
    bot: Bot,
    *,
    path: str = "/webhook",
    secret: str | None = None,
) -> web.Application:
    """Mount the webhook route and tie the bot's lifecycle to the app's."""
    handler = WebhookRequestHandler(dispatcher, bot, secret=secret)
    app["background"] = set()
    app.router.add_post(path, handler.handle)

    async def on_startup(_: web.Application) -> None:
        await dispatcher.emit_startup(bot=bot, dispatcher=dispatcher, **dispatcher.workflow_data)

    async def on_cleanup(_: web.Application) -> None:
        await dispatcher.emit_shutdown(bot=bot, dispatcher=dispatcher, **dispatcher.workflow_data)
        await dispatcher.storage.close()
        await bot.close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def run_webhook(
    dispatcher: Dispatcher,
    bot: Bot,
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    path: str = "/webhook",
    secret: str | None = None,
) -> None:
    """Blocking helper that serves the webhook with aiohttp's own runner."""
    app = web.Application()
    setup_application(app, dispatcher, bot, path=path, secret=secret)
    web.run_app(app, host=host, port=port)
