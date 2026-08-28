"""Minimal maxgram bot: replies to /start and echoes everything else."""

import asyncio
import logging
import os

from maxgram import Bot, Dispatcher, F
from maxgram.filters import Command, CommandObject
from maxgram.types import Message

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()


@dp.message(Command("start"))
async def on_start(message: Message, command: CommandObject) -> None:
    greeting = "Hello! Send me anything and I will echo it back."
    if command.args:
        greeting += f"\nDeep-link payload: {command.args}"
    await message.answer(greeting)


@dp.message(F.text)
async def echo(message: Message) -> None:
    await message.reply(message.text)


async def main() -> None:
    bot = Bot(os.environ["MAX_BOT_TOKEN"])
    async with bot:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
