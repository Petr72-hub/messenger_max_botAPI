from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StorageKey:
    """Identifies one conversation slot in the FSM storage."""

    bot_id: int
    chat_id: int | None
    user_id: int | None
    destiny: str = "default"

    def as_str(self) -> str:
        return f"{self.bot_id}:{self.chat_id}:{self.user_id}:{self.destiny}"


class BaseStorage(ABC):
    """Persistence contract for FSM state and per-conversation data."""

    @abstractmethod
    async def set_state(self, key: StorageKey, state: str | None = None) -> None: ...

    @abstractmethod
    async def get_state(self, key: StorageKey) -> str | None: ...

    @abstractmethod
    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get_data(self, key: StorageKey) -> dict[str, Any]: ...

    async def update_data(self, key: StorageKey, data: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_data(key)
        current.update(data)
        await self.set_data(key, current)
        return current

    async def clear(self, key: StorageKey) -> None:
        await self.set_state(key, None)
        await self.set_data(key, {})

    async def close(self) -> None:
        return None
