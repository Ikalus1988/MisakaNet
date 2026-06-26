"""
Tests for hub/master/token_manager.py — no-keyring fallback paths.

Covers P1 item: token manager when keyring is not available.
Verifies that:
  1. TokenManager gracefully falls back to plaintext JSON when keyring is absent
  2. Warning is emitted for insecure fallback
  3. Token save/load round-trips correctly without keyring
  4. AuditLogger does not crash on init
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

# Ensure repo root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock aiohttp so hub.master can be imported without the optional dep
sys.modules["aiohttp"] = mock.MagicMock()

# Now safe to import
from hub.master.token_manager import AuditLogger, TokenManager  # noqa: E402


class TestTokenManagerNoKeyring(unittest.TestCase):
    """Test TokenManager when keyring is NOT available."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="misakanet_test_")
        self.token_path = os.path.join(self.tmpdir, ".hermes-tokens")

    def tearDown(self):
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
        try:
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    @mock.patch("hub.master.token_manager.os.path.expanduser")
    def test_init_creates_empty_tokens_when_no_file_no_keyring(self, mock_expanduser):
        """TokenManager starts with empty tokens when no keyring and no file."""
        mock_expanduser.return_value = self.token_path

        # Simulate keyring being completely absent
        import builtins

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "keyring" or name.startswith("keyring."):
                raise ImportError("No module named 'keyring'")
            return orig_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            with self.assertWarns(UserWarning):
                tm = TokenManager(keyring_service="test-nokeyring")
            self.assertEqual(tm._tokens, {})
            self.assertFalse(tm._keyring_available)

    @mock.patch("hub.master.token_manager.os.path.expanduser")
    def test_save_and_load_tokens_no_keyring(self, mock_expanduser):
        """Token round-trip works without keyring."""
        mock_expanduser.return_value = self.token_path
        os.makedirs(self.tmpdir, exist_ok=True)

        import builtins

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "keyring" or name.startswith("keyring."):
                raise ImportError("No module named 'keyring'")
            return orig_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            with self.assertWarns(UserWarning):
                tm = TokenManager(keyring_service="test-nokeyring")

            tm._tokens["test-token-abc"] = {
                "created_at": "2026-01-01T00:00:00",
                "expires_at": "2099-01-01T00:00:00",
                "secret_hash": "abc123",
            }
            tm._save_tokens()

            self.assertTrue(os.path.exists(self.token_path))
            mode = os.stat(self.token_path).st_mode & 0o777
            if sys.platform == "win32":
                self.assertWarnsRegex(
                    UserWarning,
                    "cannot guarantee POSIX 0600",
                    tm._restrict_plaintext_file,
                    self.token_path,
                )
            else:
                self.assertEqual(mode, 0o600, f"Expected 0600, got {oct(mode)}")

            with open(self.token_path) as f:
                saved = json.load(f)
            self.assertIn("test-token-abc", saved)

    @mock.patch("hub.master.token_manager.os.path.expanduser")
    def test_revive_from_plaintext_file(self, mock_expanduser):
        """TokenManager can load tokens from a pre-existing plaintext file."""
        mock_expanduser.return_value = self.token_path

        pre_data = {
            "existing-token": {
                "created_at": "2026-01-01T00:00:00",
                "expires_at": "2099-01-01T00:00:00",
                "secret_hash": "def456",
            }
        }
        with open(self.token_path, "w") as f:
            json.dump(pre_data, f)
        os.chmod(self.token_path, 0o600)

        import builtins

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "keyring" or name.startswith("keyring."):
                raise ImportError("No module named 'keyring'")
            return orig_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=mock_import):
            with self.assertWarns(UserWarning):
                tm = TokenManager(keyring_service="test-nokeyring")
            self.assertIn("existing-token", tm._tokens)
            self.assertEqual(tm._tokens["existing-token"]["secret_hash"], "def456")


class TestAuditLogger(unittest.TestCase):
    """Test AuditLogger basic functionality."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="misakanet_audit_")
        self.log_path = os.path.join(self.tmpdir, "audit.jsonl")

    def tearDown(self):
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        try:
            os.rmdir(self.tmpdir)
        except OSError:
            pass

    def test_log_creates_file(self):
        """AuditLogger.log() creates the log file and writes an entry."""
        logger = AuditLogger(log_path=self.log_path, retention_days=30)
        logger.log("TEST_ACTION", "test-actor-12345", {"detail": "value"})

        self.assertTrue(os.path.exists(self.log_path))
        with open(self.log_path) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertEqual(entry["action"], "TEST_ACTION")
        self.assertTrue(entry["actor"].endswith("..."))
        self.assertEqual(entry["details"]["detail"], "value")

    def test_log_missing_directory_creates_it(self):
        """AuditLogger creates parent directory if missing."""
        nested_path = os.path.join(self.tmpdir, "deep", "nested", "audit.jsonl")
        logger = AuditLogger(log_path=nested_path)
        logger.log("INIT", "actor", {})
        self.assertTrue(os.path.exists(nested_path))


if __name__ == "__main__":
    unittest.main()
