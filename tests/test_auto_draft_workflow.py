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


def test_remote_dispatch_enforces_the_size_limit_after_serialization():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))' in workflow
    assert 'len(serialized.encode("utf-8")) > 65536' in workflow
    assert 'len(value.encode("utf-8")) > 65536' in workflow


def test_manual_file_input_stays_inside_the_checkout():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'WORKSPACE_PATH=$(realpath -- "$GITHUB_WORKSPACE")' in workflow
    assert 'TOMBSTONE_PATH=$(realpath -- "$TOMBSTONE_FILE" 2>/dev/null)' in workflow
    assert '"$WORKSPACE_PATH"/*' in workflow