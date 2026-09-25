"""The local Python server must mirror the deployed worker's registration contract.

Added with the 2026-09-13 change: a client that identifies itself keeps the same node
(the worker keeps a client_id → node mapping in KV; this server derives the id and
reads the token back from its local record store). Without this, an agent using the
stdio/local server would silently get a new identity per call while the docs promise
otherwise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet.server.handlers import status  # noqa: E402


@pytest.fixture()
def store(monkeypatch):
    """Patch the local record store so tests never touch data/usage_credits.jsonl."""
    records: list[dict] = []
    monkeypatch.setattr(status, "_save_registration", records.append)
    monkeypatch.setattr(
        status, "_registered_tokens",
        lambda: {r["node_id"]: r["token"] for r in records if r.get("token")},
    )
    return records


def test_the_same_client_id_returns_the_same_node_and_token(store):
    first = status.handle_register({"agent_type": "dsh", "client_id": "workspace-abc-123"})
    second = status.handle_register({"agent_type": "dsh", "client_id": "workspace-abc-123"})

    assert first["node_id"] == second["node_id"]
    assert first["token"] == second["token"]
    assert "reused" not in first, "a first registration is not a reuse"
    assert second["reused"] is True


def test_a_different_client_id_gets_its_own_node(store):
    one = status.handle_register({"client_id": "client-one-aaaa"})
    two = status.handle_register({"client_id": "client-two-bbbb"})
    assert one["node_id"] != two["node_id"]
    assert one["token"] != two["token"]


def test_omitting_client_id_keeps_a_new_node_per_call(store):
    one = status.handle_register({})
    two = status.handle_register({})
    assert one["node_id"] != two["node_id"], "backward compatible behaviour"
    assert "reused" not in two


def test_a_malformed_client_id_is_rejected_and_not_recorded(store):
    for bad in ("short", "has spaces", "semi;colon", "x" * 65):
        result = status.handle_register({"client_id": bad})
        assert result["code"] == "invalid_client_id", bad
        assert result["hint"]
    assert store == [], f"invalid input was recorded: {store}"


def test_a_client_id_with_no_stored_token_gets_a_fresh_one(store):
    """The half the old name claimed, and the half the code does not promise.

    This test used to be called `test_client_id_is_not_a_credential`: "Knowing someone's client_id
    must not hand you their token." It never proved that — it *empties the record store* before the
    second call, so a fresh token is the only possible answer. With the store intact, the call
    returns the recorded token, which is what
    `test_the_same_client_id_returns_the_same_node_and_token` above already asserts. Two tests in
    one file disagreeing about that is how "client_id is an identifier, not a credential" survived in
    six documents (corrected 2026-09-24, #2083: the docs now call it a key and tell you to keep it
    private). What this test is actually worth is the pair of properties below.
    """
    mine = status.handle_register({"client_id": "someone-elses-id"})
    assert mine["token"].startswith("mcp_")
    # The derived id is stable, but the token is not persisted *with the id*: with no record to read,
    # a new one is issued rather than a value being recomputed from the client_id.
    status._registered_tokens = lambda: {}  # type: ignore[assignment]
    again = status.handle_register({"client_id": "someone-elses-id"})
    assert again["node_id"] == mine["node_id"]
    assert again["token"] != mine["token"]


def test_knowing_a_client_id_is_enough_to_be_handed_its_token(store):
    """The behaviour that makes `client_id` sensitive, pinned so it cannot drift unnoticed.

    `AGENTS.md` §3.3, `scripts/register_issue.py`, `skills/misakanet/SKILL.md` and the CLI all tell
    the reader to treat `client_id` as a key and to generate a random UUID. That wording is true only
    while this holds. If reuse is ever changed to rotate the token instead, change those documents in
    the same commit — a promise the code does not keep is exactly the defect #2083 recorded.
    """
    first = status.handle_register({"client_id": "8f14e45f-2b1c-4f3a-9d2e-7c6b5a4d3e2f"})
    second = status.handle_register({"client_id": "8f14e45f-2b1c-4f3a-9d2e-7c6b5a4d3e2f"})
    assert second["reused"] is True
    assert second["token"] == first["token"], (
        "the stored token is handed back to anyone who presents the client_id — which is why the "
        "docs call it a credential"
    )
