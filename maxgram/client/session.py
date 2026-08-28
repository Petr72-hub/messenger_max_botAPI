"""HTTP transport for the MAX Bot API."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from dataclasses import dataclass
from typing import Any, Mapping

import aiohttp
import certifi

from maxgram.exceptions import (
    AttachmentNotReady,
    ClientDecodeError,
    MaxAPIError,
    MaxBadRequest,
    MaxEntityTooLarge,
    MaxForbiddenError,
    MaxMethodNotAllowed,
    MaxNetworkError,
    MaxNotFound,
    MaxRetryAfter,
    MaxServerError,
    MaxUnauthorizedError,
)

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://platform-api2.max.ru"

_STATUS_MAP: dict[int, type[MaxAPIError]] = {
    400: MaxBadRequest,
    401: MaxUnauthorizedError,
    403: MaxForbiddenError,
    404: MaxNotFound,
    405: MaxMethodNotAllowed,
    413: MaxEntityTooLarge,
}


@dataclass(slots=True)
class RetryPolicy:
    """How the session reacts to throttling and transient server failures."""

    max_attempts: int = 4
    backoff_base: float = 0.5
    backoff_factor: float = 2.0
    backoff_max: float = 30.0
    retry_on_network_error: bool = True

    def delay_for(self, attempt: int) -> float:
        return min(self.backoff_base * (self.backoff_factor**attempt), self.backoff_max)


class BaseSession:
    """Interface a transport must implement, useful for tests and mocks."""

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:  # pragma: no cover - interface
        raise NotImplementedError

    async def close(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class AiohttpSession(BaseSession):
    """Default transport backed by :mod:`aiohttp`.

    The session owns one connection pool, injects the ``Authorization`` header on
    every call, retries throttled and 5xx responses with exponential backoff, and
    normalises API errors into the :mod:`maxgram.exceptions` hierarchy.
    """

    def __init__(
        self,
        token: str,
        *,
        api_base: str = DEFAULT_API_BASE,
        timeout: float = 60.0,
        retry: RetryPolicy | None = None,
        connector_limit: int = 100,
        proxy: str | None = None,
    ) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.retry = retry or RetryPolicy()
        self.proxy = proxy
        self._connector_limit = connector_limit
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    # -- lifecycle -------------------------------------------------------------

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    ssl_context = ssl.create_default_context(cafile=certifi.where())
                    connector = aiohttp.TCPConnector(
                        limit=self._connector_limit, ssl=ssl_context
                    )
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=self.timeout,
                        headers={
                            "Authorization": self.token,
                            "Accept": "application/json",
                            "User-Agent": "maxgram/0.1.0",
                        },
                    )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            # Give aiohttp's SSL transports a beat to unwind cleanly.
            await asyncio.sleep(0)
        self._session = None

    async def __aenter__(self) -> "AiohttpSession":
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    # -- requests --------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        session = await self._ensure_session()
        url = f"{self.api_base}/{path.lstrip('/')}"
        clean_params = _clean_params(params)

        last_error: Exception | None = None
        for attempt in range(self.retry.max_attempts):
            try:
                async with session.request(
                    method,
                    url,
                    params=clean_params,
                    json=json_body,
                    proxy=self.proxy,
                ) as response:
                    raw = await response.read()
                    if response.status < 400:
                        return _decode(raw, method=f"{method} {path}")
                    error = _build_error(
                        status=response.status,
                        raw=raw,
                        method=f"{method} {path}",
                        headers=response.headers,
                    )
            except aiohttp.ClientError as exc:
                if not self.retry.retry_on_network_error:
                    raise MaxNetworkError(f"{method} {path} failed: {exc}") from exc
                error = MaxNetworkError(f"{method} {path} failed: {exc}")
            except asyncio.TimeoutError as exc:
                error = MaxNetworkError(f"{method} {path} timed out after {self.timeout.total}s")
                last_error = error
                if attempt == self.retry.max_attempts - 1:
                    raise error from exc

            last_error = error
            if not _is_retryable(error) or attempt == self.retry.max_attempts - 1:
                raise error

            delay = (
                error.retry_after
                if isinstance(error, MaxRetryAfter)
                else self.retry.delay_for(attempt)
            )
            logger.warning(
                "MAX API %s %s failed (%s), retrying in %.1fs (attempt %d/%d)",
                method,
                path,
                type(error).__name__,
                delay,
                attempt + 1,
                self.retry.max_attempts,
            )
            await asyncio.sleep(delay)

        raise last_error or MaxNetworkError(f"{method} {path} failed without a response")

    async def upload_file(
        self,
        upload_url: str,
        *,
        data: bytes,
        filename: str,
        field_name: str = "data",
        content_type: str | None = None,
    ) -> Any:
        """POST the binary payload to the short-lived URL returned by ``/uploads``."""
        session = await self._ensure_session()
        form = aiohttp.FormData()
        form.add_field(
            field_name,
            data,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )
        try:
            async with session.post(upload_url, data=form, proxy=self.proxy) as response:
                raw = await response.read()
                if response.status >= 400:
                    raise _build_error(
                        status=response.status,
                        raw=raw,
                        method="POST <upload-url>",
                        headers=response.headers,
                    )
                if not raw:
                    # Video and audio uploads answer with an empty body; the token
                    # handed out by POST /uploads is the one to use.
                    return {}
                return _decode(raw, method="POST <upload-url>")
        except aiohttp.ClientError as exc:
            raise MaxNetworkError(f"upload failed: {exc}") from exc


def _clean_params(params: Mapping[str, Any] | None) -> dict[str, str] | None:
    if not params:
        return None
    cleaned: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            cleaned[key] = ",".join(str(v) for v in value)
        else:
            cleaned[key] = str(value)
    return cleaned or None


def _decode(raw: bytes, *, method: str) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClientDecodeError(f"Failed to decode response of {method}", exc, raw) from exc


def _build_error(
    *, status: int, raw: bytes, method: str, headers: Mapping[str, str]
) -> MaxAPIError:
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:  # noqa: BLE001 - error bodies are not always JSON
        body = {}

    message = body.get("message") or raw.decode("utf-8", "replace")[:500] or "unknown error"
    code = body.get("code")

    if status == 429:
        retry_after = float(headers.get("Retry-After") or body.get("retry_after") or 1.0)
        return MaxRetryAfter(method=method, message=message, retry_after=retry_after, code=code)
    if code == "attachment.not.ready":
        return AttachmentNotReady(method=method, message=message, code=code)
    if status >= 500:
        return MaxServerError(method=method, message=message, code=code)

    error_cls = _STATUS_MAP.get(status, MaxAPIError)
    return error_cls(method=method, message=message, code=code)


def _is_retryable(error: Exception) -> bool:
    return isinstance(error, (MaxRetryAfter, MaxServerError, MaxNetworkError, AttachmentNotReady))
