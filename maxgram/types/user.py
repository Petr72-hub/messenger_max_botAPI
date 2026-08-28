from __future__ import annotations

from maxgram.types.base import MaxObject


class User(MaxObject):
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    is_bot: bool = False
    last_activity_time: int | None = None

    @property
    def full_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) or (self.username or str(self.user_id))

    @property
    def mention(self) -> str:
        """Markdown mention understood by MAX (``@username`` when available)."""
        if self.username:
            return f"@{self.username}"
        return self.full_name

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"User(id={self.user_id}, {self.full_name!r})"


class UserWithPhoto(User):
    description: str | None = None
    avatar_url: str | None = None
    full_avatar_url: str | None = None


class BotCommand(MaxObject):
    name: str
    description: str | None = None


class BotInfo(UserWithPhoto):
    commands: list[BotCommand] | None = None


class ChatMember(UserWithPhoto):
    last_access_time: int | None = None
    is_owner: bool = False
    is_admin: bool = False
    join_time: int | None = None
    permissions: list[str] | None = None


class ChatMembersList(MaxObject):
    members: list[ChatMember] = []
    marker: int | None = None
