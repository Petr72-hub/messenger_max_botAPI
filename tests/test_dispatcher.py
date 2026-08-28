from __future__ import annotations

import pytest

from maxgram import Dispatcher, F, Router
from maxgram.dispatcher.middlewares import BaseMiddleware
from maxgram.filters import Command, CommandObject, Text
from maxgram.fsm import State, StatesGroup
from maxgram.types import Message, MessageCallback

from .conftest import callback_update, message_update


async def test_command_filter_matches_and_injects(bot):
    dp = Dispatcher()
    seen = {}

    @dp.message(Command("start"))
    async def handler(message: Message, command: CommandObject):
        seen["text"] = message.text
        seen["args"] = command.args
        return "ok"

    result = await dp.feed_raw_update(bot, message_update("/start deep-link-payload"))
    assert result == "ok"
    assert seen == {"text": "/start deep-link-payload", "args": "deep-link-payload"}


async def test_magic_filter(bot):
    dp = Dispatcher()

    @dp.message(F.text.lower().startswith("hello"))
    async def handler(message: Message):
        return message.text

    assert await dp.feed_raw_update(bot, message_update("HELLO there")) == "HELLO there"


async def test_non_matching_update_is_unhandled(bot):
    dp = Dispatcher()

    @dp.message(Text("exact"))
    async def handler(message: Message):
        return "matched"

    from maxgram.dispatcher import UNHANDLED

    assert await dp.feed_raw_update(bot, message_update("other")) is UNHANDLED


async def test_nested_routers_resolve_in_order(bot):
    dp = Dispatcher()
    child = Router(name="child")

    @child.message(Command("ping"))
    async def child_handler(message: Message):
        return "child"

    dp.include_router(child)
    assert await dp.feed_raw_update(bot, message_update("/ping")) == "child"


async def test_callback_query_shortcuts(bot, session):
    dp = Dispatcher()

    @dp.callback_query(F.data == "vote:yes")
    async def handler(event: MessageCallback):
        await event.answer("counted")
        return event.data

    assert await dp.feed_raw_update(bot, callback_update("vote:yes")) == "vote:yes"
    assert ("POST", "/answers", {"callback_id": "cb-1"}, {"notification": "counted"}) in session.calls


async def test_message_answer_uses_same_chat(bot, session):
    dp = Dispatcher()

    @dp.message()
    async def handler(message: Message):
        await message.answer("pong")

    await dp.feed_raw_update(bot, message_update("ping", chat_id=777))
    method, path, params, body = session.calls[-1]
    assert (method, path) == ("POST", "/messages")
    assert params["chat_id"] == "777" or params["chat_id"] == 777
    assert body["text"] == "pong"


async def test_middleware_can_inject_data(bot):
    dp = Dispatcher()

    class Injector(BaseMiddleware):
        async def __call__(self, handler, event, data):
            data["injected"] = "value"
            return await handler(event, data)

    dp.message.middleware(Injector())

    @dp.message()
    async def handler(message: Message, injected: str):
        return injected

    assert await dp.feed_raw_update(bot, message_update("x")) == "value"


async def test_fsm_state_roundtrip(bot):
    dp = Dispatcher()

    class Form(StatesGroup):
        name = State()

    @dp.message(Command("begin"))
    async def begin(message: Message, state):
        await state.set_state(Form.name)
        await state.update_data(step=1)
        return "began"

    @dp.message(Form.name)
    async def collect(message: Message, state):
        data = await state.get_data()
        await state.clear()
        return f"got {message.text} step={data['step']}"

    assert await dp.feed_raw_update(bot, message_update("/begin")) == "began"
    assert await dp.feed_raw_update(bot, message_update("Ann")) == "got Ann step=1"


async def test_error_handler_catches_exception(bot):
    dp = Dispatcher()
    caught = {}

    @dp.message()
    async def broken(message: Message):
        raise ValueError("boom")

    @dp.errors()
    async def on_error(exception: Exception):
        caught["error"] = str(exception)
        return True

    await dp.feed_raw_update(bot, message_update("x"))
    assert caught["error"] == "boom"


async def test_workflow_data_is_injected(bot):
    dp = Dispatcher(config={"key": "value"})

    @dp.message()
    async def handler(message: Message, config: dict):
        return config["key"]

    assert await dp.feed_raw_update(bot, message_update("x")) == "value"
