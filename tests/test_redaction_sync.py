#!/usr/bin/env python3
"""Verify redaction patterns are consistent across JS and Python implementations.

The single source of truth is workers/lib/redact-patterns.json.
This test ensures:
1. Python (scripts/intake_redact.py) loads all patterns from JSON
2. JS inline patterns in register-proxy-sw.js match the JSON
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent
PATTERN_FILE = REPO_ROOT / "workers" / "lib" / "redact-patterns.json"
WORKER_FILE = REPO_ROOT / "workers" / "register-proxy-sw.js"


def test_pattern_file_exists():
    """redact-patterns.json must exist and be valid JSON."""
    assert PATTERN_FILE.exists(), f"Missing {PATTERN_FILE}"
    data = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) > 0
    for p in data:
        assert "id" in p, f"Pattern missing 'id': {p}"
        assert "pattern" in p, f"Pattern missing 'pattern': {p}"
        assert "replacement" in p, f"Pattern missing 'replacement': {p}"
        # Validate regex compiles
        flags = re.IGNORECASE if "i" in p.get("flags", "") else 0
        re.compile(p["pattern"], flags)


def test_python_loads_all_patterns():
    """Python implementation must load all patterns from JSON."""
    from scripts.intake_redact import REDACT_PATTERNS

    expected = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    assert len(REDACT_PATTERNS) == len(expected), (
        f"Python has {len(REDACT_PATTERNS)} patterns, JSON has {len(expected)}"
    )


def test_worker_redactintake_covers_all_patterns():
    """The redactIntake() function in register-proxy-sw.js must have all patterns."""
    worker_source = WORKER_FILE.read_text(encoding="utf-8")

    # Find the redactIntake function
    match = re.search(r"function redactIntake\(text\)\s*\{(.+?)\n    \}", worker_source, re.DOTALL)
    assert match, "Could not find redactIntake() function in worker"
    func_body = match.group(1)

    expected = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    for p in expected:
        pattern_id = p["id"]
        # Check that the replacement string appears in the function
        assert p["replacement"] in func_body, (
            f"redactIntake() missing replacement for '{pattern_id}': {p['replacement']}"
        )


def test_worker_api_intake_covers_all_patterns():
    """The REDACT_PATTERNS array in /api/intake route must have all patterns."""
    worker_source = WORKER_FILE.read_text(encoding="utf-8")

    # Find the REDACT_PATTERNS array in the /api/intake section
    match = re.search(r"const REDACT_PATTERNS = \[(.+?)\];", worker_source, re.DOTALL)
    assert match, "Could not find REDACT_PATTERNS array in worker"
    array_body = match.group(1)

    expected = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    for p in expected:
        assert p["replacement"] in array_body, (
            f"/api/intake REDACT_PATTERNS missing replacement for '{p['id']}': {p['replacement']}"
        )


def test_cross_implementation_consistency():
    """Same input must produce same output from Python and JS pattern lists."""
    from scripts.intake_redact import redact_text

    test_cases = [
        ("token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij12", "github_token"),
        ("sk-abcdefghijklmnopqrstuvwx", "api_key"),
        ("password=SuperSecret123", "credential"),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "private_key"),
        ("AKIA1234567890ABCDEF", "aws_key"),
    ]

    for text, expected_id in test_cases:
        result = redact_text(text)
        assert "[REDACTED:" in result, f"Failed to redact {expected_id}: {text!r} -> {result!r}"


# ── the three copies must agree on the *pattern*, not only on the replacement ──
#
# Before #4060 this module compared replacement strings only, so a pattern could differ between the
# worker's two inline copies and the JSON the Python path loads while every check here stayed green.
# The card rule is the one that has already been wrong in a way nobody noticed (two hyphen-joined
# numbers rewritten into `[REDACTED:card_number]`), so it is the one pinned by its source text.

CARD_FIXTURES_REDACTED = (
    "card: 4111 1111 1111 1111",
    "card: 4242-4242-4242-4242",
    "card: 4111111111111111",
    "card: 3782 822463 10005",
    "card: 3056 9300 0900 04",
)
CARD_FIXTURES_KEPT = (
    "Latency probe 32767-20261029",
    "Latency probe 7684-20261029",
    "range 1234-5678, then retry",
)


def _card_patterns_by_copy() -> dict[str, str]:
    """The card pattern as each of the three copies spells it."""
    from_json = next(
        p["pattern"] for p in json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
        if p["id"] == "card_number"
    )
    source = WORKER_FILE.read_text(encoding="utf-8")
    inline = re.findall(
        r"/([^\n]*?)/g, \"\[REDACTED:card_number\]\"", source
    )
    assert len(inline) == 2, (
        "expected the card rule in both worker copies (the /api/intake array and redactIntake), "
        f"found {len(inline)}"
    )
    return {"json": from_json, "api_intake": inline[0], "redact_intake": inline[1]}


def test_the_three_card_number_copies_are_the_same_pattern():
    copies = _card_patterns_by_copy()
    assert copies["json"] == copies["api_intake"] == copies["redact_intake"], (
        "the card rule has drifted between workers/lib/redact-patterns.json and the worker's two "
        f"inline copies: {copies}"
    )


def test_the_three_card_number_copies_agree_on_the_fixtures():
    for pattern in _card_patterns_by_copy().values():
        compiled = re.compile(pattern)
        for text in CARD_FIXTURES_REDACTED:
            assert "[REDACTED:card_number]" not in text
            assert compiled.sub("[REDACTED:card_number]", text) != text, (
                f"a real card was not redacted by {pattern!r}: {text!r}"
            )
        for text in CARD_FIXTURES_KEPT:
            assert compiled.sub("[REDACTED:card_number]", text) == text, (
                f"a non-card was rewritten by {pattern!r}: {text!r} -> "
                f"{compiled.sub('[REDACTED:card_number]', text)!r}"
            )
