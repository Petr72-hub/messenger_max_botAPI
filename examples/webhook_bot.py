"""Run the same handlers behind a webhook instead of long polling."""

import asyncio
import logging
import os

from aiohttp import web

from maxgram import Bot, Dispatcher
from maxgram.filters import Command
from maxgram.types import Message
from maxgram.webhook import setup_application

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()
PUBLIC_URL = os.environ["MAX_WEBHOOK_URL"]  # e.g. https://bot.example.com/webhook
SECRET = os.environ.get("MAX_WEBHOOK_SECRET")


@dp.message(Command("ping"))
async def ping(message: Message) -> None:
    await message.answer("pong")


async def build_app() -> web.Application:
    bot = Bot(os.environ["MAX_BOT_TOKEN"])
    await bot.set_webhook(PUBLIC_URL, secret=SECRET)
    app = web.Application()
    setup_application(app, dp, bot, path="/webhook", secret=SECRET)
    return app


if __name__ == "__main__":
    web.run_app(asyncio.run(build_app()), host="0.0.0.0", port=8080)
