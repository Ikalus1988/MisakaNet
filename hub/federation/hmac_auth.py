"""
HMAC-SHA256 authentication for federated endpoints.

Replaces raw token passing with signed requests. Each request includes:
  - X-HMAC-Signature: hex HMAC-SHA256 of canonical payload
  - X-HMAC-Timestamp: Unix epoch seconds (string)
  - X-HMAC-Key-Version: integer key version for rotation support

Canonical payload = "{timestamp}\n{method}\n{path}\n{body_hash}"

Replay protection: requests with timestamp older than MAX_AGE_SECONDS
or with a previously-seen nonce are rejected.

Dependencies: Python stdlib only (hmac, hashlib, time, threading).
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from typing import Optional, Tuple

from . import secrets as secret_store

# Replay window: 5 minutes
MAX_AGE_SECONDS = 300

# Nonce cache cleanup interval
_NONCE_CLEANUP_INTERVAL = 60

# Header names
HEADER_SIGNATURE = "X-HMAC-Signature"
HEADER_TIMESTAMP = "X-HMAC-Timestamp"
HEADER_KEY_VERSION = "X-HMAC-Key-Version"


class _NonceCache:
    """
    Thread-safe in-memory nonce cache for replay protection.

    Stores (nonce, expiry) pairs. Nonces are derived from timestamp + body hash
    so the same request body at the same second produces the same nonce.
    """

    def __init__(self, max_age: int = MAX_AGE_SECONDS):
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self._max_age = max_age
        self._last_cleanup = time.time()

    def check_and_record(self, nonce: str) -> bool:
        """
        Return True if nonce is fresh (not seen within max_age window).
        Records the nonce on success.
        """
        now = time.time()
        with self._lock:
            self._maybe_cleanup(now)
            if nonce in self._seen:
                return False
            self._seen[nonce] = now + self._max_age
            return True

    def _maybe_cleanup(self, now: float) -> None:
        """Evict expired nonces periodically."""
        if now - self._last_cleanup < _NONCE_CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        expired = [k for k, exp in self._seen.items() if exp < now]
        for k in expired:
            del self._seen[k]


# Module-level nonce cache (shared across all verifications)
_nonce_cache = _NonceCache()


def _canonical_payload(
    timestamp: str,
    method: str,
    path: str,
    body: bytes,
) -> str:
    """
    Build the canonical string that gets signed.

    Format: "{timestamp}\n{METHOD}\n{path}\n{body_sha256_hex}"
    """
    body_hash = hashlib.sha256(body).hexdigest()
    return f"{timestamp}\n{method.upper()}\n{path}\n{body_hash}"


def sign_request(
    node_id: str,
    method: str,
    path: str,
    body: bytes = b"",
    *,
    timestamp: Optional[float] = None,
) -> Tuple[str, str, str, int]:
    """
    Sign an outgoing request.

    Returns (signature_hex, timestamp_str, body, key_version) for setting headers.
    """
    ts = str(int(timestamp or time.time()))
    key_version = secret_store.get_key_version(node_id)
    shared_secret = secret_store.get_shared_secret(node_id)

    if shared_secret is None:
        raise ValueError(f"No shared secret for node '{node_id}'. Register the node first.")

    payload = _canonical_payload(ts, method, path, body)
    sig = hmac.new(
        shared_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return sig, ts, body, key_version


def verify_request(
    node_id: str,
    method: str,
    path: str,
    body: bytes,
    signature: str,
    timestamp: str,
    key_version: int = 0,
) -> Tuple[bool, str]:
    """
    Verify an incoming request's HMAC signature.

    Returns (ok, reason). On failure, reason describes what went wrong.
    """
    # 1. Timestamp freshness
    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        return False, "invalid_timestamp"

    now = int(time.time())
    age = abs(now - ts_int)
    if age > MAX_AGE_SECONDS:
        return False, f"timestamp_expired (age={age}s, max={MAX_AGE_SECONDS}s)"

    # 2. Retrieve shared secret
    shared_secret = secret_store.get_shared_secret(node_id)
    if shared_secret is None:
        return False, f"unknown_node '{node_id}'"

    # 3. Compute expected signature
    payload = _canonical_payload(timestamp, method, path, body)
    expected = hmac.new(
        shared_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # 4. Constant-time comparison
    if not hmac.compare_digest(signature, expected):
        return False, "signature_mismatch"

    # 5. Replay protection — nonce = timestamp + body hash
    body_hash = hashlib.sha256(body).hexdigest()
    nonce = f"{timestamp}:{body_hash}"
    if not _nonce_cache.check_and_record(nonce):
        return False, "replay_detected"

    return True, "ok"


def build_auth_headers(
    node_id: str,
    method: str,
    path: str,
    body: bytes = b"",
) -> dict:
    """
    Convenience: build the three auth headers for an outgoing request.
    """
    sig, ts, _, kv = sign_request(node_id, method, path, body)
    return {
        HEADER_SIGNATURE: sig,
        HEADER_TIMESTAMP: ts,
        HEADER_KEY_VERSION: str(kv),
    }


def extract_auth_headers(headers: dict) -> Tuple[str, str, int]:
    """
    Convenience: extract auth headers from a request.

    Returns (signature, timestamp, key_version).
    Raises ValueError if headers are missing.
    """
    sig = headers.get(HEADER_SIGNATURE)
    ts = headers.get(HEADER_TIMESTAMP)
    kv = headers.get(HEADER_KEY_VERSION, "0")

    if not sig or not ts:
        raise ValueError("Missing HMAC auth headers")

    return sig, ts, int(kv)
