#!/usr/bin/env python3
"""HTTP utilities with proxy support (Issue #1207).

Respects HTTPS_PROXY / HTTP_PROXY environment variables for corporate firewall compatibility.

Usage:
    from scripts.http_utils import urlopen_with_proxy, get_proxy_handler

    # Simple usage
    with urlopen_with_proxy(url, timeout=30) as resp:
        data = resp.read()

    # Custom opener
    opener = get_proxy_opener()
    with opener.open(req) as resp:
        data = resp.read()
"""
from __future__ import annotations

import os
import urllib.request
from typing import Optional


def get_proxy_url() -> Optional[str]:
    """Get proxy URL from environment variables.

    Checks HTTPS_PROXY, HTTP_PROXY, https_proxy, http_proxy (in order).
    Returns None if no proxy configured.
    """
    for var in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
        proxy = os.environ.get(var)
        if proxy:
            return proxy
    return None


def get_proxy_handler() -> Optional[urllib.request.ProxyHandler]:
    """Create proxy handler from environment variables.

    Returns ProxyHandler if proxy is configured, None otherwise.
    """
    proxy = get_proxy_url()
    if proxy:
        return urllib.request.ProxyHandler({"https": proxy, "http": proxy})
    return None


def get_proxy_opener() -> urllib.request.OpenerDirector:
    """Create URL opener with proxy support.

    Returns opener with proxy handler if configured, default opener otherwise.
    """
    handler = get_proxy_handler()
    if handler:
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener()


def urlopen_with_proxy(
    url: str,
    data: bytes | None = None,
    timeout: float = 30,
    headers: dict[str, str] | None = None,
    method: str | None = None,
) -> urllib.request.AbstractHTTPHandler:
    """Open URL with automatic proxy support.

    Drop-in replacement for urllib.request.urlopen that respects proxy env vars.

    Args:
        url: URL to open
        data: Request body (for POST/PUT)
        timeout: Request timeout in seconds
        headers: Optional request headers
        method: HTTP method (GET, POST, etc.)

    Returns:
        Response object (context manager)
    """
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)

    opener = get_proxy_opener()
    return opener.open(req, timeout=timeout)


def make_request(
    url: str,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    timeout: float = 30,
) -> tuple[int, bytes]:
    """Make HTTP request with proxy support.

    Returns (status_code, response_body) tuple.
    """
    try:
        with urlopen_with_proxy(url, data=data, timeout=timeout, headers=headers, method=method) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception:
        return 0, b""


if __name__ == "__main__":
    proxy = get_proxy_url()
    print(f"Proxy configured: {proxy or 'None (direct connection)'}")
    print(f"Proxy handler: {get_proxy_handler()}")
