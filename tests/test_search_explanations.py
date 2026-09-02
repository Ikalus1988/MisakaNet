import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.search import engine


def _doc(name, content, title="", domain=""):
    return engine.CachedDoc(
        filename=f"{name}.md",
        filepath=REPO / "lessons" / "core" / f"{name}.md",
        content=content,
        title=title or name,
        domain=domain,
        tags=["timeout"],
        status="published",
    )


def test_breakdown_exposes_terms_entities_and_hybrid_components(monkeypatch):
    doc = _doc("pip-timeout", "pip timeout timeout proxy", "pip timeout", "python")
    other = _doc("other", "proxy guidance", "other", "devops")
    monkeypatch.setattr(engine, "_compute_bm25_scores", lambda query, docs: [0.75])
    monkeypatch.setattr(engine, "_vector_similarity", lambda query, item: 0.42)

    breakdown = engine._score_breakdown("pip timeout", doc, docs=[doc, other])

    assert breakdown["bm25"] == pytest.approx(0.75)
    assert breakdown["vector_similarity"] == pytest.approx(0.42)
    assert breakdown["entity_matches"]["title"] == ["pip", "timeout"]
    assert "domain" not in breakdown["entity_matches"]
    assert {term["term"] for term in breakdown["bm25_terms"]} == {"pip", "timeout"}
    assert set(breakdown["hybrid"]) == {
        "bm25_component", "metadata_component", "baseline_component",
        "boost_component", "vector_component",
    }


def test_vector_explanation_fails_explicitly_when_backend_unavailable(monkeypatch):
    doc = _doc("plain", "keyword", "plain")
    monkeypatch.setattr(engine, "_compute_bm25_scores", lambda query, docs: [0.1])
    monkeypatch.setattr(engine, "_vector_similarity", lambda query, item: None)
    breakdown = engine._score_breakdown("keyword", doc)
    assert breakdown["vector_similarity"] is None
    assert breakdown["hybrid"]["vector_component"] is None
