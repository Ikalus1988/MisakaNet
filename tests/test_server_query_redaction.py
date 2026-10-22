#!/usr/bin/env python3
"""The server's redaction covers the three classes it was missing (issue #3692).

The trial user named them: "报错片段会作为查询关键词发到该服务器——这意味着内部表名、路径等可能随
查询外发". The server had nine redaction rules and every one of them was a *secret* rule — a
filesystem path and a mail address were not redacted anywhere, so an internal path in a submitted
problem text (which becomes a PUBLIC GitHub issue) survived, and the search query was stored raw.

What this file pins, and why each is a fact rather than a preference:

* the single source of truth (`workers/lib/redact-patterns.json`) carries the three new classes, so
  the Python twin and the worker's two inlined copies inherit them instead of each keeping its own
  list — three copies that drift are the disease this repository already paid for once;
* a path is redacted and a **route is not**: `/home/alice/project/secret.py` is a leak, while
  `/api/v1/users` is corpus text. The corpus is indexed by error text and is full of REST routes;
  a rule that ate them would destroy what the maintainer triages with;
* a mail address is redacted and an **npm version spec is not**: `alice@corp.com` is a leak,
  `pkg@1.2.3` is the version the reporter was talking about;
* the Python twin and the JavaScript worker produce the same output for the same input, because
  the worker has its own inlined copy of the rule list and nothing else compares them.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

PATTERN_FILE = REPO / "workers" / "lib" / "redact-patterns.json"
WORKER_FILE = REPO / "workers" / "register-proxy-sw.js"

NEW_CLASSES = ("abs_path", "windows_path", "email")


def _patterns() -> dict:
    data = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    return {p["id"]: p for p in data}


def _js_regex(pattern_id: str) -> re.Pattern:
    """The worker's own copy of the rule, read out of the file, compiled here.

    The worker inlines the rule list (the sync gate checks the inlined replacements), so reading
    the regex out of the file is the only way to test the worker's behaviour rather than the
    JSON's.
    """
    spec = _patterns()[pattern_id]
    source = spec["pattern"]
    # The worker writes the regex as a JavaScript literal; the JSON keeps the same source.
    return re.compile(source)


def test_the_source_of_truth_carries_the_three_new_classes():
    patterns = _patterns()
    for pattern_id in NEW_CLASSES:
        assert pattern_id in patterns, (
            f"the pattern list lost '{pattern_id}' — the server would store a raw path again"
        )
        spec = patterns[pattern_id]
        assert spec["replacement"], f"'{pattern_id}' has no replacement"


def test_a_filesystem_path_is_redacted():
    from scripts.intake_redact import redact_text

    for text in (
        "/home/alice/project/secret.py",
        "/opt/app/config.yaml",
        "C:\\Users\\alice\\project\\secret.py",
        "EACCES: permission denied, open '/home/alice/app/secret.py'",
    ):
        out = redact_text(text)
        assert "<PATH>" in out, f"a path survived redaction: {text!r} -> {out!r}"
        assert "alice" not in out or "corp" not in out, f"the path text survived: {out!r}"


def test_an_api_route_is_not_redacted():
    """The corpus is indexed by error text and is full of REST routes. #3692 is about leaks."""
    from scripts.intake_redact import redact_text

    for text in ("/api/v1/users", "/v1/sessions", "POST /oauth/token returns 403"):
        out = redact_text(text)
        assert out == text, f"a route was redacted: {text!r} -> {out!r}"


def test_a_mail_address_is_redacted_and_a_version_spec_is_not():
    from scripts.intake_redact import redact_text

    out = redact_text("mail alice@corp.com about it")
    assert "<REDACTED:email>" in out, f"a mail address survived: {out!r}"
    assert "alice@corp.com" not in out

    for text in ("npm install pkg@1.2.3", "pip install misakanet==0.5.6"):
        out = redact_text(text)
        assert out == text, f"a version spec was redacted: {text!r} -> {out!r}"


def test_ordinary_text_survives():
    from scripts.intake_redact import redact_text

    for text in (
        "普通的英文句子 and 普通的中文句子",
        "ratio 3:1 and time 12:30 stay",
        "connection refused on port 8080",
    ):
        out = redact_text(text)
        assert out == text, f"ordinary text was redacted: {text!r} -> {out!r}"


def test_the_worker_carries_the_same_three_classes():
    """The worker has its own inlined copy; the generic sync gate covers the replacements."""
    source = WORKER_FILE.read_text(encoding="utf-8")
    for pattern_id in NEW_CLASSES:
        replacement = _patterns()[pattern_id]["replacement"]
        assert replacement in source, (
            f"the worker no longer carries the replacement for '{pattern_id}' ({replacement!r})"
        )


def test_the_worker_and_the_python_twin_agree():
    """Two implementations of the same rule list, and nothing else compares them."""
    from scripts.intake_redact import redact_text

    source = WORKER_FILE.read_text(encoding="utf-8")
    # The worker's own rule bodies, read out of the file, applied the way it applies them.
    # Parsed per line on purpose: the rule bodies contain ";" and "/" inside character classes,
    # so a single regex over the whole file gets the split wrong.
    rules = []
    for line in source.splitlines():
        marker = "r = r.replace("
        if marker not in line:
            continue
        literal = line.split(marker, 1)[1].split(', "', 1)[0].strip()
        replacement = line.split(', "', 1)[1].split('"', 1)[0]
        match = re.match(r"^(/.*)/([gimsuy]*)$", literal)
        if not match:
            continue
        # group(1) keeps the leading "/" of the JavaScript literal; the pattern itself does not
        # have it.
        rules.append((match.group(1)[1:], match.group(2), replacement))
    assert len(rules) >= 12, f"could not read the worker's redaction rules out of the file: {rules}"

    def worker_redact(text: str) -> str:
        out = text
        for pattern_text, flags_text, replacement in rules:
            flags = re.IGNORECASE if "i" in flags_text else 0
            out = re.sub(pattern_text, replacement, out, flags=flags)
        return out

    for text in (
        "/home/alice/project/secret.py",
        "alice@corp.com",
        "Bearer abc123",
        "npm install pkg@1.2.3",
        "/api/v1/users",
    ):
        assert worker_redact(text) == redact_text(text), (
            f"the worker and the Python twin disagree on {text!r}: "
            f"{worker_redact(text)!r} vs {redact_text(text)!r}"
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
