from misakanet import Inbox


def test_submit_is_self_describing_and_poll_gets_answer():
    box = Inbox()
    first = box.submit_intake("How do I do X?", "node-7")
    assert first["answered"] is False
    assert first["problem_key"] in first["pull_instruction"] or "problem_key" in first["pull_instruction"]
    box.record_answer("node-7", problem_key=first["problem_key"], answer="Do Y.", issue="#1", lesson="tested", evidence_level="verified")
    got = box.me_events("node-7", first["problem_key"])
    assert got["events"] == [{"problem_key": first["problem_key"], "evidence_level": "verified", "answered": True, "answer": "Do Y.", "issue": "#1", "lesson": "tested"}]


def test_unanswered_is_explicit_not_empty_success():
    result = Inbox().me_events("node-never")
    assert result["status"] == "no_answer_yet"
    assert result["message"]


def test_answer_and_resolution_share_stream_and_no_plaintext_is_stored():
    box = Inbox()
    submitted = box.submit_intake("secret question text", "node")
    box.record_resolution("node", submitted["problem_key"], issue="#1528", lesson="converted", evidence_level="verified")
    event = box.me_events("node")["events"][0]
    assert event["resolved"] and event["issue"] == "#1528"
    assert "secret question text" not in str(box.db.execute("SELECT * FROM events").fetchall())


def test_agent_type_cannot_be_identity_and_validation():
    box = Inbox()
    try:
        box.submit_intake("x", "")
        assert False
    except ValueError:
        pass
