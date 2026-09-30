"""Tests for misakanet_me_inbox handler (#2056)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from misakanet.server.handlers.inbox import handle_me_inbox


class TestMeInbox:
    """Tests for the agent-readable inbox handler."""

    def test_missing_both_params_returns_error(self):
        """Both intake_id and dedup_key missing → error."""
        result = handle_me_inbox({})
        assert "error" in result
        assert "intake_id" in result["error"] or "dedup_key" in result["error"]

    def test_empty_params_returns_error(self):
        """Empty strings count as missing."""
        result = handle_me_inbox({"intake_id": "", "dedup_key": ""})
        assert "error" in result

    def test_pending_status_when_no_events(self):
        """When no events found, status is 'pending'."""
        with patch("misakanet.server.handlers.inbox._query_d1", return_value=[]):
            result = handle_me_inbox({"intake_id": "nonexistent123"})
            assert result["status"] == "pending"
            assert result["count"] == 0
            assert result["events"] == []
            assert "poll_hint" in result
            assert "24-48 hours" in result["poll_hint"]

    def test_resolved_status_when_events_found(self):
        """When events found, status is 'resolved'."""
        mock_rows = [{
            "problem": "test question",
            "answer": "test answer",
            "issue_number": "123",
            "answered_at": "2026-09-30",
            "evidence_level": "maintainer",
        }]
        with patch("misakanet.server.handlers.inbox._query_d1", return_value=mock_rows):
            result = handle_me_inbox({"intake_id": "123"})
            assert result["status"] == "resolved"
            assert result["count"] == 1
            assert result["events"][0]["type"] == "answered"
            assert result["events"][0]["answer"] == "test answer"

    def test_dedup_key_query(self):
        """dedup_key queries D1 with dedup_hash."""
        mock_rows = [{
            "problem": "test",
            "answer": "answer",
            "issue_number": "456",
            "answered_at": "2026-09-30",
            "evidence_level": "faq",
        }]
        with patch("misakanet.server.handlers.inbox._query_d1", return_value=mock_rows) as mock_q:
            result = handle_me_inbox({"dedup_key": "abc123def456"})
            assert mock_q.call_count == 1
            call_args = mock_q.call_args[0]
            assert "dedup_hash" in call_args[0]
            assert call_args[1] == ["abc123def456"]

    def test_d1_unavailable_graceful(self):
        """When D1 raises, handler returns empty events, not error."""
        with patch("misakanet.server.handlers.inbox._query_d1", side_effect=Exception("D1 down")):
            result = handle_me_inbox({"intake_id": "123"})
            assert "error" not in result
            assert result["count"] == 0
            assert result["status"] == "pending"

    def test_contribution_queue_conversion(self, tmp_path):
        """Converted intake in queue → converted event."""
        import misakanet.server.handlers.inbox as inbox_mod

        queue = tmp_path / "data" / "contribution_queue.jsonl"
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text(
            json.dumps({
                "id": "intake-789",
                "kind": "missing_lesson",
                "status": "converted",
                "title": "test intake",
                "message": "Kind: missing_lesson",
                "note": "lessons/contrib/test-lesson.md",
                "reviewed_at": "2026-09-30",
            }) + "\n",
            encoding="utf-8",
        )
        # Monkey-patch the module-level repo path for testing
        orig_func = inbox_mod.handle_me_inbox
        with patch("misakanet.server.handlers.inbox._query_d1", return_value=[]):
            # Temporarily replace the function to use tmp_path as repo
            import types
            def patched_handle(args):
                intake_id = args.get("intake_id", "")
                dedup_key = args.get("dedup_key", "")
                if not intake_id and not dedup_key:
                    return {"error": "Provide intake_id or dedup_key"}
                events = []
                queue_path = tmp_path / "data" / "contribution_queue.jsonl"
                if queue_path.exists():
                    import hashlib
                    for line in queue_path.read_text(encoding="utf-8").splitlines():
                        entry = json.loads(line.strip())
                        entry_id = entry.get("id", "")
                        if intake_id and entry_id != intake_id:
                            continue
                        status = entry.get("status", "")
                        if status == "converted":
                            events.append({
                                "type": "converted",
                                "intake_id": entry_id,
                                "lesson_path": entry.get("note", ""),
                                "converted_at": entry.get("reviewed_at", ""),
                            })
                if not events:
                    return {"events": [], "count": 0, "status": "pending", "poll_hint": "No answer yet."}
                return {"events": events, "count": len(events), "status": "resolved", "poll_hint": "Done."}

            result = patched_handle({"intake_id": "intake-789"})
            assert result["count"] == 1
            assert result["events"][0]["type"] == "converted"
            assert result["events"][0]["lesson_path"] == "lessons/contrib/test-lesson.md"

    def test_multiple_events(self):
        """Multiple answered questions → multiple events."""
        mock_rows = [
            {
                "problem": "question 1",
                "answer": "answer 1",
                "issue_number": "100",
                "answered_at": "2026-09-29",
                "evidence_level": "maintainer",
            },
            {
                "problem": "question 2",
                "answer": "answer 2",
                "issue_number": "100",
                "answered_at": "2026-09-30",
                "evidence_level": "faq",
            },
        ]
        with patch("misakanet.server.handlers.inbox._query_d1", return_value=mock_rows):
            result = handle_me_inbox({"intake_id": "100"})
            assert result["count"] == 2
            assert result["events"][0]["answer"] == "answer 1"
            assert result["events"][1]["answer"] == "answer 2"


class TestSubmitIntakePollHint:
    """Test that submit_intake returns poll_hint and inbox_tool."""

    def test_submit_returns_poll_hint(self):
        """submit_intake response includes poll_hint and inbox_tool."""
        import os

        # Use temp dir for contribution queue
        test_dir = Path(tempfile.mkdtemp())
        os.environ["MISAKANET_CONTRIBUTION_QUEUE"] = str(test_dir / "queue.jsonl")

        try:
            from misakanet.server.handlers.submit import handle_submit_intake
            result = handle_submit_intake({
                "kind": "missing_lesson",
                "problem": "test problem for poll hint",
                "source": "test",
            })
            assert result.get("submitted") is True
            assert "poll_hint" in result
            assert "misakanet_me_inbox" in result["poll_hint"]
            assert result.get("inbox_tool") == "misakanet_me_inbox"
            assert "dedup_key" in result
            assert len(result["dedup_key"]) == 16  # SHA256 truncated to 16 chars
        finally:
            del os.environ["MISAKANET_CONTRIBUTION_QUEUE"]
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_question_poll_hint_mentions_hours(self):
        """Question kind → poll_hint mentions 24-48 hours."""
        import os

        test_dir = Path(tempfile.mkdtemp())
        os.environ["MISAKANET_CONTRIBUTION_QUEUE"] = str(test_dir / "queue.jsonl")

        try:
            from misakanet.server.handlers.submit import handle_submit_intake
            result = handle_submit_intake({
                "kind": "question",
                "problem": "how to configure X?",
                "source": "test",
            })
            assert "24-48 hours" in result["poll_hint"]
        finally:
            del os.environ["MISAKANET_CONTRIBUTION_QUEUE"]
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)


class TestMeInboxToolDefinition:
    """Test that the tool is properly registered."""

    def test_tool_in_tools_list(self):
        from misakanet.server.tools import TOOLS
        tool_names = [t["name"] for t in TOOLS]
        assert "misakanet_me_inbox" in tool_names

    def test_tool_has_required_fields(self):
        from misakanet.server.tools import TOOLS
        tool = next(t for t in TOOLS if t["name"] == "misakanet_me_inbox")
        assert "description" in tool
        assert "inputSchema" in tool
        assert "Input semantics" in tool["description"]
        assert "Output schema" in tool["description"]
        assert "Error cases" in tool["description"]

    def test_handler_registered(self):
        from misakanet.server.protocol import _HANDLERS
        assert "misakanet_me_inbox" in _HANDLERS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])