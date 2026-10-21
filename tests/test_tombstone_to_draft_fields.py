# SPDX-License-Identifier: MIT
"""The draft a crash produces — issue #3645.

The chain that turns a crash into a lesson has three links after the payload:
the converter has to read the error text the Node payload carries, the draft
has to be structurally valid enough to be *read* by a contributor, and the
search that follows has to find the lesson about *that* failure.

These tests pin all three, offline: the corpus is the checked-in one, so no
network is involved.
"""
import json
import re
from pathlib import Path

from misakanet.search.engine import MisakaNetSearchEngine
from scripts.lesson_gate import parse_frontmatter, validate_file
from scripts.tombstone_to_draft import (
    DEFAULT_DOMAIN,
    DOMAIN_RULES,
    _canonical_domains,
    _generate_draft,
    _infer_domain,
    _parse_tombstone,
)

REPO = Path(__file__).parent.parent

# A payload as the Node CLI wrapper writes it: the error text in `message`,
# the crash site in `stackSnippet` (#3645).
NODE_WRAPPER_PAYLOAD = {
    "schemaVersion": 1,
    "reason": "process_crash",
    "timestamp": "2026-10-21T12:00:00.000Z",
    "pid": 4242,
    "errorName": "Error",
    "message": "Error: EACCES: permission denied, open '/etc/shadow'",
    "stackSnippet": "at evalFunction (node:internal/process/execution:279:30)",
    "exit_code": 1,
}

# A payload as the in-process path writes it: the error object is in the
# payload, but the process has not exited yet, so there is no exit code.
IN_PROCESS_PAYLOAD = {
    "schemaVersion": 1,
    "reason": "uncaught_exception",
    "timestamp": "2026-10-21T12:00:05.000Z",
    "pid": 4243,
    "errorName": "Error",
    "message": "EACCES: permission denied, open '/etc/shadow'",
    "stackSnippet": "Error: EACCES: permission denied, open '/etc/shadow'\n    at app.js:1:20",
    "exit_code": 1,
}


def _draft(tmp_path: Path, payload: dict) -> Path:
    """Write the draft a tombstone produces into `tmp_path` (never the repo)."""
    tombstone = _parse_tombstone(payload)
    filename, body = _generate_draft(tombstone, "tombstone.json", "")
    # A draft lives in a lesson tree: that is what makes the lesson gate treat
    # it as a lesson entering the corpus (and therefore judge it strictly).
    target = tmp_path / "lessons" / "drafts" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def test_the_node_payload_keeps_the_error_text_in_the_draft():
    """The payload's error text is the only thing a search can be built from."""
    tombstone = _parse_tombstone(NODE_WRAPPER_PAYLOAD)
    assert "EACCES: permission denied" in tombstone["snippet"]
    assert tombstone["exit_code"] == 1


def test_the_in_process_payload_is_converted_even_without_an_exit_code():
    """The in-process payload reports the error before the process exits."""
    payload = {k: v for k, v in IN_PROCESS_PAYLOAD.items() if k != "exit_code"}
    tombstone = _parse_tombstone(payload)
    assert "EACCES: permission denied" in tombstone["snippet"]
    # No exit code was recorded — the crash is recorded as exit 1.
    assert tombstone["exit_code"] == 1


def test_a_generated_draft_declares_evidence_level_and_a_canonical_domain(tmp_path):
    draft = _draft(tmp_path, NODE_WRAPPER_PAYLOAD)
    frontmatter, _content = parse_frontmatter(draft.read_text(encoding="utf-8"))

    assert frontmatter["evidence_level"] == "E0"
    assert frontmatter["domain"] in _canonical_domains()
    assert frontmatter["status"] == "draft"


def test_the_domain_rules_only_name_canonical_domains():
    """A rule that names a domain outside the vocabulary would fail the gate."""
    canonical = _canonical_domains()
    for keyword, domain in DOMAIN_RULES:
        assert domain in canonical, f"{keyword!r} maps to {domain!r}, which is not canonical"
    assert DEFAULT_DOMAIN in canonical


def test_an_eacces_crash_is_classified_as_security():
    assert _infer_domain("process_crash", "Error: EACCES: permission denied") == "security"


def test_the_lesson_gate_still_rejects_a_generated_draft(tmp_path):
    """A draft is not a lesson: it must not pass the gate.

    The fields the crash *can* fill in (evidence_level, domain) are fixed — so
    the gate has to reject the draft for what it still lacks, not for those.
    """
    draft = _draft(tmp_path, NODE_WRAPPER_PAYLOAD)
    errors = validate_file(draft)
    assert errors, "the gate accepted an auto-generated draft"

    joined = "\n".join(errors)
    assert "evidence_level" not in joined
    assert "canonical vocabulary" not in joined
    assert "structured field" in joined


def test_an_eacces_crash_finds_a_lesson_about_permissions():
    """The point of carrying the error text: the search finds *that* lesson.

    With the old payload ("exit code: 1, signal: none") the same search
    returned a lesson about a Claude Code hook — the failure the issue
    reported.
    """
    tombstone = _parse_tombstone(NODE_WRAPPER_PAYLOAD)
    hits = MisakaNetSearchEngine().search(tombstone["snippet"], top=3)
    assert hits, "no lesson answers the crash"

    top = hits[0]
    haystack = f"{top.get('title', '')} {top.get('path', '')}".lower()
    assert re.search(r"permission|eacces", haystack), (
        "the first lesson for an EACCES crash is not about permissions:\n"
        f"  top hit: {top.get('path')} — {top.get('title')}"
    )


def test_the_draft_body_keeps_the_error_text(tmp_path):
    draft = _draft(tmp_path, NODE_WRAPPER_PAYLOAD)
    content = draft.read_text(encoding="utf-8")
    assert "EACCES: permission denied" in content
    # The absolute path is redacted on the way into the draft.
    assert "/etc/shadow" not in content
    assert "[REDACTED_PATH]" in content


def test_a_python_sidecar_tombstone_still_converts():
    """The sidecar's own field names keep working."""
    tombstone = _parse_tombstone({
        "pid": 77,
        "timestamp": "2026-10-21T12:00:00.000Z",
        "reason": "exit code 1",
        "exit_code": 1,
        "snippet": "PermissionError: [Errno 13] Permission denied: '/etc/shadow'",
        "signal": None,
        "host": "box",
        "node_id": "env:MISAKANET_NODE_ID",
    })
    assert tombstone["snippet"].startswith("PermissionError")
    assert tombstone["exit_code"] == 1
    assert _infer_domain(tombstone["reason"], tombstone["snippet"]) == "security"


def test_a_tombstone_without_the_required_fields_is_refused():
    import pytest

    with pytest.raises(ValueError, match="Missing required tombstone fields"):
        _parse_tombstone({"pid": 1, "timestamp": "2026-10-21T12:00:00.000Z"})


def test_the_frontmatter_is_json_and_the_body_has_the_lesson_sections(tmp_path):
    draft = _draft(tmp_path, NODE_WRAPPER_PAYLOAD)
    text = draft.read_text(encoding="utf-8")
    block = text.split("---")[1]
    frontmatter = json.loads(block)
    assert frontmatter["domain"] == "security"
    for section in ("## Problem", "## Root Cause", "## Solution", "## Verification"):
        assert section in text
