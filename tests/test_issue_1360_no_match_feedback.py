"""Regression tests for the no-match search -> intake continuation contract."""
import json

from scripts.mcp_server import handle_request


def test_no_match_returns_actionable_intake_template(monkeypatch, tmp_path):
    import misakanet.server.handlers.search as search

    monkeypatch.setattr(search, "_SEARCH_STATE", (False, None, False, None))
    monkeypatch.setattr(search, "REPO_ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "lessons.json").write_text("[{}]", encoding="utf-8")

    result = search.handle_search({"query": "quantum computing error correction"})

    assert result["results"] == []
    assert result["no_match"] is True
    assert result["query"] == "quantum computing error correction"
    assert "misakanet_submit_intake" in result["suggestion"]
    assert result["intake"] == {
        "tool": "misakanet_submit_intake",
        "args": {
            "kind": "missing_lesson",
            "problem": "<short description of the failure>",
            "error": "quantum computing error correction",
            "source": "mcp",
        },
    }


def test_match_does_not_include_no_match_feedback(monkeypatch):
    import misakanet.server.handlers.search as search

    monkeypatch.setattr(search, "_SEARCH_STATE", (False, None, False, None))
    monkeypatch.setattr(search, "_fallback_search", lambda *args, **kwargs: [{"title": "match"}])
    result = search.handle_search({"query": "known topic"})
    assert result["results"][0]["title"] == "match"
    assert "no_match" not in result