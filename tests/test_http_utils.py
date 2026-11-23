"""Tests for http_utils module (Issue #1207)."""
from __future__ import annotations

import os
import urllib.request
from unittest.mock import patch

from scripts.http_utils import get_proxy_url, get_proxy_handler, get_proxy_opener

#: Every spelling `get_proxy_url()` honours. The module reads the environment case-insensitively
#: (there is a test for exactly that below), and a machine that configures only the lowercase pair —
#: which is what curl and git take — is the common case. Measured 2026-11-23 on such a machine: three
#: of the "no proxy" tests failed, because they cleared only `HTTPS_PROXY`/`HTTP_PROXY` and then
#: asserted the absence of a proxy that the lowercase pair was still supplying.
_PROXY_VARS = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy", "NO_PROXY", "no_proxy")


def _clear_proxy_env(monkeypatch):
    """Start every case from "no proxy configured", whatever the machine has.

    Environment variables are only half of it: `build_opener()` builds a `ProxyHandler`, and that
    handler asks `urllib.request.getproxies()`, which on Windows reads the WinINET registry rather
    than the environment. So a machine with the system proxy switched on keeps a proxy handler even
    after every `*_PROXY` variable is gone — measured 2026-11-23: two "no proxy" tests failed on such
    a machine and passed in CI, where nothing is configured at either layer.
    """
    for name in _PROXY_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})


def test_get_proxy_url_from_https_proxy(monkeypatch):
    """HTTPS_PROXY takes precedence."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.com:8080")
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    assert get_proxy_url() == "http://proxy.corp.com:8080"


def test_get_proxy_url_from_http_proxy(monkeypatch):
    """Falls back to HTTP_PROXY if HTTPS_PROXY not set."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.corp.com:3128")

    assert get_proxy_url() == "http://proxy.corp.com:3128"


def test_get_proxy_url_no_proxy(monkeypatch):
    """Returns None when no proxy configured."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)

    assert get_proxy_url() is None


def test_get_proxy_handler_with_proxy(monkeypatch):
    """Returns ProxyHandler when proxy configured."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.com:8080")

    handler = get_proxy_handler()
    assert handler is not None
    assert isinstance(handler, urllib.request.ProxyHandler)


def test_get_proxy_handler_no_proxy(monkeypatch):
    """Returns None when no proxy configured."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    handler = get_proxy_handler()
    assert handler is None


def test_get_proxy_opener_with_proxy(monkeypatch):
    """Returns opener with proxy handler."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.com:8080")

    opener = get_proxy_opener()
    assert opener is not None
    # Verify proxy handler is in opener's handlers
    handler_types = [type(h).__name__ for h in opener.handlers]
    assert "ProxyHandler" in handler_types


def test_get_proxy_opener_no_proxy(monkeypatch):
    """Returns default opener when no proxy."""
    _clear_proxy_env(monkeypatch)
    monkeypatch.delenv("HTTP_PROXY", raising=False)

    opener = get_proxy_opener()
    assert opener is not None
    # Should not have proxy handler
    handler_types = [type(h).__name__ for h in opener.handlers]
    assert "ProxyHandler" not in handler_types


def test_case_insensitive_env_vars(monkeypatch):
    """Lowercase env vars also work."""
    _clear_proxy_env(monkeypatch)
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
