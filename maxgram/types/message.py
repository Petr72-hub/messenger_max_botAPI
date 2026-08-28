from __future__ import annotations

from typing import TYPE_CHECKING, Any

from maxgram.enums import ChatType, MarkupType, MessageLinkType
from maxgram.types.attachments import AnyAttachment
from maxgram.types.base import MaxObject
from maxgram.types.user import User

if TYPE_CHECKING:
    from maxgram.types.keyboard import InlineKeyboardMarkup


class MarkupElement(MaxObject):
    """One rich-text span inside :attr:`MessageBody.markup`."""

    type: MarkupType
    from_: int = 0
    length: int = 0
    url: str | None = None
    user_link: str | None = None
    user_id: int | None = None
    language: str | None = None
    level: int | None = None

    def __init__(self, **data: Any) -> None:
        if "from" in data:
            data["from_"] = data.pop("from")
        super().__init__(**data)


class Recipient(MaxObject):
    chat_id: int | None = None
    chat_type: ChatType | None = None
    user_id: int | None = None


class MessageStat(MaxObject):
    views: int = 0


class MessageBody(MaxObject):
    mid: str
    seq: int | None = None
    text: str | None = None
    attachments: list[AnyAttachment] | None = None
    markup: list[MarkupElement] | None = None


class LinkedMessage(MaxObject):
    type: MessageLinkType
    sender: User | None = None
    chat_id: int | None = None
    message: MessageBody | None = None


class Message(MaxObject):
    sender: User | None = None
    recipient: Recipient
    timestamp: int
    link: LinkedMessage | None = None
    body: MessageBody | None = None
    stat: MessageStat | None = None
    url: str | None = None

    # -- convenience accessors -------------------------------------------------

    @property
    def message_id(self) -> str:
        if self.body is None:
            raise ValueError("message has no body, message_id is unavailable")
        return self.body.mid

    @property
    def mid(self) -> str:
        return self.message_id

    @property
    def text(self) -> str | None:
        return self.body.text if self.body else None

    @property
    def attachments(self) -> list[AnyAttachment]:
        if self.body is None or self.body.attachments is None:
            return []
        return self.body.attachments

    @property
    def chat_id(self) -> int | None:
        return self.recipient.chat_id

    @property
    def user_id(self) -> int | None:
        return self.recipient.user_id

    @property
    def chat_type(self) -> ChatType | None:
        return self.recipient.chat_type

    @property
    def from_user(self) -> User | None:
        return self.sender

    @property
    def content_type(self) -> str:
        atts = self.attachments
        if atts:
            return str(getattr(atts[0], "type", "unknown"))
        if self.text:
            return "text"
        return "unknown"

    @property
    def is_channel_post(self) -> bool:
        return self.recipient.chat_type == ChatType.CHANNEL

    @property
    def reply_to(self) -> MessageBody | None:
        if self.link and self.link.type == MessageLinkType.REPLY:
            return self.link.message
        return None

    @property
    def forwarded_from(self) -> MessageBody | None:
        if self.link and self.link.type == MessageLinkType.FORWARD:
            return self.link.message
        return None

    # -- shortcuts -------------------------------------------------------------

    def _target(self) -> dict[str, Any]:
        if self.recipient.chat_id is not None:
            return {"chat_id": self.recipient.chat_id}
        return {"user_id": self.recipient.user_id}

    async def answer(
        self,
        text: str | None = None,
        *,
        attachments: list[Any] | None = None,
        reply_markup: "InlineKeyboardMarkup | None" = None,
        **kwargs: Any,
    ) -> "Message":
        """Send a new message into the same conversation."""
        return await self.bot.send_message(
            text=text,
            attachments=attachments,
            reply_markup=reply_markup,
            **self._target(),
            **kwargs,
        )

    async def reply(
        self,
        text: str | None = None,
        *,
        attachments: list[Any] | None = None,
        reply_markup: "InlineKeyboardMarkup | None" = None,
        **kwargs: Any,
    ) -> "Message":
        """Send a message quoting this one."""
        return await self.bot.send_message(
            text=text,
            attachments=attachments,
            reply_markup=reply_markup,
            link=NewMessageLink(type=MessageLinkType.REPLY, mid=self.message_id),
            **self._target(),
            **kwargs,
        )

    async def forward(self, chat_id: int | None = None, user_id: int | None = None) -> "Message":
        return await self.bot.send_message(
            chat_id=chat_id,
            user_id=user_id,
            link=NewMessageLink(type=MessageLinkType.FORWARD, mid=self.message_id),
        )

    async def edit(
        self,
        text: str | None = None,
        *,
        attachments: list[Any] | None = None,
        reply_markup: "InlineKeyboardMarkup | None" = None,
        **kwargs: Any,
    ) -> bool:
        return await self.bot.edit_message(
            message_id=self.message_id,
            text=text,
            attachments=attachments,
            reply_markup=reply_markup,
            **kwargs,
        )

    async def delete(self) -> bool:
        return await self.bot.delete_message(self.message_id)

    async def pin(self, notify: bool = True) -> bool:
        if self.recipient.chat_id is None:
            raise ValueError("only chat messages can be pinned")
        return await self.bot.pin_message(self.recipient.chat_id, self.message_id, notify=notify)

    async def answer_photo(self, path_or_url: str, caption: str | None = None, **kwargs: Any):
        return await self.bot.send_photo(
            photo=path_or_url, text=caption, **self._target(), **kwargs
        )

    async def answer_video(self, path_or_url: str, caption: str | None = None, **kwargs: Any):
        return await self.bot.send_video(
            video=path_or_url, text=caption, **self._target(), **kwargs
        )

    async def answer_document(self, path_or_url: str, caption: str | None = None, **kwargs: Any):
        return await self.bot.send_document(
            document=path_or_url, text=caption, **self._target(), **kwargs
        )


class NewMessageLink(MaxObject):
    type: MessageLinkType
    mid: str


class SendMessageResult(MaxObject):
    message: Message


class MessagesList(MaxObject):
    messages: list[Message] = []


class SimpleQueryResult(MaxObject):
    success: bool
    message: str | None = None


class Callback(MaxObject):
    """Payload of a pressed inline button."""

    timestamp: int
    callback_id: str
    payload: str | None = None
    user: User


class CommentMessage(MaxObject):
    """A comment under a channel post."""

    comment_id: str | None = None
    sender: User | None = None
    timestamp: int | None = None
    body: MessageBody | None = None
    reply_to: str | None = None

    @property
    def text(self) -> str | None:
        return self.body.text if self.body else None


class CommentsList(MaxObject):
    comments: list[CommentMessage] = []
    marker: int | None = None
