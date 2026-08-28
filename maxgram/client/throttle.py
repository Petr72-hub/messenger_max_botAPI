"""Client-side pacing so the bot stays under MAX's per-conversation limits."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    """Token-free leaky bucket keyed by conversation.

    MAX accepts at most two messages per second in a single chat. Waiting locally
    is cheaper than collecting HTTP 429s and re-sending, so the Bot routes every
    send through here.
    """

    def __init__(self, rate: float = 2.0, per: float = 1.0) -> None:
        self.min_interval = per / rate if rate > 0 else 0.0
        self._last_call: dict[str, float] = defaultdict(float)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def acquire(self, key: str | int | None) -> None:
        if self.min_interval <= 0:
            return
        bucket = str(key or "global")
        async with self._locks[bucket]:
            now = time.monotonic()
            wait = self._last_call[bucket] + self.min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._last_call[bucket] = now
