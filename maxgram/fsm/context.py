from __future__ import annotations

from typing import Any

from maxgram.fsm.state import State
from maxgram.fsm.storage.base import BaseStorage, StorageKey


class FSMContext:
    """Per-conversation handle over the storage, injected as ``state``."""

    def __init__(self, storage: BaseStorage, key: StorageKey) -> None:
        self.storage = storage
        self.key = key

    async def set_state(self, state: State | str | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self.storage.set_state(self.key, value)

    async def get_state(self) -> str | None:
        return await self.storage.get_state(self.key)

    async def set_data(self, data: dict[str, Any]) -> None:
        await self.storage.set_data(self.key, data)

    async def get_data(self) -> dict[str, Any]:
        return await self.storage.get_data(self.key)

    async def update_data(self, data: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(data or {})
        payload.update(kwargs)
        return await self.storage.update_data(self.key, payload)

    async def get_value(self, name: str, default: Any = None) -> Any:
        return (await self.get_data()).get(name, default)

    async def clear(self) -> None:
        await self.storage.clear(self.key)
