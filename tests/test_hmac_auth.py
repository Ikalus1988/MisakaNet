"""Tests for HMAC-SHA256 federation authentication.

Covers:
  1. Sign and verify round-trip
  2. Replay protection (duplicate nonce rejection)
  3. Timestamp expiry (stale request rejection)
  4. Key rotation (version bump, old key invalid)
  5. Signature mismatch (tampered body)
  6. Integration with registry (auto-generate on add_peer)
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from hub.federation.hmac_auth import (
    sign_request,
    verify_request,
    build_auth_headers,
    extract_auth_headers,
    _NonceCache,
    MAX_AGE_SECONDS,
)
from hub.federation import secrets as secret_store
from hub.federation.registry import FederationRegistry


@pytest.fixture
def secrets_dir(tmp_path):
    """Isolate secrets to a temp directory."""
    with patch.object(secret_store, "_SECRETS_DIR", tmp_path / "secrets"):
        yield tmp_path / "secrets"


@pytest.fixture
def node_with_secret(secrets_dir):
    """Register a node and return its ID."""
    node_id = "test-node-alpha"
    secret_store.generate_shared_secret(node_id)
    return node_id


def _now():
    """Current time as float, for test convenience."""
    return time.time()


# ── 1. Sign & Verify Round-Trip ──────────────────────────────────────────────


class TestSignAndVerify:
    def test_sign_produces_valid_headers(self, node_with_secret):
        """sign_request returns (sig, timestamp, body, key_version)."""
        sig, ts, body, kv = sign_request(
            node_with_secret, "POST", "/api/sync", b'{"data": 1}'
        )
        assert len(sig) == 64  # SHA-256 hex = 64 chars
        assert ts.isdigit()
        assert kv >= 1

    def test_verify_accepts_valid_request(self, node_with_secret):
        """verify_request accepts a properly signed request."""
        body = b'{"lesson": "test"}'
        sig, ts, _, kv = sign_request(node_with_secret, "POST", "/federation/sync", body)

        ok, reason = verify_request(
            node_with_secret, "POST", "/federation/sync", body, sig, ts, kv
        )
        assert ok is True
        assert reason == "ok"

    def test_build_auth_headers_round_trip(self, node_with_secret):
        """build_auth_headers + extract_auth_headers round-trips correctly."""
        body = b"hello"
        headers = build_auth_headers(node_with_secret, "PUT", "/api/lesson", body)

        sig, ts, kv = extract_auth_headers(headers)
        ok, reason = verify_request(
            node_with_secret, "PUT", "/api/lesson", body, sig, ts, kv
        )
        assert ok is True

    def test_different_methods_produce_different_signatures(self, node_with_secret):
        """GET and POST to the same path produce different signatures."""
        body = b""
        ts_fixed = _now()
        sig_get, _, _, _ = sign_request(node_with_secret, "GET", "/api/x", body, timestamp=ts_fixed)
        sig_post, _, _, _ = sign_request(node_with_secret, "POST", "/api/x", body, timestamp=ts_fixed)
        assert sig_get != sig_post


# ── 2. Replay Protection ─────────────────────────────────────────────────────


class TestReplayProtection:
    def test_duplicate_request_rejected(self, node_with_secret):
        """Sending the same signed request twice is rejected as replay."""
        body = b'{"data": "replay-me"}'
        ts_fixed = _now()
        sig, ts, _, kv = sign_request(
            node_with_secret, "POST", "/api/sync", body, timestamp=ts_fixed
        )

        # First time: ok
        ok1, _ = verify_request(
            node_with_secret, "POST", "/api/sync", body, sig, ts, kv
        )
        assert ok1 is True

        # Second time: replay detected
        ok2, reason = verify_request(
            node_with_secret, "POST", "/api/sync", body, sig, ts, kv
        )
        assert ok2 is False
        assert "replay" in reason

    def test_different_body_not_replay(self, node_with_secret):
        """Same timestamp but different body is not a replay."""
        ts_fixed = _now()
        body_a = b'{"id": 1}'
        body_b = b'{"id": 2}'

        sig_a, ts_a, _, kv_a = sign_request(
            node_with_secret, "POST", "/api/x", body_a, timestamp=ts_fixed
        )
        sig_b, ts_b, _, kv_b = sign_request(
            node_with_secret, "POST", "/api/x", body_b, timestamp=ts_fixed
        )

        ok1, _ = verify_request(
            node_with_secret, "POST", "/api/x", body_a, sig_a, ts_a, kv_a
        )
        ok2, _ = verify_request(
            node_with_secret, "POST", "/api/x", body_b, sig_b, ts_b, kv_b
        )
        assert ok1 is True
        assert ok2 is True


# ── 3. Timestamp Expiry ──────────────────────────────────────────────────────


class TestTimestampExpiry:
    def test_expired_timestamp_rejected(self, node_with_secret):
        """Request with timestamp older than MAX_AGE_SECONDS is rejected."""
        old_ts = _now() - MAX_AGE_SECONDS - 10
        body = b"stale"
        sig, ts, _, kv = sign_request(
            node_with_secret, "GET", "/api/status", body, timestamp=old_ts
        )

        ok, reason = verify_request(
            node_with_secret, "GET", "/api/status", body, sig, ts, kv
        )
        assert ok is False
        assert "expired" in reason

    def test_future_timestamp_within_window_accepted(self, node_with_secret):
        """Request with timestamp slightly in the future is accepted (clock skew)."""
        future_ts = _now() + 30  # 30s in future, within 5min window
        body = b"future"
        sig, ts, _, kv = sign_request(
            node_with_secret, "GET", "/api/ping", body, timestamp=future_ts
        )

        ok, reason = verify_request(
            node_with_secret, "GET", "/api/ping", body, sig, ts, kv
        )
        assert ok is True

    def test_invalid_timestamp_format_rejected(self, node_with_secret):
        """Non-numeric timestamp is rejected."""
        ok, reason = verify_request(
            node_with_secret, "GET", "/api/x", b"", "bad-sig", "not-a-number", 1
        )
        assert ok is False
        assert "invalid_timestamp" in reason


# ── 4. Key Rotation ──────────────────────────────────────────────────────────


class TestKeyRotation:
    def test_key_version_bumps_on_rotation(self, secrets_dir, node_with_secret):
        """Rotating a key increments the version."""
        assert secret_store.get_key_version(node_with_secret) == 1

        secret_store.generate_shared_secret(node_with_secret, rotate=True)
        assert secret_store.get_key_version(node_with_secret) == 2

    def test_old_key_invalid_after_rotation(self, secrets_dir, node_with_secret):
        """After rotation, signatures made with the old key are rejected."""
        ts_fixed = _now()
        body = b"old-key-data"
        sig_v1, ts, _, kv_v1 = sign_request(
            node_with_secret, "POST", "/api/sync", body, timestamp=ts_fixed
        )
        assert kv_v1 == 1

        # Rotate key
        secret_store.generate_shared_secret(node_with_secret, rotate=True)
        assert secret_store.get_key_version(node_with_secret) == 2

        # Verify with v1 signature should fail (server now has v2 key)
        ok, reason = verify_request(
            node_with_secret, "POST", "/api/sync", body, sig_v1, ts, kv_v1
        )
        assert ok is False
        assert "signature_mismatch" in reason

    def test_new_key_signs_and_verifies(self, secrets_dir, node_with_secret):
        """After rotation, new key signs and verifies correctly."""
        secret_store.generate_shared_secret(node_with_secret, rotate=True)

        body = b"new-key-data"
        sig, ts, _, kv = sign_request(
            node_with_secret, "POST", "/api/sync", body, timestamp=_now()
        )
        assert kv == 2

        ok, reason = verify_request(
            node_with_secret, "POST", "/api/sync", body, sig, ts, kv
        )
        assert ok is True


# ── 5. Signature Mismatch ────────────────────────────────────────────────────


class TestSignatureMismatch:
    def test_tampered_body_rejected(self, node_with_secret):
        """Changing the body after signing invalidates the signature."""
        ts_fixed = _now()
        original_body = b'{"lesson": "original"}'
        tampered_body = b'{"lesson": "TAMPERED"}'

        sig, ts, _, kv = sign_request(
            node_with_secret, "POST", "/api/sync", original_body, timestamp=ts_fixed
        )

        ok, reason = verify_request(
            node_with_secret, "POST", "/api/sync", tampered_body, sig, ts, kv
        )
        assert ok is False
        assert "signature_mismatch" in reason

    def test_tampered_path_rejected(self, node_with_secret):
        """Changing the path after signing invalidates the signature."""
        ts_fixed = _now()
        body = b"data"
        sig, ts, _, kv = sign_request(
            node_with_secret, "POST", "/api/sync", body, timestamp=ts_fixed
        )

        ok, reason = verify_request(
            node_with_secret, "POST", "/api/DIFFERENT", body, sig, ts, kv
        )
        assert ok is False
        assert "signature_mismatch" in reason

    def test_unknown_node_rejected(self, secrets_dir):
        """Request from an unregistered node is rejected."""
        ok, reason = verify_request(
            "nonexistent-node", "GET", "/api/x", b"", "fake-sig", str(int(_now())), 0
        )
        assert ok is False
        assert "unknown_node" in reason


# ── 6. Registry Integration ──────────────────────────────────────────────────


class TestRegistryIntegration:
    def test_add_peer_generates_secret(self, secrets_dir):
        """FederationRegistry.add_peer auto-generates an HMAC shared secret."""
        config_path = secrets_dir.parent / "config.yaml"
        registry = FederationRegistry.from_config(config_path)
        registry.add_peer("hub-node-1", "https://github.com/peer/repo")

        secret = secret_store.get_shared_secret("hub-node-1")
        assert secret is not None
        assert len(secret) == 64  # 256-bit hex

    def test_remove_peer_revokes_secret(self, secrets_dir):
        """FederationRegistry.remove_peer revokes the HMAC shared secret."""
        config_path = secrets_dir.parent / "config.yaml"
        registry = FederationRegistry.from_config(config_path)
        registry.add_peer("hub-node-2", "https://github.com/peer/repo")

        assert secret_store.get_shared_secret("hub-node-2") is not None

        registry.remove_peer("hub-node-2")
        assert secret_store.get_shared_secret("hub-node-2") is None

    def test_full_flow_register_sign_verify(self, secrets_dir):
        """End-to-end: register peer → sign request → verify request."""
        config_path = secrets_dir.parent / "config.yaml"
        registry = FederationRegistry.from_config(config_path)
        registry.add_peer("federation-hub", "https://hub.misaka.net")

        body = b'{"lessons": ["pip-ssl-fix", "git-rebase"]}'
        headers = build_auth_headers("federation-hub", "POST", "/api/federation/sync", body)

        sig, ts, kv = extract_auth_headers(headers)
        ok, reason = verify_request(
            "federation-hub", "POST", "/api/federation/sync", body, sig, ts, kv
        )
        assert ok is True


# ── 7. NonceCache Unit Tests ─────────────────────────────────────────────────


class TestNonceCache:
    def test_fresh_nonce_accepted(self):
        cache = _NonceCache(max_age=60)
        assert cache.check_and_record("nonce-1") is True

    def test_duplicate_nonce_rejected(self):
        cache = _NonceCache(max_age=60)
        cache.check_and_record("nonce-2")
        assert cache.check_and_record("nonce-2") is False

    def test_expired_nonce_cleaned_up(self):
        cache = _NonceCache(max_age=0)  # instant expiry
        cache.check_and_record("nonce-3")
        # Force cleanup by advancing time
        with patch("time.time", return_value=cache._last_cleanup + 120):
            assert cache.check_and_record("nonce-3") is True  # should be cleaned


# ── 8. Edge Cases ────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_body(self, node_with_secret):
        """Empty body (b'') is valid."""
        sig, ts, _, kv = sign_request(node_with_secret, "GET", "/health", b"")
        ok, _ = verify_request(node_with_secret, "GET", "/health", b"", sig, ts, kv)
        assert ok is True

    def test_large_body(self, node_with_secret):
        """Large body (1MB) signs and verifies correctly."""
        body = b"x" * (1024 * 1024)
        sig, ts, _, kv = sign_request(
            node_with_secret, "POST", "/api/upload", body
        )
        ok, _ = verify_request(
            node_with_secret, "POST", "/api/upload", body, sig, ts, kv
        )
        assert ok is True

    def test_unicode_body(self, node_with_secret):
        """UTF-8 body with CJK characters signs correctly."""
        body = '{"lesson": "pip SSL 证书修复"}'.encode("utf-8")
        sig, ts, _, kv = sign_request(
            node_with_secret, "POST", "/api/lesson", body
        )
        ok, _ = verify_request(
            node_with_secret, "POST", "/api/lesson", body, sig, ts, kv
        )
        assert ok is True

    def test_missing_headers_raises(self):
        """extract_auth_headers raises on missing headers."""
        with pytest.raises(ValueError, match="Missing HMAC"):
            extract_auth_headers({})
