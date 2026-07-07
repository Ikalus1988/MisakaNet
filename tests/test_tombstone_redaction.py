import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from tombstone_to_draft import redact_snippet


class TestTombstoneRedaction(unittest.TestCase):
    def test_redacts_sensitive_snippets(self):
        cases = [
            (
                "github token",
                "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
                "[REDACTED_GITHUB_TOKEN]",
            ),
            (
                "bearer token",
                "Bearer abcdefghijklmnopqrstuvwxyz1234567890",
                "Bearer [REDACTED]",
            ),
            (
                "email address",
                "developer@example.internal",
                "[REDACTED_EMAIL]",
            ),
            (
                "windows path",
                r"C:\Users\alice\project\secret.txt",
                "[REDACTED_PATH]",
            ),
            (
                "linux path",
                "/home/alice/project/secret.txt",
                "[REDACTED_PATH]",
            ),
            (
                "192.168 internal ip",
                "192.168.10.25",
                "[REDACTED_IP]",
            ),
            (
                "10.x internal ip",
                "10.42.0.7",
                "[REDACTED_IP]",
            ),
        ]

        for name, sensitive_value, expected_marker in cases:
            with self.subTest(name=name):
                redacted = redact_snippet(f"crash detail: {sensitive_value}")
                self.assertNotIn(sensitive_value, redacted)
                self.assertIn(expected_marker, redacted)


if __name__ == "__main__":
    unittest.main()