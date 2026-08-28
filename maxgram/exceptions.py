"""Exception hierarchy for maxgram."""

from __future__ import annotations

from typing import Any


class MaxgramError(Exception):
    """Base class for every error raised by maxgram."""


class DetailedMaxgramError(MaxgramError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class ClientDecodeError(DetailedMaxgramError):
    """Raised when the API returned a body that is not valid JSON."""

    def __init__(self, message: str, original: Exception, data: Any) -> None:
        super().__init__(message)
        self.original = original
        self.data = data

    def __str__(self) -> str:
        return f"{self.message}\nOriginal: {type(self.original).__name__}: {self.original}"


class MaxNetworkError(DetailedMaxgramError):
    """Transport level failure: connection reset, DNS, TLS, timeout."""


class MaxAPIError(DetailedMaxgramError):
    """Any non-2xx answer from the MAX Bot API."""

    label: str = "Server says"

    def __init__(self, method: str, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.method = method
        self.code = code

    def __str__(self) -> str:
        original = f" [{self.code}]" if self.code else ""
        return f"MAX server says{original} - {self.message} (method={self.method})"


class MaxBadRequest(MaxAPIError):
    """HTTP 400."""


class MaxUnauthorizedError(MaxAPIError):
    """HTTP 401 - the access token is missing, malformed or revoked."""


class MaxForbiddenError(MaxAPIError):
    """HTTP 403 - the bot lacks rights for this action."""


class MaxNotFound(MaxAPIError):
    """HTTP 404."""


class MaxMethodNotAllowed(MaxAPIError):
    """HTTP 405."""


class MaxRetryAfter(MaxAPIError):
    """HTTP 429 - flood control. ``retry_after`` holds the suggested delay in seconds."""

    def __init__(
        self, method: str, message: str, retry_after: float, code: str | None = None
    ) -> None:
        super().__init__(method=method, message=message, code=code)
        self.retry_after = retry_after

    def __str__(self) -> str:
        return f"{super().__str__()} (retry after {self.retry_after}s)"


class MaxServerError(MaxAPIError):
    """HTTP 5xx."""


class MaxEntityTooLarge(MaxAPIError):
    """HTTP 413 - uploaded file exceeds the per-type limit."""


class AttachmentNotReady(MaxAPIError):
    """The media is still being processed on MAX side; retry shortly."""


class UnsupportedKeywordArgument(DetailedMaxgramError):
    """A handler asked for a keyword argument the dispatcher cannot provide."""


class SkipHandler(MaxgramError):
    """Raise inside a handler to fall through to the next matching one."""


class CancelHandler(MaxgramError):
    """Raise inside a middleware to abort update processing silently."""


class SceneError(MaxgramError):
    """FSM misuse, e.g. storage is not configured."""
