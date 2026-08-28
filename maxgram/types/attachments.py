from __future__ import annotations

from typing import Any, Literal

from maxgram.enums import AttachmentType
from maxgram.types.base import MaxObject
from maxgram.types.keyboard import InlineKeyboardMarkup
from maxgram.types.user import User


class PhotoPayload(MaxObject):
    photo_id: int | None = None
    token: str | None = None
    url: str | None = None


class MediaPayload(MaxObject):
    url: str | None = None
    token: str | None = None


class FilePayload(MaxObject):
    url: str | None = None
    token: str | None = None
    fid: int | None = None


class StickerPayload(MaxObject):
    url: str | None = None
    code: str | None = None


class ContactPayload(MaxObject):
    vcf_info: str | None = None
    max_info: User | None = None


class SharePayload(MaxObject):
    url: str | None = None
    token: str | None = None


class Attachment(MaxObject):
    type: AttachmentType


class PhotoAttachment(Attachment):
    type: Literal[AttachmentType.IMAGE] = AttachmentType.IMAGE
    payload: PhotoPayload


class VideoAttachment(Attachment):
    type: Literal[AttachmentType.VIDEO] = AttachmentType.VIDEO
    payload: MediaPayload
    thumbnail: dict[str, Any] | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None


class AudioAttachment(Attachment):
    type: Literal[AttachmentType.AUDIO] = AttachmentType.AUDIO
    payload: MediaPayload
    transcription: str | None = None


class FileAttachment(Attachment):
    type: Literal[AttachmentType.FILE] = AttachmentType.FILE
    payload: FilePayload
    filename: str | None = None
    size: int | None = None


class StickerAttachment(Attachment):
    type: Literal[AttachmentType.STICKER] = AttachmentType.STICKER
    payload: StickerPayload
    width: int | None = None
    height: int | None = None


class ContactAttachment(Attachment):
    type: Literal[AttachmentType.CONTACT] = AttachmentType.CONTACT
    payload: ContactPayload


class LocationAttachment(Attachment):
    type: Literal[AttachmentType.LOCATION] = AttachmentType.LOCATION
    latitude: float
    longitude: float


class ShareAttachment(Attachment):
    type: Literal[AttachmentType.SHARE] = AttachmentType.SHARE
    payload: SharePayload | None = None
    title: str | None = None
    description: str | None = None
    image_url: str | None = None


class InlineKeyboardAttachment(Attachment):
    type: Literal[AttachmentType.INLINE_KEYBOARD] = AttachmentType.INLINE_KEYBOARD
    payload: InlineKeyboardMarkup


AnyAttachment = (
    PhotoAttachment
    | VideoAttachment
    | AudioAttachment
    | FileAttachment
    | StickerAttachment
    | ContactAttachment
    | LocationAttachment
    | ShareAttachment
    | InlineKeyboardAttachment
    | Attachment
)


class UploadEndpoint(MaxObject):
    """Answer of ``POST /uploads``."""

    url: str
    token: str | None = None


class UploadedInfo(MaxObject):
    """Answer of the actual file upload; shape depends on the media type."""

    token: str | None = None
    photos: dict[str, PhotoPayload] | None = None

    @property
    def any_token(self) -> str | None:
        if self.token:
            return self.token
        if self.photos:
            first = next(iter(self.photos.values()), None)
            if first is not None:
                return first.token
        return None


# ---------------------------------------------------------------------------
# Outgoing attachment builders
# ---------------------------------------------------------------------------


def image(*, token: str | None = None, url: str | None = None) -> dict[str, Any]:
    return {"type": "image", "payload": _payload(token=token, url=url)}


def video(*, token: str | None = None, url: str | None = None) -> dict[str, Any]:
    return {"type": "video", "payload": _payload(token=token, url=url)}


def audio(*, token: str | None = None, url: str | None = None) -> dict[str, Any]:
    return {"type": "audio", "payload": _payload(token=token, url=url)}


def file(*, token: str | None = None, url: str | None = None) -> dict[str, Any]:
    return {"type": "file", "payload": _payload(token=token, url=url)}


def sticker(code: str) -> dict[str, Any]:
    return {"type": "sticker", "payload": {"code": code}}


def location(latitude: float, longitude: float) -> dict[str, Any]:
    return {"type": "location", "latitude": latitude, "longitude": longitude}


def contact(
    *,
    name: str | None = None,
    contact_id: int | None = None,
    vcf_info: str | None = None,
    vcf_phone: str | None = None,
) -> dict[str, Any]:
    payload = {
        "name": name,
        "contactId": contact_id,
        "vcfInfo": vcf_info,
        "vcfPhone": vcf_phone,
    }
    return {"type": "contact", "payload": {k: v for k, v in payload.items() if v is not None}}


def album(tokens: list[str]) -> list[dict[str, Any]]:
    """MAX renders several ``image`` attachments in one message as an album."""
    return [image(token=t) for t in tokens]


def _payload(*, token: str | None, url: str | None) -> dict[str, Any]:
    if not token and not url:
        raise ValueError("either token or url must be provided")
    return {"token": token} if token else {"url": url}
