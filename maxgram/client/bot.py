"""The MAX Bot API client."""

from __future__ import annotations

import asyncio
import contextvars
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Sequence

from maxgram.client.default import DefaultBotProperties
from maxgram.client.session import AiohttpSession, BaseSession, RetryPolicy
from maxgram.client.throttle import RateLimiter
from maxgram.enums import SenderAction, TextFormat, UploadType
from maxgram.exceptions import AttachmentNotReady, MaxAPIError
from maxgram.types import (
    BotCommand,
    BotInfo,
    Chat,
    ChatList,
    ChatMember,
    ChatMembersList,
    CommentMessage,
    CommentsList,
    InlineKeyboardMarkup,
    Message,
    MessagesList,
    NewMessageLink,
    SubscriptionsList,
    UploadEndpoint,
    UploadedInfo,
    bind_tree,
)

logger = logging.getLogger(__name__)

_current_bot: contextvars.ContextVar["Bot | None"] = contextvars.ContextVar(
    "maxgram_current_bot", default=None
)

InputFile = str | Path | bytes | BinaryIO


class Bot:
    """Async client for ``https://platform-api2.max.ru``.

    Every method returns parsed models bound to this instance, which is what makes
    ``message.answer(...)`` and friends work without passing the bot around.

    ``Bot`` is an async context manager; entering it opens the HTTP session and
    exiting closes it.
    """

    def __init__(
        self,
        token: str,
        *,
        session: BaseSession | None = None,
        default: DefaultBotProperties | None = None,
        api_base: str = "https://platform-api2.max.ru",
        timeout: float = 60.0,
        retry: RetryPolicy | None = None,
        rate_limit: float = 2.0,
        proxy: str | None = None,
    ) -> None:
        if not token or not token.strip():
            raise ValueError("bot token must be a non-empty string")
        self.token = token.strip()
        self.default = default or DefaultBotProperties()
        self.session: BaseSession = session or AiohttpSession(
            self.token, api_base=api_base, timeout=timeout, retry=retry, proxy=proxy
        )
        self.limiter = RateLimiter(rate=rate_limit)
        self._me: BotInfo | None = None

    # -- plumbing --------------------------------------------------------------

    async def __aenter__(self) -> "Bot":
        _current_bot.set(self)
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self.session.close()

    @staticmethod
    def get_current() -> "Bot | None":
        """The bot bound to the running task, set by the Dispatcher."""
        return _current_bot.get()

    def _bind(self, obj: Any) -> Any:
        return bind_tree(obj, self)

    async def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        return await self.session.request(method, path, params=params, json_body=json_body)

    # -- bot profile -----------------------------------------------------------

    async def get_me(self, *, cached: bool = False) -> BotInfo:
        """``GET /me`` - identity and command list of the current bot."""
        if cached and self._me is not None:
            return self._me
        data = await self._call("GET", "/me")
        self._me = self._bind(BotInfo.model_validate(data))
        return self._me

    async def set_my_info(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        commands: Sequence[BotCommand | dict[str, Any]] | None = None,
        photo: dict[str, Any] | None = None,
    ) -> BotInfo:
        """``PATCH /me`` - update the bot's public profile."""
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if commands is not None:
            body["commands"] = [
                c.model_dump(exclude_none=True) if isinstance(c, BotCommand) else c
                for c in commands
            ]
        if photo is not None:
            body["photo"] = photo
        data = await self._call("PATCH", "/me", json_body=body)
        self._me = self._bind(BotInfo.model_validate(data))
        return self._me

    async def set_my_commands(
        self, commands: Sequence[BotCommand | dict[str, Any]]
    ) -> BotInfo:
        """``PATCH /me/commands`` - replace the command menu."""
        payload = [
            c.model_dump(exclude_none=True) if isinstance(c, BotCommand) else c for c in commands
        ]
        data = await self._call("PATCH", "/me/commands", json_body={"commands": payload})
        return self._bind(BotInfo.model_validate(data))

    # -- chats -----------------------------------------------------------------

    async def get_chats(self, *, count: int = 50, marker: int | None = None) -> ChatList:
        """``GET /chats`` - chats and channels the bot participates in.

        Deprecated by MAX in favour of maintaining your own chat registry from
        ``bot_added`` / ``bot_removed`` events; kept because it still answers.
        """
        data = await self._call("GET", "/chats", params={"count": count, "marker": marker})
        return self._bind(ChatList.model_validate(data))

    async def get_chat(self, chat_id: int) -> Chat:
        """``GET /chats/{chatId}``."""
        data = await self._call("GET", f"/chats/{chat_id}")
        return self._bind(Chat.model_validate(data))

    async def get_chat_by_link(self, link: str) -> Chat:
        """``GET /chats/{chatLink}`` - resolve a public ``@name`` or invite link."""
        data = await self._call("GET", f"/chats/{link.lstrip('@')}")
        return self._bind(Chat.model_validate(data))

    async def edit_chat(
        self,
        chat_id: int,
        *,
        title: str | None = None,
        icon: dict[str, Any] | None = None,
        pin: str | None = None,
        notify: bool | None = None,
    ) -> Chat:
        """``PATCH /chats/{chatId}``."""
        body = {"title": title, "icon": icon, "pin": pin, "notify": notify}
        data = await self._call(
            "PATCH", f"/chats/{chat_id}", json_body={k: v for k, v in body.items() if v is not None}
        )
        return self._bind(Chat.model_validate(data))

    async def send_chat_action(
        self, chat_id: int, action: SenderAction | str = SenderAction.TYPING_ON
    ) -> bool:
        """``POST /chats/{chatId}/actions`` - the "typing…" indicator and friends."""
        data = await self._call(
            "POST", f"/chats/{chat_id}/actions", json_body={"action": str(action)}
        )
        return bool(data.get("success", True))

    async def leave_chat(self, chat_id: int) -> bool:
        """``DELETE /chats/{chatId}/members/me``."""
        data = await self._call("DELETE", f"/chats/{chat_id}/members/me")
        return bool(data.get("success", True))

    async def get_pinned_message(self, chat_id: int) -> Message | None:
        data = await self._call("GET", f"/chats/{chat_id}/pin")
        message = data.get("message")
        return self._bind(Message.model_validate(message)) if message else None

    async def pin_message(self, chat_id: int, message_id: str, *, notify: bool = True) -> bool:
        data = await self._call(
            "PUT", f"/chats/{chat_id}/pin", json_body={"message_id": message_id, "notify": notify}
        )
        return bool(data.get("success", True))

    async def unpin_message(self, chat_id: int) -> bool:
        data = await self._call("DELETE", f"/chats/{chat_id}/pin")
        return bool(data.get("success", True))

    async def get_my_membership(self, chat_id: int) -> ChatMember:
        data = await self._call("GET", f"/chats/{chat_id}/members/me")
        return self._bind(ChatMember.model_validate(data))

    async def get_chat_admins(self, chat_id: int) -> ChatMembersList:
        data = await self._call("GET", f"/chats/{chat_id}/members/admins")
        return self._bind(ChatMembersList.model_validate(data))

    async def add_chat_admins(self, chat_id: int, admins: Sequence[dict[str, Any]]) -> bool:
        data = await self._call(
            "POST", f"/chats/{chat_id}/members/admins", json_body={"admins": list(admins)}
        )
        return bool(data.get("success", True))

    async def remove_chat_admin(self, chat_id: int, user_id: int) -> bool:
        data = await self._call("DELETE", f"/chats/{chat_id}/members/admins/{user_id}")
        return bool(data.get("success", True))

    async def get_chat_members(
        self,
        chat_id: int,
        *,
        user_ids: Sequence[int] | None = None,
        marker: int | None = None,
        count: int = 20,
    ) -> ChatMembersList:
        data = await self._call(
            "GET",
            f"/chats/{chat_id}/members",
            params={"user_ids": user_ids, "marker": marker, "count": count},
        )
        return self._bind(ChatMembersList.model_validate(data))

    async def add_chat_members(self, chat_id: int, user_ids: Sequence[int]) -> bool:
        data = await self._call(
            "POST", f"/chats/{chat_id}/members", json_body={"user_ids": list(user_ids)}
        )
        return bool(data.get("success", True))

    async def remove_chat_member(
        self, chat_id: int, user_id: int, *, block: bool = False
    ) -> bool:
        data = await self._call(
            "DELETE", f"/chats/{chat_id}/members", params={"user_id": user_id, "block": block}
        )
        return bool(data.get("success", True))

    # -- messages --------------------------------------------------------------

    async def send_message(
        self,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        attachments: Sequence[Any] | None = None,
        reply_markup: InlineKeyboardMarkup | Sequence[Sequence[Any]] | None = None,
        link: NewMessageLink | dict[str, Any] | None = None,
        notify: bool | None = None,
        parse_mode: TextFormat | str | None = None,
        disable_link_preview: bool | None = None,
    ) -> Message:
        """``POST /messages`` - send to a chat/channel (``chat_id``) or a user (``user_id``).

        ``attachments`` accepts raw dicts (use the helpers in :mod:`maxgram.types`)
        and ``reply_markup`` is folded into the attachment list automatically.
        """
        if chat_id is None and user_id is None:
            raise ValueError("send_message requires either chat_id or user_id")

        body = self._build_message_body(
            text=text,
            attachments=attachments,
            reply_markup=reply_markup,
            link=link,
            notify=notify,
            parse_mode=parse_mode,
        )
        preview = (
            disable_link_preview
            if disable_link_preview is not None
            else self.default.disable_link_preview
        )
        await self.limiter.acquire(chat_id or user_id)
        data = await self._call(
            "POST",
            "/messages",
            params={
                "chat_id": chat_id,
                "user_id": user_id,
                "disable_link_preview": preview,
            },
            json_body=body,
        )
        return self._bind(Message.model_validate(data["message"]))

    async def edit_message(
        self,
        message_id: str,
        *,
        text: str | None = None,
        attachments: Sequence[Any] | None = None,
        reply_markup: InlineKeyboardMarkup | Sequence[Sequence[Any]] | None = None,
        link: NewMessageLink | dict[str, Any] | None = None,
        notify: bool | None = None,
        parse_mode: TextFormat | str | None = None,
    ) -> bool:
        """``PUT /messages`` - replace the body of an existing message.

        Passing ``attachments=[]`` strips every attachment, including the keyboard.
        """
        body = self._build_message_body(
            text=text,
            attachments=attachments,
            reply_markup=reply_markup,
            link=link,
            notify=notify,
            parse_mode=parse_mode,
        )
        data = await self._call(
            "PUT", "/messages", params={"message_id": message_id}, json_body=body
        )
        return bool(data.get("success", True))

    async def delete_message(self, message_id: str) -> bool:
        """``DELETE /messages``."""
        data = await self._call("DELETE", "/messages", params={"message_id": message_id})
        return bool(data.get("success", True))

    async def get_message(self, message_id: str) -> Message:
        """``GET /messages/{messageId}``."""
        data = await self._call("GET", f"/messages/{message_id}")
        return self._bind(Message.model_validate(data))

    async def get_messages(
        self,
        *,
        chat_id: int | None = None,
        message_ids: Sequence[str] | None = None,
        from_time: int | None = None,
        to_time: int | None = None,
        count: int = 50,
    ) -> MessagesList:
        """``GET /messages`` - history slice or a batch lookup by id."""
        data = await self._call(
            "GET",
            "/messages",
            params={
                "chat_id": chat_id,
                "message_ids": message_ids,
                "from": from_time,
                "to": to_time,
                "count": count,
            },
        )
        return self._bind(MessagesList.model_validate(data))

    async def get_video(self, video_token: str) -> dict[str, Any]:
        """``GET /videos/{videoToken}`` - playback urls for an uploaded video."""
        return await self._call("GET", f"/videos/{video_token}")

    async def answer_callback(
        self,
        callback_id: str,
        *,
        notification: str | None = None,
        message: Any = None,
        show_alert: bool = False,
    ) -> bool:
        """``POST /answers`` - close the loading state on a pressed inline button."""
        body: dict[str, Any] = {}
        if notification is not None:
            body["notification"] = notification
        if message is not None:
            body["message"] = (
                message if isinstance(message, dict) else self._build_message_body(text=message)
            )
        if show_alert:
            body["show_alert"] = True
        data = await self._call(
            "POST", "/answers", params={"callback_id": callback_id}, json_body=body
        )
        return bool(data.get("success", True))

    # -- comments --------------------------------------------------------------

    async def get_comments(
        self, message_id: str, *, count: int = 50, marker: int | None = None
    ) -> CommentsList:
        data = await self._call(
            "GET", f"/messages/{message_id}/comments", params={"count": count, "marker": marker}
        )
        return self._bind(CommentsList.model_validate(data))

    async def send_comment(
        self,
        message_id: str,
        *,
        text: str | None = None,
        attachments: Sequence[Any] | None = None,
        reply_to: str | None = None,
        parse_mode: TextFormat | str | None = None,
    ) -> CommentMessage:
        body = self._build_message_body(
            text=text, attachments=attachments, parse_mode=parse_mode
        )
        if reply_to:
            body["reply_to"] = reply_to
        data = await self._call("POST", f"/messages/{message_id}/comments", json_body=body)
        return self._bind(CommentMessage.model_validate(data.get("comment", data)))

    async def edit_comment(
        self, message_id: str, comment_id: str, *, text: str | None = None, **kwargs: Any
    ) -> bool:
        body = self._build_message_body(text=text, **kwargs)
        data = await self._call(
            "PUT",
            f"/messages/{message_id}/comments",
            params={"comment_id": comment_id},
            json_body=body,
        )
        return bool(data.get("success", True))

    async def delete_comment(self, message_id: str, comment_id: str) -> bool:
        data = await self._call(
            "DELETE", f"/messages/{message_id}/comments", params={"comment_id": comment_id}
        )
        return bool(data.get("success", True))

    # -- uploads ---------------------------------------------------------------

    async def get_upload_url(self, upload_type: UploadType | str) -> UploadEndpoint:
        """``POST /uploads`` - reserve a slot and receive the upload URL."""
        data = await self._call("POST", "/uploads", params={"type": str(upload_type)})
        return UploadEndpoint.model_validate(data)

    async def upload(
        self, file: InputFile, upload_type: UploadType | str, *, filename: str | None = None
    ) -> str:
        """Run the two-step upload and return the attachment token.

        ``file`` may be a filesystem path, raw ``bytes`` or an open binary handle.
        """
        payload, resolved_name = _read_input_file(file, filename)
        endpoint = await self.get_upload_url(upload_type)
        content_type = mimetypes.guess_type(resolved_name)[0]
        result = await self._upload_binary(
            endpoint.url, payload, resolved_name, content_type=content_type
        )
        info = UploadedInfo.model_validate(result if isinstance(result, dict) else {})
        token = info.any_token or endpoint.token
        if not token:
            raise MaxAPIError(
                method="POST <upload-url>",
                message=f"upload of {resolved_name} returned no token",
            )
        return token

    async def _upload_binary(
        self, url: str, data: bytes, filename: str, *, content_type: str | None
    ) -> Any:
        session = self.session
        if not isinstance(session, AiohttpSession):
            raise TypeError("custom sessions must implement upload_file to support uploads")
        return await session.upload_file(
            url, data=data, filename=filename, content_type=content_type
        )

    async def send_photo(
        self,
        *,
        photo: InputFile,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        **kwargs: Any,
    ) -> Message:
        """Upload (or link) an image and send it, optionally with a caption."""
        attachment = await self._media_attachment(photo, UploadType.IMAGE)
        return await self._send_media(
            attachment, chat_id=chat_id, user_id=user_id, text=text, **kwargs
        )

    async def send_video(
        self,
        *,
        video: InputFile,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        **kwargs: Any,
    ) -> Message:
        attachment = await self._media_attachment(video, UploadType.VIDEO)
        return await self._send_media(
            attachment, chat_id=chat_id, user_id=user_id, text=text, **kwargs
        )

    async def send_audio(
        self,
        *,
        audio: InputFile,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        **kwargs: Any,
    ) -> Message:
        attachment = await self._media_attachment(audio, UploadType.AUDIO)
        return await self._send_media(
            attachment, chat_id=chat_id, user_id=user_id, text=text, **kwargs
        )

    async def send_document(
        self,
        *,
        document: InputFile,
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        **kwargs: Any,
    ) -> Message:
        attachment = await self._media_attachment(document, UploadType.FILE)
        return await self._send_media(
            attachment, chat_id=chat_id, user_id=user_id, text=text, **kwargs
        )

    async def send_media_group(
        self,
        *,
        photos: Iterable[InputFile],
        chat_id: int | None = None,
        user_id: int | None = None,
        text: str | None = None,
        **kwargs: Any,
    ) -> Message:
        """Send several images as one album."""
        attachments = [await self._media_attachment(p, UploadType.IMAGE) for p in photos]
        return await self.send_message_with_retry(
            chat_id=chat_id, user_id=user_id, text=text, attachments=attachments, **kwargs
        )

    async def _media_attachment(
        self, source: InputFile, upload_type: UploadType
    ) -> dict[str, Any]:
        if isinstance(source, str) and source.startswith(("http://", "https://")):
            return {"type": str(upload_type), "payload": {"url": source}}
        token = await self.upload(source, upload_type)
        return {"type": str(upload_type), "payload": {"token": token}}

    async def _send_media(self, attachment: dict[str, Any], **kwargs: Any) -> Message:
        return await self.send_message_with_retry(attachments=[attachment], **kwargs)

    async def send_message_with_retry(
        self, *, attempts: int = 5, delay: float = 2.0, **kwargs: Any
    ) -> Message:
        """``send_message`` that waits out ``attachment.not.ready``.

        Freshly uploaded video and audio need a moment on MAX's side before they
        can be attached; without this the first send after an upload often fails.
        """
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                return await self.send_message(**kwargs)
            except AttachmentNotReady as exc:
                last = exc
                wait = delay * (attempt + 1)
                logger.info("attachment not ready, retrying in %.1fs", wait)
                await asyncio.sleep(wait)
        raise last  # type: ignore[misc]

    # -- webhooks & polling transport -----------------------------------------

    async def get_updates(
        self,
        *,
        limit: int = 100,
        timeout: int = 30,
        marker: int | None = None,
        types: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """``GET /updates`` - long polling. Returns the raw ``{updates, marker}`` dict."""
        return await self._call(
            "GET",
            "/updates",
            params={"limit": limit, "timeout": timeout, "marker": marker, "types": types},
        )

    async def get_subscriptions(self) -> SubscriptionsList:
        """``GET /subscriptions`` - currently registered webhooks."""
        data = await self._call("GET", "/subscriptions")
        return self._bind(SubscriptionsList.model_validate(data))

    async def set_webhook(
        self,
        url: str,
        *,
        update_types: Sequence[str] | None = None,
        secret: str | None = None,
        version: str | None = None,
    ) -> bool:
        """``POST /subscriptions`` - start delivering events to ``url``."""
        body: dict[str, Any] = {"url": url}
        if update_types:
            body["update_types"] = list(update_types)
        if secret:
            body["secret"] = secret
        if version:
            body["version"] = version
        data = await self._call("POST", "/subscriptions", json_body=body)
        return bool(data.get("success", True))

    async def delete_webhook(self, url: str) -> bool:
        """``DELETE /subscriptions``."""
        data = await self._call("DELETE", "/subscriptions", params={"url": url})
        return bool(data.get("success", True))

    # -- helpers ---------------------------------------------------------------

    def _build_message_body(
        self,
        *,
        text: str | None = None,
        attachments: Sequence[Any] | None = None,
        reply_markup: InlineKeyboardMarkup | Sequence[Sequence[Any]] | None = None,
        link: NewMessageLink | dict[str, Any] | None = None,
        notify: bool | None = None,
        parse_mode: TextFormat | str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}

        if text is not None:
            body["text"] = text

        prepared = [_serialize_attachment(a) for a in attachments] if attachments else []
        if reply_markup is not None:
            prepared.append(_serialize_keyboard(reply_markup))
        if attachments is not None or reply_markup is not None:
            body["attachments"] = prepared

        if link is not None:
            body["link"] = (
                link.model_dump(exclude_none=True, mode="json")
                if isinstance(link, NewMessageLink)
                else link
            )

        notify_value = notify if notify is not None else self.default.notify
        if notify_value is not None:
            body["notify"] = notify_value

        fmt = parse_mode if parse_mode is not None else self.default.parse_mode
        if fmt is not None:
            body["format"] = str(fmt)

        return body


def _serialize_attachment(attachment: Any) -> dict[str, Any]:
    if isinstance(attachment, dict):
        return attachment
    if isinstance(attachment, InlineKeyboardMarkup):
        return attachment.to_attachment()
    if hasattr(attachment, "model_dump"):
        return attachment.model_dump(exclude_none=True, mode="json")
    raise TypeError(f"unsupported attachment type: {type(attachment).__name__}")


def _serialize_keyboard(
    markup: InlineKeyboardMarkup | Sequence[Sequence[Any]],
) -> dict[str, Any]:
    if isinstance(markup, InlineKeyboardMarkup):
        return markup.to_attachment()
    rows = [
        [b if isinstance(b, dict) else b.model_dump(exclude_none=True, mode="json") for b in row]
        for row in markup
    ]
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


def _read_input_file(file: InputFile, filename: str | None) -> tuple[bytes, str]:
    if isinstance(file, bytes):
        return file, filename or "upload.bin"
    if isinstance(file, (str, Path)):
        path = Path(file)
        return path.read_bytes(), filename or path.name
    data = file.read()
    name = filename or os.path.basename(getattr(file, "name", "") or "upload.bin")
    return data, name
