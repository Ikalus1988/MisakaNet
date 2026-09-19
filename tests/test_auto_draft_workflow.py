from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "auto-draft.yml"


def test_auto_draft_uses_the_converter_contract():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "--create-issue" in workflow
    assert "--create-bounty" not in workflow
    assert ".issue.json" in workflow
    assert ".bounty.json" not in workflow


def test_remote_dispatch_has_a_real_tombstone_source():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "client_payload.tombstone" in workflow
    assert "client_payload.tombstone_json" in workflow
    assert 'elif [ -f "crash-reports/latest-tombstone.json" ]' not in workflow