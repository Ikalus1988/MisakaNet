"""Tests for cross-encoder reranking (Issue #312)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from misakanet.search.engine import _rank_docs_impl, CachedDoc
from pathlib import Path as P


def _make_doc(title, content="", domain="", status="published"):
    d = CachedDoc(
        filename=title.replace(" ", "_") + ".md",
        filepath=P(f"lessons/{title.replace(' ', '_')}.md"),
        content=content,
        title=title,
        domain=domain,
        status=status,
    )
    d.mtime = 0.0
    return d


def test_rerank_flag_accepted():
    """_rank_docs_impl should accept rerank parameter without error."""
    docs = [
        _make_doc("pip install timeout fix", "pip install network timeout error"),
        _make_doc("SSL certificate error", "SSL certificate verification failed"),
    ]
    # Should not raise even without sentence-transformers
    result = _rank_docs_impl("timeout", docs, rerank=True)
    assert len(result) == 2


def test_rerank_graceful_fallback():
    """Without sentence-transformers, should return same results as BM25."""
    docs = [
        _make_doc("pip install timeout fix", "pip install network timeout error"),
        _make_doc("SSL certificate error", "SSL certificate verification failed"),
        _make_doc("proxy configuration", "HTTP proxy setup guide"),
    ]
    result_normal = _rank_docs_impl("timeout", docs, rerank=False)
    result_rerank = _rank_docs_impl("timeout", docs, rerank=True)

    # Without sentence-transformers installed, rerank should fallback to BM25
    # Results should be in same order (or very close)
    assert len(result_normal) == len(result_rerank)
    # Top result should be the same
    assert result_normal[0][1].title == result_rerank[0][1].title


def test_rerank_empty_docs():
    """Empty docs should return empty results."""
    result = _rank_docs_impl("timeout", [], rerank=True)
    assert result == []


def test_rerank_single_doc():
    """Single doc should work fine."""
    docs = [_make_doc("pip install timeout fix", "pip install network timeout error")]
    result = _rank_docs_impl("timeout", docs, rerank=True)
    assert len(result) == 1
