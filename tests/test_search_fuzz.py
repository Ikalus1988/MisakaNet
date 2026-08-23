"""Hypothesis fuzz tests for search (Issue #1182).

Tests that search functions never crash on arbitrary input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from hypothesis import given, strategies as st, settings, HealthCheck
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

# Skip if hypothesis not installed
pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


def _get_fallback_search():
    """Get fallback search function."""
    from scripts.mcp_server import _fallback_search
    return _fallback_search


def _get_bm25_search():
    """Get BM25 search function if available."""
    try:
        from misakanet.search.engine import _search_cached
        return _search_cached
    except ImportError:
        return None


@given(query=st.text(min_size=0, max_size=10000))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_fallback_search_never_crashes(query):
    """Fallback search should never crash, regardless of input."""
    search = _get_fallback_search()
    try:
        result = search(query)
        assert result is None or isinstance(result, list)
    except Exception as e:
        # Should not raise
        pytest.fail(f"Search crashed on input {repr(query[:100])}: {e}")


@given(query=st.text(alphabet=st.characters(blacklist_categories=("Cs",))))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_fallback_search_handles_unicode(query):
    """Fallback search handles all unicode without error."""
    search = _get_fallback_search()
    try:
        result = search(query)
        assert result is None or isinstance(result, list)
    except Exception as e:
        pytest.fail(f"Search crashed on unicode input: {e}")


@given(
    query=st.text(min_size=0, max_size=1000),
    domain=st.one_of(st.none(), st.text(min_size=0, max_size=100)),
    top=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_fallback_search_with_params(query, domain, top):
    """Fallback search handles all parameter combinations."""
    search = _get_fallback_search()
    try:
        result = search(query, domain=domain, top=top)
        assert result is None or isinstance(result, list)
    except Exception as e:
        pytest.fail(f"Search crashed with params: {e}")


@given(query=st.from_regex(r"[a-zA-Z0-9\s]{1,100}", fullmatch=True))
@settings(max_examples=50)
def test_fallback_search_normal_queries(query):
    """Normal alphanumeric queries should work."""
    search = _get_fallback_search()
    result = search(query)
    assert result is None or isinstance(result, list)


@given(query=st.sampled_from([
    "",
    " ",
    "\n",
    "\t",
    "\x00",
    "a" * 10000,
    "SELECT * FROM lessons",
    "<script>alert(1)</script>",
    "../../etc/passwd",
    "'; DROP TABLE lessons; --",
    "🔥" * 100,
    "\x00\x01\x02\x03",
]))
@settings(max_examples=20)
def test_fallback_search_edge_cases(query):
    """Edge case queries should not crash."""
    search = _get_fallback_search()
    try:
        result = search(query)
        assert result is None or isinstance(result, list)
    except Exception as e:
        pytest.fail(f"Search crashed on edge case {repr(query[:50])}: {e}")


if __name__ == "__main__":
    if HAS_HYPOTHESIS:
        test_fallback_search_never_crashes()
        test_fallback_search_handles_unicode()
        test_fallback_search_with_params()
        test_fallback_search_normal_queries()
        test_fallback_search_edge_cases()
        print("All fuzz tests passed ✓")
    else:
        print("hypothesis not installed, skipping fuzz tests")
