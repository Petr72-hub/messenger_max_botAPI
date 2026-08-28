from __future__ import annotations

import pytest

from maxgram import F, Intent
from maxgram.filters import CallbackData
from maxgram.types import CallbackButton, InlineKeyboardMarkup, LinkButton, Message
from maxgram.utils import InlineKeyboardBuilder, escape_md, split_text

from .conftest import callback_update


def make_message(text: str) -> Message:
    return Message.model_validate(
        {
            "sender": {"user_id": 1, "first_name": "Ann"},
            "recipient": {"chat_id": 5, "chat_type": "chat"},
            "timestamp": 1,
            "body": {"mid": "a", "text": text},
        }
    )


def test_keyboard_builder_adjust():
    kb = InlineKeyboardBuilder()
    for i in range(5):
        kb.button(text=str(i), payload=f"p{i}")
    kb.adjust(2)
    markup = kb.as_markup()
    assert [len(row) for row in markup.buttons] == [2, 2, 1]


def test_keyboard_serialises_to_attachment():
    markup = InlineKeyboardMarkup(
        buttons=[[CallbackButton(text="Yes", payload="y", intent=Intent.POSITIVE)],
                 [LinkButton(text="Docs", url="https://dev.max.ru")]]
    )
    attachment = markup.to_attachment()
    assert attachment["type"] == "inline_keyboard"
    rows = attachment["payload"]["buttons"]
    assert rows[0][0] == {"type": "callback", "text": "Yes", "payload": "y", "intent": "positive"}
    assert rows[1][0]["url"] == "https://dev.max.ru"


def test_callback_data_pack_unpack():
    class Vote(CallbackData, prefix="vote"):
        post_id: int
        choice: str

    packed = Vote(post_id=7, choice="yes").pack()
    assert packed == "vote:7:yes"
    assert Vote.unpack(packed) == Vote(post_id=7, choice="yes")


async def test_callback_data_filter(bot):
    from maxgram import Dispatcher

    class Vote(CallbackData, prefix="vote"):
        choice: str

    dp = Dispatcher()

    @dp.callback_query(Vote.filter())
    async def handler(event, callback_data: Vote):
        return callback_data.choice

    assert await dp.feed_raw_update(bot, callback_update("vote:yes")) == "yes"


def test_magic_chain_survives_missing_links():
    message = make_message("hi")
    assert (F.link.message.text == "anything").resolve(message) is False
    assert F.body.text.is_not_none().resolve(message) is True


def test_magic_logic_operators():
    message = make_message("/start")
    expr = (F.text.startswith("/")) & (~F.sender.is_bot)
    assert expr.resolve(message) is True


def test_split_text_prefers_paragraph_breaks():
    text = ("a" * 100 + "\n\n" + "b" * 100)
    chunks = split_text(text, limit=150)
    assert chunks[0] == "a" * 100
    assert chunks[1] == "b" * 100


def test_split_text_short_passthrough():
    assert split_text("hello", limit=10) == ["hello"]


def test_escape_md():
    assert escape_md("a*b_c") == r"a\*b\_c"


async def test_upload_flow(bot, session, tmp_path):
    from maxgram.client.session import AiohttpSession

    photo = tmp_path / "pic.png"
    photo.write_bytes(b"\x89PNG")

    session.responses["POST /uploads"] = {"url": "https://iu.oneme.ru/upload", "token": "tok-1"}

    async def fake_upload_binary(url, data, filename, *, content_type):
        assert data == b"\x89PNG"
        assert filename == "pic.png"
        return {"photos": {"p": {"token": "tok-photo"}}}

    bot._upload_binary = fake_upload_binary  # type: ignore[assignment]
    token = await bot.upload(photo, "image")
    assert token == "tok-photo"


async def test_send_message_requires_target(bot):
    with pytest.raises(ValueError):
        await bot.send_message(text="orphan")
