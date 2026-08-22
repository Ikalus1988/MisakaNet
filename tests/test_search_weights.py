import importlib
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

engine = importlib.import_module("misakanet.search.engine")


def _doc(name, content, title=""):
    return engine.CachedDoc(
        filename=f"{name}.md",
        filepath=REPO / "lessons" / "core" / f"{name}.md",
        content=content,
        title=title or name,
        status="published",
    )


def test_weights_are_normalized():
    assert engine._validate_search_weights(2, 1) == (pytest.approx(2 / 3), pytest.approx(1 / 3))


@pytest.mark.parametrize("weights", [(0, 0), (-1, 1), ("bad", 1)])
def test_invalid_weights_fail_closed(weights):
    with pytest.raises(ValueError):
        engine._validate_search_weights(*weights)


def test_vector_weight_can_change_ranking_without_model_dependency(monkeypatch):
    first = _doc("first", "database timeout", "first")
    second = _doc("second", "database timeout", "second")
    monkeypatch.setattr(engine, "_compute_bm25_scores", lambda query, docs: [1.0, 0.0])
    ranked = engine._rank_docs_impl(
        "query", [first, second], bm25_weight=0, vector_weight=1,
        vector_scores=[0.1, 0.9],
    )
    assert ranked[0][1] is second


def test_config_file_controls_weights(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("retrieval:\n  bm25_weight: 0.8\n  vector_weight: 0.2\n", encoding="utf-8")
    monkeypatch.delenv("MISAKANET_BM25_WEIGHT", raising=False)
    monkeypatch.delenv("MISAKANET_VECTOR_WEIGHT", raising=False)
    assert engine.load_search_weights(config) == (pytest.approx(0.8), pytest.approx(0.2))
