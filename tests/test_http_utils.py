"""Tests for http_utils module (Issue #1207)."""
from __future__ import annotations

import os
import urllib.request
from unittest.mock import patch

from scripts.http_utils import get_proxy_url, get_proxy_handler, get_proxy_opener


def test_get_proxy_url_from_https_proxy(monkeypatch):
    """HTTPS_PROXY takes precedence."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.com:8080")
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    assert get_proxy_url() == "http://proxy.corp.com:8080"


def test_get_proxy_url_from_http_proxy(monkeypatch):
    """Falls back to HTTP_PROXY if HTTPS_PROXY not set."""
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.corp.com:3128")

    assert get_proxy_url() == "http://proxy.corp.com:3128"


def test_get_proxy_url_no_proxy(monkeypatch):
    """Returns None when no proxy configured."""
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)

    assert get_proxy_url() is None


def test_get_proxy_handler_with_proxy(monkeypatch):
    """Returns ProxyHandler when proxy configured."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.com:8080")

    handler = get_proxy_handler()
    assert handler is not None
    assert isinstance(handler, urllib.request.ProxyHandler)


def test_get_proxy_handler_no_proxy(monkeypatch):
    """Returns None when no proxy configured."""
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    handler = get_proxy_handler()
    assert handler is None


def test_get_proxy_opener_with_proxy(monkeypatch):
    """Returns opener with proxy handler."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.com:8080")

    opener = get_proxy_opener()
    assert opener is not None
    # Verify proxy handler is in opener's handlers
    handler_types = [type(h).__name__ for h in opener.handlers]
    assert "ProxyHandler" in handler_types


def test_get_proxy_opener_no_proxy(monkeypatch):
    """Returns default opener when no proxy."""
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    opener = get_proxy_opener()
    assert opener is not None
    # Should not have proxy handler
    handler_types = [type(h).__name__ for h in opener.handlers]
    assert "ProxyHandler" not in handler_types


def test_case_insensitive_env_vars(monkeypatch):
    """Lowercase env vars also work."""
    monkeypatch.setenv("https_proxy", "http://proxy.corp.com:8080")

    assert get_proxy_url() == "http://proxy.corp.com:8080"


if __name__ == "__main__":
    import tempfile
    monkeypatch = type("Monkeypatch", (), {"setenv": staticmethod(lambda k, v: os.environ.update({k: v})), "delenv": staticmethod(lambda k, **kw: os.environ.pop(k, None))})()

    test_get_proxy_url_from_https_proxy(monkeypatch)
    test_get_proxy_url_from_http_proxy(monkeypatch)
    test_get_proxy_url_no_proxy(monkeypatch)
    test_get_proxy_handler_with_proxy(monkeypatch)
    test_get_proxy_handler_no_proxy(monkeypatch)
    test_get_proxy_opener_with_proxy(monkeypatch)
    test_get_proxy_opener_no_proxy(monkeypatch)
    test_case_insensitive_env_vars(monkeypatch)
    print("All tests passed ✓")
