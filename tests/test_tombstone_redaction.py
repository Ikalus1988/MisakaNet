"""
Regression tests for redact_snippet() in scripts/tombstone_to_draft.py

Each test checks that the redacted output does NOT contain the original
sensitive value, for each supported redaction category:
  - GitHub tokens (ghp_...)
  - Bearer tokens
  - Email addresses
  - Absolute Windows paths
  - Absolute Linux paths
  - Internal IPs (192.168.x.x, 10.x.x.x)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.tombstone_to_draft import redact_snippet


def test_redact_github_token():
    original = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    text = f"auth failed with token {original}"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted


def test_redact_bearer_token():
    original = "Bearer abcdef123456.token.value"
    text = f"request header: Authorization: {original}"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED]" in redacted


def test_redact_email_address():
    original = "user@example.com"
    text = f"error reported by {original}"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_redact_windows_path():
    original = r"C:\Users\johndoe\AppData\Local\Temp\crash.log"
    text = f"failed to read {original}"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED_PATH]" in redacted


def test_redact_linux_path():
    original = "/home/johndoe/projects/app/main.py"
    text = f"traceback in {original}"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED_PATH]" in redacted


def test_redact_internal_ip():
    original = "192.168.1.42"
    text = f"connection refused from {original}"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED_IP]" in redacted


def test_redact_internal_ip_10_range():
    original = "10.0.0.5"
    text = f"internal host {original} unreachable"
    redacted = redact_snippet(text)
    assert original not in redacted
    assert "[REDACTED_IP]" in redacted
