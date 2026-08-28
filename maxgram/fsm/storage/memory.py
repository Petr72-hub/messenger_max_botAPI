from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any

from maxgram.fsm.storage.base import BaseStorage, StorageKey


class MemoryStorage(BaseStorage):
    """In-process storage. Fast, zero setup, and lost on restart."""

    def __init__(self) -> None:
        self._state: dict[str, str | None] = defaultdict(lambda: None)
        self._data: dict[str, dict[str, Any]] = defaultdict(dict)

    async def set_state(self, key: StorageKey, state: str | None = None) -> None:
        self._state[key.as_str()] = state

    async def get_state(self, key: StorageKey) -> str | None:
        return self._state.get(key.as_str())

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        self._data[key.as_str()] = copy.deepcopy(data)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return copy.deepcopy(self._data.get(key.as_str(), {}))

    async def close(self) -> None:
        self._state.clear()
        self._data.clear()
