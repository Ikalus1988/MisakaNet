"""Unit tests for scripts/source_ledger.py."""
import json
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import source_ledger
from source_ledger import (
    load_ledger,
    save_ledger,
    record_submission,
    record_dedup,
    record_promotion,
    record_receipt,
    is_receipt_emitted,
    get_source_stats,
    get_summary,
    sync_promotions_from_lessons,
)


@pytest.fixture
def temp_ledger(monkeypatch, tmp_path):
    ledger_path = tmp_path / "source_ledger.json"
    init_data = {
        "_schema": "1.0",
        "_last_updated": "2026-09-07T00:00:00Z",
        "sources": {},
    }
    ledger_path.write_text(json.dumps(init_data), encoding="utf-8")
    monkeypatch.setattr(source_ledger, "LEDGER_PATH", ledger_path)
    monkeypatch.setattr(source_ledger, "LEDGER_FILE", ledger_path)
    return ledger_path


def test_load_and_save_ledger(temp_ledger):
    data = load_ledger()
    assert data["_schema"] == "1.0"
    assert "sources" in data

    data["sources"]["test-bot"] = {"submitted": 1, "deduped": 0, "promoted": 0}
    save_ledger(data)

    reloaded = load_ledger()
    assert "test-bot" in reloaded["sources"]
    assert reloaded["sources"]["test-bot"]["submitted"] == 1


def test_record_submission(temp_ledger):
    record_submission(source="crawler-a", issue_number=1001)
    record_submission(source="crawler-a", issue_number=1002)
    record_submission(source="crawler-a", issue_number=1001)

    stats = get_source_stats("crawler-a")
    assert stats["submitted"] == 3
    assert 1001 in stats["intake_issues"]
    assert 1002 in stats["intake_issues"]


def test_record_dedup(temp_ledger):
    record_submission(source="crawler-b", issue_number=2001)
    record_dedup(source="crawler-b", count=3)

    stats = get_source_stats("crawler-b")
    assert stats["submitted"] == 1
    assert stats["deduped"] == 3


def test_record_promotion(temp_ledger):
    record_submission(source="agent-c", issue_number=3001)
    record_promotion(
        source="agent-c",
        lesson_id="py-async-lock-deadlock",
        evidence_level="E3",
        intake_issue=3001,
        title="Async Lock Deadlock",
    )

    stats = get_source_stats("agent-c")
    assert stats["promoted"] == 1
    assert len(stats["lessons"]) == 1
    assert stats["lessons"][0]["lesson_id"] == "py-async-lock-deadlock"
    assert stats["lessons"][0]["evidence_level"] == "E3"
    assert stats["conversion_rate"] == 1.0


def test_record_receipt_and_idempotency(temp_ledger):
    record_submission(source="agent-d", issue_number=4001)
    assert not is_receipt_emitted(4001, "py-test-lesson")

    entry = record_receipt(
        source="agent-d",
        intake_issue=4001,
        lesson_id="py-test-lesson",
        receipt_id="rcpt-4001-py-test-lesson",
        channel="comment",
    )
    assert any(r["receipt_id"] == "rcpt-4001-py-test-lesson" for r in entry["receipts"])
    assert is_receipt_emitted(4001, "py-test-lesson")
    assert is_receipt_emitted("agent-d", 4001, "py-test-lesson")

    duplicate_entry = record_receipt(
        source="agent-d",
        intake_issue=4001,
        lesson_id="py-test-lesson",
        receipt_id="rcpt-4001-py-test-lesson",
        channel="comment",
    )
    assert len(duplicate_entry["receipts"]) == 1

    stats = get_source_stats("agent-d")
    assert len(stats["receipts"]) == 1


def test_get_summary_metrics(temp_ledger):
    record_submission(source="s1", issue_number=101)
    record_submission(source="s1", issue_number=102)
    record_dedup(source="s1", count=1)
    record_promotion(source="s1", lesson_id="l1", evidence_level="E2", intake_issue=101)

    record_submission(source="s2", issue_number=201)

    summary = get_summary()
    assert summary["total_sources"] == 2
    assert summary["total_submitted"] == 3
    assert summary["total_deduped"] == 1
    assert summary["total_promoted"] == 1
    assert summary["overall_conversion_rate"] == round(1 / 3, 3)
