from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from maxgram.fsm.storage.base import BaseStorage, StorageKey


class JSONFileStorage(BaseStorage):
    """Storage that survives restarts by keeping one JSON file on disk.

    Adequate for single-process bots; use Redis when you run several workers.
    Writes are debounced so a chatty conversation does not hit the disk per event.
    """

    def __init__(self, path: str | Path, *, flush_delay: float = 1.0) -> None:
        self.path = Path(path)
        self.flush_delay = flush_delay
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._store = json.loads(self.path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._store = {}

    def _slot(self, key: StorageKey) -> dict[str, Any]:
        return self._store.setdefault(key.as_str(), {"state": None, "data": {}})

    def _schedule_flush(self) -> None:
        if self._flush_task and not self._flush_task.done():
            return
        self._flush_task = asyncio.create_task(self._flush_later())

    async def _flush_later(self) -> None:
        await asyncio.sleep(self.flush_delay)
        await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            payload = json.dumps(self._store, ensure_ascii=False, indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(payload, "utf-8")
        tmp.replace(self.path)

    async def set_state(self, key: StorageKey, state: str | None = None) -> None:
        self._slot(key)["state"] = state
        self._schedule_flush()

    async def get_state(self, key: StorageKey) -> str | None:
        return self._slot(key).get("state")

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        self._slot(key)["data"] = data
        self._schedule_flush()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return dict(self._slot(key).get("data", {}))

    async def close(self) -> None:
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        await self.flush()
