"""Retrying HTTP helpers for MisakaNet CLI network operations."""
from __future__ import annotations

import json
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.5
RETRY_HTTP_STATUSES = {404, 408, 429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """User-facing network failure without a traceback dump."""

    def __init__(
        self,
        message: str,
        *,
        url: str = "",
        attempts: int = 1,
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.attempts = attempts
        self.status = status


class _ResponseStatusError(RuntimeError):
    def __init__(self, status_code: int, text: str, url: str) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.text = text
        self.url = url


def _request_url(request: Request | str) -> str:
    return getattr(request, "full_url", str(request))


def _status_from_error(error: BaseException) -> int | None:
    if isinstance(error, HTTPError):
        return error.code
    return getattr(error, "status_code", None)


def _detail_from_error(error: BaseException) -> str:
    if isinstance(error, HTTPError):
        reason = error.reason or error.msg
        try:
            body = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        if body:
            return f"{reason}: {body[:200]}"
        return str(reason)
    if isinstance(error, _ResponseStatusError):
        body = (error.text or "").strip()
        if body:
            return body[:200]
        return str(error)
    if isinstance(error, URLError):
        return str(error.reason)
    return str(error)


def _is_retryable(error: BaseException, retry_statuses: set[int]) -> bool:
    status = _status_from_error(error)
    if status is not None:
        return status in retry_statuses
    return isinstance(error, (TimeoutError, socket.timeout, URLError, OSError))


def _format_fetch_error(error: BaseException, url: str, attempts: int) -> str:
    status = _status_from_error(error)
    detail = _detail_from_error(error)
    target = f" from {url}" if url else ""
    if status is not None:
        return f"Network request failed after {attempts} attempts: HTTP {status}{target}. {detail}"
    return f"Network request failed after {attempts} attempts{target}: {detail}"


def _sleep_before_retry(attempt: int, backoff_seconds: float, sleep=time.sleep) -> None:
    if backoff_seconds <= 0:
        return
    sleep(backoff_seconds * (2 ** (attempt - 1)))


def fetch_bytes(
    request: Request | str,
    *,
    timeout: int = 30,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    opener=urlopen,
    sleep=time.sleep,
    retry_statuses: set[int] | None = None,
) -> bytes:
    """Fetch bytes with bounded retries and clean FetchError failures."""

    retry_statuses = retry_statuses or RETRY_HTTP_STATUSES
    max_attempts = max(1, retries)
    url = _request_url(request)
    last_error: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                return response.read()
        except Exception as error:
            last_error = error
            if attempt < max_attempts and _is_retryable(error, retry_statuses):
                _sleep_before_retry(attempt, backoff_seconds, sleep)
                continue
            raise FetchError(
                _format_fetch_error(error, url, attempt),
                url=url,
                attempts=attempt,
                status=_status_from_error(error),
            ) from error

    raise FetchError(
        f"Network request failed after {max_attempts} attempts from {url}.",
        url=url,
        attempts=max_attempts,
        status=_status_from_error(last_error) if last_error else None,
    )


def fetch_json(request: Request | str, **kwargs: Any) -> dict[str, Any] | list[Any]:
    raw = fetch_bytes(request, **kwargs)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: int = 15,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    request_func=None,
    sleep=time.sleep,
    retry_statuses: set[int] | None = None,
) -> dict[str, Any] | list[Any]:
    """requests-compatible JSON fetch with the same retry behavior."""

    if request_func is None:
        try:
            import requests
        except ImportError as error:
            raise FetchError("Network request failed: the requests package is not installed.") from error
        request_func = requests.request

    retry_statuses = retry_statuses or RETRY_HTTP_STATUSES
    max_attempts = max(1, retries)

    for attempt in range(1, max_attempts + 1):
        try:
            response = request_func(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=timeout,
            )
            status_code = getattr(response, "status_code", 0)
            if status_code >= 400:
                raise _ResponseStatusError(status_code, getattr(response, "text", ""), url)
            if status_code == 204:
                return {"status": "ok"}
            return response.json()
        except Exception as error:
            if attempt < max_attempts and _is_retryable(error, retry_statuses):
                _sleep_before_retry(attempt, backoff_seconds, sleep)
                continue
            raise FetchError(
                _format_fetch_error(error, url, attempt),
                url=url,
                attempts=attempt,
                status=_status_from_error(error),
            ) from error

    raise FetchError(f"Network request failed after {max_attempts} attempts from {url}.", url=url)

