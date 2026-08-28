from __future__ import annotations

from typing import TYPE_CHECKING, Any

from maxgram.enums import ChatStatus, ChatType
from maxgram.types.base import MaxObject
from maxgram.types.user import User

if TYPE_CHECKING:
    from maxgram.types.message import Message


class Image(MaxObject):
    url: str


class Chat(MaxObject):
    chat_id: int
    type: ChatType
    status: ChatStatus | None = None
    title: str | None = None
    icon: Image | None = None
    last_event_time: int | None = None
    participants_count: int | None = None
    owner_id: int | None = None
    participants: dict[str, int] | None = None
    is_public: bool | None = None
    link: str | None = None
    description: str | None = None
    dialog_with_user: User | None = None
    messages_count: int | None = None
    chat_message_id: str | None = None
    pinned_message: "Message | None" = None

    @property
    def is_channel(self) -> bool:
        return self.type == ChatType.CHANNEL

    @property
    def is_dialog(self) -> bool:
        return self.type == ChatType.DIALOG

    @property
    def full_title(self) -> str:
        if self.title:
            return self.title
        if self.dialog_with_user:
            return self.dialog_with_user.full_name
        return str(self.chat_id)

    async def send(self, text: str | None = None, **kwargs: Any) -> "Message":
        return await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)

    async def leave(self) -> bool:
        return await self.bot.leave_chat(self.chat_id)

    async def pin(self, message_id: str, notify: bool = True) -> bool:
        return await self.bot.pin_message(self.chat_id, message_id, notify=notify)


class ChatList(MaxObject):
    chats: list[Chat] = []
    marker: int | None = None


class ChatPatch(MaxObject):
    icon: dict[str, Any] | None = None
    title: str | None = None
    pin: str | None = None
    notify: bool | None = None
