from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

NextMiddleware = Callable[[Any, dict[str, Any]], Awaitable[Any]]


class BaseMiddleware(ABC):
    """Wraps handler execution.

    Register on ``router.message.middleware`` (inner: runs only when a handler
    matched) or ``router.message.outer_middleware`` (outer: runs for every event,
    matched or not, and can populate ``data`` before filters see it).
    """

    @abstractmethod
    async def __call__(
        self,
        handler: NextMiddleware,
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        raise NotImplementedError
