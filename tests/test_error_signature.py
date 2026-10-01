"""Tests for the error-signature normalizer (#1654).

Golden pairs: same failure class, different volatile artifacts → same hash.
Differential: new normalizer beats intake_bot.fingerprint on volatile-token variance.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.error_signature import (
    SIGNATURE_NORM_VERSION,
    classify,
    compute_dedup_hash,
    compute_signature,
    detect_stack,
    extract_error_line,
    normalize_tokens,
    strip_volatile,
)


# ── golden pairs: same class → same hash ─────────────────────────────────────

GOLDEN_PAIRS = [
    # (description, text_a, text_b)
    (
        "ModuleNotFoundError with different paths/PIDs/timestamps",
        "ModuleNotFoundError: No module named 'requests' in /home/eric/app/main.py (pid 48291, 2026-09-01T12:00:00Z)",
        "ModuleNotFoundError: No module named 'requests' in /Users/bob/project/server.py (pid 12345, 2026-09-15T08:30:00+08:00)",
    ),
    (
        "ConnectionError with different IPs/ports",
        "requests.exceptions.ConnectionError: HTTPSConnectionPool(host='10.0.1.50', port=8443): Max retries exceeded",
        "requests.exceptions.ConnectionError: HTTPSConnectionPool(host='192.168.1.100', port=443): Max retries exceeded",
    ),
    (
        "PermissionError with different paths",
        "PermissionError: [Errno 13] Permission denied: '/data/uploads/config.json'",
        "PermissionError: [Errno 13] Permission denied: '/var/lib/app/settings.yaml'",
    ),
    (
        "exit code 137 (OOM) with different contexts",
        "Killed: process exited with code 137 (out of memory) pid=99823",
        "exit code 137 — container oomkilled pid 44521",
    ),
    (
        "HTTP 503 with different URLs",
        "HTTP 503 Service Unavailable: https://api.example.com/v2/models/chat",
        "HTTP 503 Service Unavailable: https://internal.corp.net/api/v1/submit",
    ),
    (
        "ECONNRESET with different hosts",
        "Error: connect ECONNRESET 10.0.0.1:5432 — proxy",
        "Error: connect ECONNRESET 172.16.0.99:3306 — database",
    ),
    (
        "Swift compilation error with different file paths",
        "/Users/developer/MyApp/Sources/Views/ContentView.swift:42:8: error: cannot find 'foo' in scope",
        "/Users/other/dev/TheirApp/Sources/Main/AppDelegate.swift:15:3: error: cannot find 'foo' in scope",
    ),
    (
        "Docker build failure with different image hashes",
        "error building image: sha256:a1b2c3d4e5f607182930405060708090 failed to compute cache key",
        "error building image: sha256:f0e1d2c3b4a596877869504030201000 failed to compute cache key",
    ),
    (
        "Kubernetes CrashLoopBackOff with different pod names",
        "pod my-app-7b8c9d-x4k2z CrashLoopBackOff: back-off 5m0s restarting failed container",
        "pod frontend-abc12-def34 CrashLoopBackOff: back-off 10m0s restarting failed container",
    ),
    (
        "git merge conflict with different branch names",
        "CONFLICT (content): Merge conflict in src/main.py — feature/auth vs develop",
        "CONFLICT (content): Merge conflict in src/main.py — bugfix/header vs release/2.0",
    ),
    (
        "npm ERESOLVE with different package versions",
        "npm ERR! ERESOLVE could not resolve — @types/node@18.0.0 vs @types/node@20.0.0",
        "npm ERR! ERESOLVE could not resolve — @types/node@16.0.0 vs @types/node@22.0.0",
    ),
    (
        "TypeError with different variable names",
        "TypeError: Cannot read properties of undefined (reading 'map') in /app/src/utils.js:45",
        "TypeError: Cannot read properties of undefined (reading 'map') in /build/worker/handler.ts:120",
    ),
]


@pytest.mark.parametrize("desc,text_a,text_b", GOLDEN_PAIRS, ids=[p[0] for p in GOLDEN_PAIRS])
def test_golden_pair_same_hash(desc: str, text_a: str, text_b: str):
    """Same failure class with different volatile tokens must produce the same signature hash."""
    sig_a = compute_signature(text_a)
    sig_b = compute_signature(text_b)
    assert sig_a["hash"] == sig_b["hash"], (
        f"Hash mismatch for: {desc}\n"
        f"  A: {sig_a['display']}\n     hash={sig_a['hash']}\n"
        f"  B: {sig_b['display']}\n     hash={sig_b['hash']}"
    )


# ── different classes → different hash ───────────────────────────────────────

DIFFERENT_PAIRS = [
    (
        "ModuleNotFoundError vs PermissionError",
        "ModuleNotFoundError: No module named 'requests'",
        "PermissionError: [Errno 13] Permission denied: '/etc/passwd'",
    ),
    (
        "HTTP 401 vs HTTP 503",
        "HTTP 401 Unauthorized: https://api.example.com/auth",
        "HTTP 503 Service Unavailable: https://api.example.com/models",
    ),
    (
        "ECONNRESET vs ETIMEDOUT",
        "Error: connect ECONNRESET 10.0.0.1:5432",
        "Error: connect ETIMEDOUT 10.0.0.1:5432",
    ),
    (
        "git merge conflict vs docker build failure",
        "CONFLICT (content): Merge conflict in src/main.py",
        "error building image: sha256:abc123 failed to compute cache key",
    ),
]


@pytest.mark.parametrize("desc,text_a,text_b", DIFFERENT_PAIRS, ids=[p[0] for p in DIFFERENT_PAIRS])
def test_different_classes_different_hash(desc: str, text_a: str, text_b: str):
    """Different failure classes must produce different signature hashes."""
    sig_a = compute_signature(text_a)
    sig_b = compute_signature(text_b)
    assert sig_a["hash"] != sig_b["hash"], (
        f"Hash collision for different classes: {desc}\n"
        f"  A: {sig_a['display']}\n"
        f"  B: {sig_b['display']}"
    )


# ── Phase 0: error-line extraction ──────────────────────────────────────────

def test_extract_prefers_traceback_exception():
    text = """Traceback (most recent call last):
  File "main.py", line 10, in <module>
    foo()
  File "main.py", line 5, in foo
    requests.get(url)
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='example.com')
"""
    result = extract_error_line(text)
    assert "ConnectionError" in result


def test_extract_falls_back_to_error_line():
    text = """INFO: Starting server
ERROR: Failed to bind to port 8080 — address already in use
"""
    result = extract_error_line(text)
    assert "ERROR" in result or "address already in use" in result


def test_extract_falls_back_to_exit_code():
    text = "Process exited with exit code 137"
    result = extract_error_line(text)
    assert "exit code 137" in result


def test_extract_caps_at_400_chars():
    text = "x" * 1000
    result = extract_error_line(text)
    assert len(result) <= 400


# ── Phase 1: volatile stripping ─────────────────────────────────────────────

def test_strip_paths():
    result = strip_volatile("error in /home/eric/app/main.py")
    assert "/home/eric/app/main.py" not in result
    assert "<PATH>" in result


def test_strip_urls():
    text = "failed to fetch https://api.example.com/v2/models"
    stripped = strip_volatile(text)
    assert "api.example.com" not in stripped
    assert "<URL>" in stripped


def test_strip_uuids():
    text = "job 550e8400-e29b-41d4-a716-446655440000 failed"
    stripped = strip_volatile(text)
    assert "550e8400" not in stripped
    assert "<UUID>" in stripped


def test_strip_iso_timestamp():
    text = "crashed at 2026-09-01T12:00:00Z"
    stripped = strip_volatile(text)
    assert "2026-09-01" not in stripped
    assert "<TS>" in stripped


def test_strip_pid():
    text = "process pid=48291 killed"
    stripped = strip_volatile(text)
    assert "48291" not in stripped
    assert "<PID>" in stripped


def test_strip_emails():
    text = "notify admin@example.com about failure"
    stripped = strip_volatile(text)
    assert "admin@example.com" not in stripped
    assert "<EMAIL>" in stripped


def test_strip_preserves_exception_class():
    text = "ModuleNotFoundError at /home/eric/main.py"
    stripped = strip_volatile(text)
    assert "ModuleNotFoundError" in stripped


# ── Phase 2: token normalization ─────────────────────────────────────────────

def test_normalize_lowercases():
    tokens = normalize_tokens("ModuleNotFoundError")
    assert "modulenotfounderror" in tokens


def test_normalize_keeps_known_tokens():
    tokens = normalize_tokens("permission denied")
    assert "permission" in tokens
    assert "denied" in tokens


def test_normalize_drops_noise():
    tokens = normalize_tokens("the error was a failure during execution")
    assert "the" not in tokens
    assert "a" not in tokens
    assert "was" not in tokens
    # But "error" is dropped as noise only if other informative tokens remain
    assert len(tokens) > 0  # should keep "failure" and "execution"


def test_normalize_keeps_placeholders():
    """Placeholders are lowercased for case-insensitive hashing."""
    tokens = normalize_tokens("<PATH> <PID> <TS>")
    assert "<path>" in tokens
    assert "<pid>" in tokens
    assert "<ts>" in tokens


# ── classification ───────────────────────────────────────────────────────────

def test_classify_exception():
    assert classify("ModuleNotFoundError: No module named 'foo'") == "ModuleNotFoundError"


def test_classify_http():
    assert classify("HTTP 503 Service Unavailable") == "http-503"


def test_classify_errno():
    assert classify("ECONNRESET connection reset") == "econnreset"


def test_classify_exit_code():
    assert classify("process exited with exit code 137") == "exit-137"


def test_classify_generic_with_stack():
    assert "python" in classify("something went wrong with pip install")


def test_classify_generic_fallback():
    result = classify("something totally unknown happened")
    assert result == "generic-failure"


# ── stack detection ──────────────────────────────────────────────────────────

def test_detect_stack_python():
    assert "python" in detect_stack("pip install failed")


def test_detect_stack_node():
    assert "node" in detect_stack("npm ERR! code ERESOLVE")


def test_detect_stack_docker():
    assert "docker" in detect_stack("docker build failed")


def test_detect_stack_multiple():
    stacks = detect_stack("python docker build failed in CI with github actions")
    assert "python" in stacks
    assert "docker" in stacks
    assert "ci" in stacks


# ── dedup hash ───────────────────────────────────────────────────────────────

def test_dedup_hash_same_class_same():
    h1 = compute_dedup_hash("missing_lesson", "ModuleNotFoundError: No module named 'requests'")
    h2 = compute_dedup_hash("missing_lesson", "ModuleNotFoundError: No module named 'flask'")
    assert h1 == h2  # same class → same dedup hash


def test_dedup_hash_different_class():
    h1 = compute_dedup_hash("missing_lesson", "ModuleNotFoundError: No module named 'requests'")
    h2 = compute_dedup_hash("missing_lesson", "PermissionError: denied")
    assert h1 != h2


def test_dedup_hash_with_domain():
    h1 = compute_dedup_hash("missing_lesson", "ModuleNotFoundError: foo", domain="python")
    h2 = compute_dedup_hash("missing_lesson", "ModuleNotFoundError: foo", domain="devops")
    assert h1 != h2  # different domain → different hash


# ── version gate ─────────────────────────────────────────────────────────────

def test_version_is_positive_integer():
    assert isinstance(SIGNATURE_NORM_VERSION, int)
    assert SIGNATURE_NORM_VERSION >= 1


# ── full pipeline ────────────────────────────────────────────────────────────

def test_compute_signature_returns_all_fields():
    sig = compute_signature("ModuleNotFoundError: No module named 'requests' in /home/eric/app.py pid=1234")
    assert "raw" in sig
    assert "stripped" in sig
    assert "tokens" in sig
    assert "kind" in sig
    assert "hash" in sig
    assert "display" in sig
    assert "stack" in sig
    assert "norm_version" in sig
    assert sig["norm_version"] == SIGNATURE_NORM_VERSION


def test_compute_signature_strips_paths_from_stripped():
    sig = compute_signature("error in /home/eric/app/main.py line 42")
    assert "/home/eric" not in sig["stripped"]
    assert "<PATH>" in sig["stripped"]


def test_compute_signature_display_starts_with_kind():
    sig = compute_signature("ModuleNotFoundError: No module named 'requests'")
    assert sig["display"].startswith("ModuleNotFoundError ::")


# ── differential: intake_bot fingerprint weakness ────────────────────────────

def _intake_bot_fingerprint(text: str) -> str:
    """Reproduce intake_bot.fingerprint() for differential testing."""
    import hashlib
    text = text.lower()
    text = re.sub(r"0x[0-9a-f]+", "", text)
    text = re.sub(r"\b\d{2,}\b", "", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha1(text.encode()).hexdigest()[:16]


# These pairs have the same failure class but different volatile tokens that
# intake_bot.fingerprint does NOT strip (absolute paths, ISO timestamps with
# seconds precision kept, ports, PIDs, IPs).
INTAKE_FINGERPRINT_WEAKNESSES = [
    (
        "absolute paths differ",
        "ModuleNotFoundError: No module named 'requests' in /home/eric/app/main.py",
        "ModuleNotFoundError: No module named 'requests' in /Users/bob/project/server.py",
    ),
    (
        "PID differs",
        "Killed: process exited with code 137 (out of memory) pid=99823",
        "Killed: process exited with code 137 (out of memory) pid=44521",
    ),
    (
        "IP/port differs",
        "requests.exceptions.ConnectionError: host 10.0.1.50 port 8443",
        "requests.exceptions.ConnectionError: host 192.168.1.100 port 443",
    ),
    (
        "ISO timestamp differs",
        "crashed at 2026-09-01T12:00:00Z with exit code 137",
        "crashed at 2026-12-25T08:30:00+08:00 with exit code 137",
    ),
]


@pytest.mark.parametrize(
    "desc,text_a,text_b",
    INTAKE_FINGERPRINT_WEAKNESSES,
    ids=[p[0] for p in INTAKE_FINGERPRINT_WEAKNESSES],
)
def test_signature_beats_intake_bot_fingerprint(desc: str, text_a: str, text_b: str):
    """The new normalizer produces the same hash for same-class failures where
    intake_bot.fingerprint produces different hashes (its weakness)."""
    # intake_bot fingerprint should differ (proving the weakness exists)
    fp_a = _intake_bot_fingerprint(text_a)
    fp_b = _intake_bot_fingerprint(text_b)
    # If they happen to match, this pair doesn't demonstrate the weakness — skip
    if fp_a == fp_b:
        pytest.skip("intake_bot fingerprint already matches for this pair")

    # Our normalizer should match
    sig_a = compute_signature(text_a)
    sig_b = compute_signature(text_b)
    assert sig_a["hash"] == sig_b["hash"], (
        f"Signature hash mismatch (should beat fingerprint): {desc}\n"
        f"  fingerprint: {fp_a} vs {fp_b}\n"
        f"  signature:   {sig_a['hash']} vs {sig_b['hash']}"
    )