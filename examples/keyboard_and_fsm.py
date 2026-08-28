"""Inline keyboards, typed callback payloads and a two-step FSM form."""

import asyncio
import logging
import os

from maxgram import Bot, Dispatcher, Intent, Router
from maxgram.filters import CallbackData, Command
from maxgram.fsm import State, StatesGroup
from maxgram.types import Message, MessageCallback
from maxgram.utils import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

router = Router(name="demo")


class Vote(CallbackData, prefix="vote"):
    poll_id: int
    choice: str


class Feedback(StatesGroup):
    waiting_subject = State()
    waiting_body = State()


@router.message(Command("poll"))
async def send_poll(message: Message) -> None:
    kb = InlineKeyboardBuilder()
    kb.button(text="👍 Yes", payload=Vote(poll_id=1, choice="yes").pack(), intent=Intent.POSITIVE)
    kb.button(text="👎 No", payload=Vote(poll_id=1, choice="no").pack(), intent=Intent.NEGATIVE)
    kb.url("What is this?", "https://dev.max.ru/docs-api")
    kb.adjust(2, 1)
    await message.answer("Do you like maxgram?", reply_markup=kb.as_markup())


@router.callback_query(Vote.filter())
async def on_vote(event: MessageCallback, callback_data: Vote) -> None:
    await event.answer(f"Recorded: {callback_data.choice}")
    await event.edit_text(f"Thanks! You voted **{callback_data.choice}**.")


@router.message(Command("feedback"))
async def start_feedback(message: Message, state) -> None:
    await state.set_state(Feedback.waiting_subject)
    await message.answer("What is the subject?")


@router.message(Feedback.waiting_subject)
async def got_subject(message: Message, state) -> None:
    await state.update_data(subject=message.text)
    await state.set_state(Feedback.waiting_body)
    await message.answer("Now describe the issue.")


@router.message(Feedback.waiting_body)
async def got_body(message: Message, state) -> None:
    data = await state.update_data(body=message.text)
    await state.clear()
    await message.answer(f"Saved!\nSubject: {data['subject']}\nBody: {data['body']}")


async def main() -> None:
    dp = Dispatcher()
    dp.include_router(router)
    bot = Bot(os.environ["MAX_BOT_TOKEN"])
    async with bot:
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
