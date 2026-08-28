from __future__ import annotations

from typing import Any, Literal

from maxgram.enums import UpdateType
from maxgram.types.base import MaxObject
from maxgram.types.chat import Chat
from maxgram.types.message import Callback, CommentMessage, Message
from maxgram.types.user import User


class Update(MaxObject):
    update_type: UpdateType
    timestamp: int

    @property
    def event_type(self) -> str:
        return str(self.update_type)


class MessageCreated(Update):
    update_type: Literal[UpdateType.MESSAGE_CREATED] = UpdateType.MESSAGE_CREATED
    message: Message
    user_locale: str | None = None


class MessageEdited(Update):
    update_type: Literal[UpdateType.MESSAGE_EDITED] = UpdateType.MESSAGE_EDITED
    message: Message


class MessageRemoved(Update):
    update_type: Literal[UpdateType.MESSAGE_REMOVED] = UpdateType.MESSAGE_REMOVED
    message_id: str
    chat_id: int | None = None
    user_id: int | None = None


class MessageCallback(Update):
    update_type: Literal[UpdateType.MESSAGE_CALLBACK] = UpdateType.MESSAGE_CALLBACK
    callback: Callback
    message: Message | None = None
    user_locale: str | None = None

    # -- aiogram-flavoured shortcuts ------------------------------------------

    @property
    def id(self) -> str:
        return self.callback.callback_id

    @property
    def data(self) -> str | None:
        return self.callback.payload

    @property
    def from_user(self) -> User:
        return self.callback.user

    async def answer(
        self,
        text: str | None = None,
        *,
        show_alert: bool = False,
        message: Any = None,
    ) -> bool:
        """Acknowledge the button press.

        ``text`` becomes a toast notification, ``message`` replaces the original
        message body (MAX merges both into one ``POST /answers`` call).
        """
        return await self.bot.answer_callback(
            callback_id=self.callback.callback_id,
            notification=text,
            message=message,
            show_alert=show_alert,
        )

    async def edit_text(self, text: str, **kwargs: Any) -> bool:
        if self.message is None:
            raise ValueError("callback has no attached message to edit")
        return await self.message.edit(text=text, **kwargs)


class MessageChatCreated(Update):
    update_type: Literal[UpdateType.MESSAGE_CHAT_CREATED] = UpdateType.MESSAGE_CHAT_CREATED
    chat: Chat
    message_id: str | None = None
    start_payload: str | None = None


class BotAdded(Update):
    update_type: Literal[UpdateType.BOT_ADDED] = UpdateType.BOT_ADDED
    chat_id: int
    user: User
    is_channel: bool = False


class BotRemoved(Update):
    update_type: Literal[UpdateType.BOT_REMOVED] = UpdateType.BOT_REMOVED
    chat_id: int
    user: User
    is_channel: bool = False


class BotStarted(Update):
    update_type: Literal[UpdateType.BOT_STARTED] = UpdateType.BOT_STARTED
    chat_id: int
    user: User
    payload: str | None = None
    user_locale: str | None = None


class BotStopped(Update):
    update_type: Literal[UpdateType.BOT_STOPPED] = UpdateType.BOT_STOPPED
    chat_id: int | None = None
    user: User | None = None


class UserAdded(Update):
    update_type: Literal[UpdateType.USER_ADDED] = UpdateType.USER_ADDED
    chat_id: int
    user: User
    inviter_id: int | None = None
    is_channel: bool = False


class UserRemoved(Update):
    update_type: Literal[UpdateType.USER_REMOVED] = UpdateType.USER_REMOVED
    chat_id: int
    user: User
    admin_id: int | None = None
    is_channel: bool = False


class ChatTitleChanged(Update):
    update_type: Literal[UpdateType.CHAT_TITLE_CHANGED] = UpdateType.CHAT_TITLE_CHANGED
    chat_id: int
    user: User
    title: str


class DialogCleared(Update):
    update_type: Literal[UpdateType.DIALOG_CLEARED] = UpdateType.DIALOG_CLEARED
    chat_id: int | None = None
    user: User | None = None


class DialogRemoved(Update):
    update_type: Literal[UpdateType.DIALOG_REMOVED] = UpdateType.DIALOG_REMOVED
    chat_id: int | None = None
    user: User | None = None


class DialogMuted(Update):
    update_type: Literal[UpdateType.DIALOG_MUTED] = UpdateType.DIALOG_MUTED
    chat_id: int | None = None
    user: User | None = None
    muted_until: int | None = None


class DialogUnmuted(Update):
    update_type: Literal[UpdateType.DIALOG_UNMUTED] = UpdateType.DIALOG_UNMUTED
    chat_id: int | None = None
    user: User | None = None


class CommentCreated(Update):
    update_type: Literal[UpdateType.COMMENT_CREATED] = UpdateType.COMMENT_CREATED
    chat_id: int | None = None
    message_id: str | None = None
    comment: CommentMessage | None = None


class CommentEdited(Update):
    update_type: Literal[UpdateType.COMMENT_EDITED] = UpdateType.COMMENT_EDITED
    chat_id: int | None = None
    message_id: str | None = None
    comment: CommentMessage | None = None


class CommentRemoved(Update):
    update_type: Literal[UpdateType.COMMENT_REMOVED] = UpdateType.COMMENT_REMOVED
    chat_id: int | None = None
    message_id: str | None = None
    comment_id: str | None = None


UPDATE_MODELS: dict[str, type[Update]] = {
    UpdateType.MESSAGE_CREATED.value: MessageCreated,
    UpdateType.MESSAGE_EDITED.value: MessageEdited,
    UpdateType.MESSAGE_REMOVED.value: MessageRemoved,
    UpdateType.MESSAGE_CALLBACK.value: MessageCallback,
    UpdateType.MESSAGE_CHAT_CREATED.value: MessageChatCreated,
    UpdateType.BOT_ADDED.value: BotAdded,
    UpdateType.BOT_REMOVED.value: BotRemoved,
    UpdateType.BOT_STARTED.value: BotStarted,
    UpdateType.BOT_STOPPED.value: BotStopped,
    UpdateType.USER_ADDED.value: UserAdded,
    UpdateType.USER_REMOVED.value: UserRemoved,
    UpdateType.CHAT_TITLE_CHANGED.value: ChatTitleChanged,
    UpdateType.DIALOG_CLEARED.value: DialogCleared,
    UpdateType.DIALOG_REMOVED.value: DialogRemoved,
    UpdateType.DIALOG_MUTED.value: DialogMuted,
    UpdateType.DIALOG_UNMUTED.value: DialogUnmuted,
    UpdateType.COMMENT_CREATED.value: CommentCreated,
    UpdateType.COMMENT_EDITED.value: CommentEdited,
    UpdateType.COMMENT_REMOVED.value: CommentRemoved,
}


def parse_update(raw: dict[str, Any]) -> Update:
    """Turn a raw JSON event into the matching typed model.

    Unknown event types degrade to the generic :class:`Update` instead of raising,
    so a server-side addition never takes a running bot down.
    """
    model = UPDATE_MODELS.get(str(raw.get("update_type")))
    if model is None:
        return Update.model_validate(raw)
    return model.model_validate(raw)


class UpdatesList(MaxObject):
    updates: list[dict[str, Any]] = []
    marker: int | None = None


class Subscription(MaxObject):
    url: str
    time: int | None = None
    update_types: list[str] | None = None
    version: str | None = None


class SubscriptionsList(MaxObject):
    subscriptions: list[Subscription] = []
