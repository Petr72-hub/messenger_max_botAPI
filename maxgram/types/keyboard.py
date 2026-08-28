from __future__ import annotations

from typing import Any, Literal

from maxgram.enums import ButtonType, Intent
from maxgram.types.base import MaxObject


class Button(MaxObject):
    type: ButtonType
    text: str


class CallbackButton(Button):
    type: Literal[ButtonType.CALLBACK] = ButtonType.CALLBACK
    payload: str
    intent: Intent = Intent.DEFAULT


class LinkButton(Button):
    type: Literal[ButtonType.LINK] = ButtonType.LINK
    url: str


class RequestContactButton(Button):
    type: Literal[ButtonType.REQUEST_CONTACT] = ButtonType.REQUEST_CONTACT


class RequestGeoLocationButton(Button):
    type: Literal[ButtonType.REQUEST_GEO_LOCATION] = ButtonType.REQUEST_GEO_LOCATION
    quick: bool = False


class ChatButton(Button):
    """Creates a chat linked to the message when pressed."""

    type: Literal[ButtonType.CHAT] = ButtonType.CHAT
    chat_title: str | None = None
    chat_description: str | None = None
    start_payload: str | None = None
    uuid: int | None = None


class OpenAppButton(Button):
    type: Literal[ButtonType.OPEN_APP] = ButtonType.OPEN_APP
    web_app: dict[str, Any] | None = None
    contact_id: int | None = None


class MessageButton(Button):
    """Sends ``text`` back to the bot as a regular message."""

    type: Literal[ButtonType.MESSAGE] = ButtonType.MESSAGE


AnyButton = (
    CallbackButton
    | LinkButton
    | RequestContactButton
    | RequestGeoLocationButton
    | ChatButton
    | OpenAppButton
    | MessageButton
    | Button
)


class InlineKeyboardMarkup(MaxObject):
    """Rows of buttons.

    MAX transports keyboards as an attachment rather than a top-level field, but
    maxgram lets you pass this object as ``reply_markup=`` and wraps it for you.
    """

    buttons: list[list[AnyButton]] = []

    def to_attachment(self) -> dict[str, Any]:
        return {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [b.model_dump(exclude_none=True, mode="json") for b in row]
                    for row in self.buttons
                ]
            },
        }
