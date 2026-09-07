"""Unit tests for scripts/intake_receipt.py and MCP receipt handler."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import source_ledger
import intake_receipt
from intake_receipt import (
    build_receipt,
    format_receipt_markdown,
    format_receipt_webhook_payload,
    emit_conversion_receipt,
    scan_promotions,
)
from misakanet.server.handlers.submit import handle_intake_receipt


@pytest.fixture
def temp_ledger(monkeypatch, tmp_path):
    """Fixture providing an isolated temporary source ledger."""
    ledger_path = tmp_path / "source_ledger.json"
    init_data = {
        "_schema": "1.0",
        "_last_updated": "2026-09-07T00:00:00Z",
        "sources": {},
    }
    ledger_path.write_text(json.dumps(init_data), encoding="utf-8")
    monkeypatch.setattr(source_ledger, "LEDGER_PATH", ledger_path)
    monkeypatch.setattr(source_ledger, "LEDGER_FILE", ledger_path)
    monkeypatch.setattr(intake_receipt, "LEDGER_PATH", ledger_path)
    import scripts.source_ledger
    monkeypatch.setattr(scripts.source_ledger, "LEDGER_PATH", ledger_path)
    monkeypatch.setattr(scripts.source_ledger, "LEDGER_FILE", ledger_path)
    return ledger_path


def test_build_receipt():
    """Verify receipt structure and URL formatting."""
    rcpt = build_receipt(
        intake_issue=1528,
        lesson_id="py-async-lock-deadlock",
        source="crawler-gemini",
        evidence_level="E3",
        title="Async Lock Deadlock",
    )
    assert rcpt["receipt_id"] == "rcpt-1528-py-async-lock-deadlock"
    assert rcpt["intake_issue"] == 1528
    assert rcpt["lesson_id"] == "py-async-lock-deadlock"
    assert rcpt["evidence_level"] == "E3"
    assert rcpt["source"] == "crawler-gemini"
    assert rcpt["lesson_url"] == "https://misakanet.org/lessons/py-async-lock-deadlock/"


def test_format_receipt_markdown_no_emojis():
    """Verify markdown output contains required fields without emojis."""
    rcpt = build_receipt(
        intake_issue=1528,
        lesson_id="py-async-lock-deadlock",
        source="crawler-gemini",
        evidence_level="E3",
        title="Async Lock Deadlock",
    )
    md = format_receipt_markdown(rcpt)
    assert "Intake Conversion Receipt" in md
    assert "py-async-lock-deadlock" in md
    assert "E3" in md
    assert "https://misakanet.org/lessons/py-async-lock-deadlock/" in md
    assert "rcpt-1528-py-async-lock-deadlock" in md

    for char in md:
        assert ord(char) < 0x1F000 or ord(char) > 0x1FFFF


def test_format_receipt_webhook_payload():
    """Verify webhook payload serialization and fields."""
    rcpt = build_receipt(
        intake_issue=1528,
        lesson_id="py-async-lock-deadlock",
        source="crawler-gemini",
        evidence_level="E2",
    )
    payload = format_receipt_webhook_payload(rcpt)
    assert "promoted" in payload["event"]
    assert payload["receipt_id"] == "rcpt-1528-py-async-lock-deadlock"
    assert payload["evidence_level"] == "E2"


def test_emit_conversion_receipt_dry_run(temp_ledger):
    """Verify dry run execution does not persist mutations."""
    result = emit_conversion_receipt(
        intake_issue=1528,
        lesson_id="py-async-lock-deadlock",
        source="crawler-gemini",
        evidence_level="E3",
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["emitted"] is True
    assert result["receipt"]["receipt_id"] == "rcpt-1528-py-async-lock-deadlock"


def test_emit_conversion_receipt_idempotent(temp_ledger):
    """Verify duplicate emission requests are safely skipped."""
    with patch("intake_receipt.emit_receipt_comment", return_value=True), \
         patch("intake_receipt.emit_receipt_webhook", return_value=True):
        res1 = emit_conversion_receipt(
            intake_issue=1528,
            lesson_id="py-async-lock-deadlock",
            source="crawler-gemini",
            evidence_level="E3",
            dry_run=False,
            ledger_path=temp_ledger,
        )
        assert res1["emitted"] is True

        res2 = emit_conversion_receipt(
            intake_issue=1528,
            lesson_id="py-async-lock-deadlock",
            source="crawler-gemini",
            evidence_level="E3",
            dry_run=False,
            ledger_path=temp_ledger,
        )
        assert res2["emitted"] is False
        assert res2["skipped"] is True


def test_scan_promotions(temp_ledger, tmp_path):
    """Verify scanning lessons finds intake contributions lacking receipts."""
    lessons_file = tmp_path / "lessons.json"
    lessons_data = [
        {
            "id": "lesson-with-intake",
            "title": "Lesson with Intake",
            "source": "crawler-test",
            "intake_issue": 9999,
            "evidence_level": "E2",
        },
        {
            "id": "lesson-without-intake",
            "title": "Lesson without Intake",
            "source": "unknown",
        },
    ]
    lessons_file.write_text(json.dumps(lessons_data), encoding="utf-8")

    promotions = scan_promotions(lessons_path=lessons_file, ledger_path=temp_ledger)
    assert len(promotions) == 1
    assert promotions[0]["lesson_id"] == "lesson-with-intake"
    assert promotions[0]["intake_issue"] == 9999
    assert promotions[0]["evidence_level"] == "E2"


def test_handle_intake_receipt_server_tool(temp_ledger):
    """Verify MCP tool handler queries ledger and lesson catalog."""
    source_ledger.record_promotion(
        source="mcp",
        lesson_id="mcp-test-lesson",
        evidence_level="E3",
        intake_issue=7777,
        title="MCP Test Lesson",
    )
    source_ledger.record_receipt(
        source="mcp",
        intake_issue=7777,
        lesson_id="mcp-test-lesson",
        receipt_id="rcpt-7777-mcp-test-lesson",
        channel="mcp",
    )

    res = handle_intake_receipt({"intake_id": "issue-7777"})
    assert res["found"] is True
    assert res["status"] == "promoted"
    assert res["lesson"]["id"] == "mcp-test-lesson"
    assert res["lesson"]["evidence_level"] == "E3"
    assert res["receipt_id"] == "rcpt-7777-mcp-test-lesson"

    res_unpromoted = handle_intake_receipt({"intake_id": "issue-99999"})
    assert res_unpromoted["found"] is True
    assert res_unpromoted["status"] == "pending_review"
