"""maxgram - an asynchronous framework for the MAX messenger Bot API.

The public surface deliberately mirrors aiogram, so code and habits transfer::

    from maxgram import Bot, Dispatcher, F
    from maxgram.filters import Command
    from maxgram.types import Message

    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start(message: Message):
        await message.answer("Hello from MAX!")

    if __name__ == "__main__":
        dp.run_polling(Bot("<token>"))
"""

from maxgram.client.bot import Bot
from maxgram.client.default import DefaultBotProperties
from maxgram.client.session import AiohttpSession, RetryPolicy
from maxgram.dispatcher.dispatcher import Dispatcher
from maxgram.dispatcher.middlewares import BaseMiddleware
from maxgram.dispatcher.router import Router
from maxgram.enums import (
    AttachmentType,
    ChatType,
    Intent,
    SenderAction,
    TextFormat,
    UpdateType,
    UploadType,
)
from maxgram.filters import F
from maxgram.fsm import FSMContext, State, StatesGroup
from maxgram.utils.keyboard import InlineKeyboardBuilder

__version__ = "0.1.0"

__all__ = [
    "AiohttpSession",
    "AttachmentType",
    "BaseMiddleware",
    "Bot",
    "ChatType",
    "DefaultBotProperties",
    "Dispatcher",
    "F",
    "FSMContext",
    "InlineKeyboardBuilder",
    "Intent",
    "RetryPolicy",
    "Router",
    "SenderAction",
    "State",
    "StatesGroup",
    "TextFormat",
    "UpdateType",
    "UploadType",
    "__version__",
]
