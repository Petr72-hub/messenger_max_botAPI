"""String enums mirroring the MAX Bot API vocabulary."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class UpdateType(StrEnum):
    MESSAGE_CREATED = "message_created"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_REMOVED = "message_removed"
    MESSAGE_CALLBACK = "message_callback"
    MESSAGE_CHAT_CREATED = "message_chat_created"
    BOT_ADDED = "bot_added"
    BOT_REMOVED = "bot_removed"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    USER_ADDED = "user_added"
    USER_REMOVED = "user_removed"
    CHAT_TITLE_CHANGED = "chat_title_changed"
    DIALOG_CLEARED = "dialog_cleared"
    DIALOG_REMOVED = "dialog_removed"
    DIALOG_MUTED = "dialog_muted"
    DIALOG_UNMUTED = "dialog_unmuted"
    COMMENT_CREATED = "comment_created"
    COMMENT_EDITED = "comment_edited"
    COMMENT_REMOVED = "comment_removed"


class ChatType(StrEnum):
    DIALOG = "dialog"
    CHAT = "chat"
    CHANNEL = "channel"


class ChatStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"
    LEFT = "left"
    CLOSED = "closed"
    SUSPENDED = "suspended"


class AttachmentType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    STICKER = "sticker"
    CONTACT = "contact"
    INLINE_KEYBOARD = "inline_keyboard"
    LOCATION = "location"
    SHARE = "share"
    DATA = "data"


class UploadType(StrEnum):
    """Values accepted by ``POST /uploads?type=``."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"


class ButtonType(StrEnum):
    CALLBACK = "callback"
    LINK = "link"
    REQUEST_CONTACT = "request_contact"
    REQUEST_GEO_LOCATION = "request_geo_location"
    CHAT = "chat"
    OPEN_APP = "open_app"
    MESSAGE = "message"


class Intent(StrEnum):
    """Visual accent of a callback button."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    DEFAULT = "default"


class TextFormat(StrEnum):
    MARKDOWN = "markdown"
    HTML = "html"


class SenderAction(StrEnum):
    TYPING_ON = "typing_on"
    SENDING_PHOTO = "sending_photo"
    SENDING_VIDEO = "sending_video"
    SENDING_AUDIO = "sending_audio"
    SENDING_FILE = "sending_file"
    MARK_SEEN = "mark_seen"


class MessageLinkType(StrEnum):
    FORWARD = "forward"
    REPLY = "reply"


class ChatAdminPermission(StrEnum):
    READ_ALL_MESSAGES = "read_all_messages"
    ADD_REMOVE_MEMBERS = "add_remove_members"
    ADD_ADMINS = "add_admins"
    CHANGE_CHAT_INFO = "change_chat_info"
    PIN_MESSAGE = "pin_message"
    WRITE = "write"


class MarkupType(StrEnum):
    """Rich-text markup element kinds returned inside ``MessageBody.markup``."""

    STRONG = "strong"
    EMPHASIZED = "emphasized"
    MONOSPACED = "monospaced"
    LINK = "link"
    STRIKETHROUGH = "strikethrough"
    UNDERLINE = "underline"
    USER_MENTION = "user_mention"
    HEADING = "heading"
    HIGHLIGHTED = "highlighted"
    CODE_BLOCK = "code_block"
