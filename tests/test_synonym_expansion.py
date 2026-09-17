#!/usr/bin/env python3
"""Tests for domain synonym query expansion.

Feature #532's hard-coded `_SYNONYM_MAP` was unified into data/query-aliases.json in
#1780: the map and `_expand_query` are now a *view of* that file, and the expansion
itself is `scripts/expand_query.py::expand` (the same implementation the Worker runs).
These tests are kept as the behaviour contract for the callers of `_expand_query` —
they still pass unchanged except for `test_expand_mcp`, where the output is now a
token string (BM25 tokens) rather than the raw canonical `tools/list`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from misakanet.search.engine import _SYNONYM_MAP, _expand_query


class TestSynonymExpansion:
    def test_expand_mcp(self):
        result = _expand_query("mcp tool not showing")
        assert "setup" in result
        # `tools/list` is the canonical in the table; expansion emits its BM25 tokens
        # (`expand_query.tokenize("tools/list") == ["tools", "list"]`), because what
        # reaches the scorer is a token string — before #1780 this assertion only passed
        # because the old map appended the raw string.
        assert "tools" in result and "list" in result

    def test_expand_gbk(self):
        result = _expand_query("gbk error")
        assert "unicode" in result
        assert "encoding" in result

    def test_expand_dco(self):
        result = _expand_query("dco fail")
        assert "signoff" in result

    def test_expand_pip(self):
        result = _expand_query("pip timeout")
        assert "ssl" in result
        assert "proxy" in result

    def test_unmapped_query_unchanged(self):
        original = "database locked"
        result = _expand_query(original)
        assert result == original

    def test_no_duplicate_synonyms(self):
        result = _expand_query("dco")
        tokens = result.split()
        assert len(tokens) == len(set(tokens))

    def test_synonym_map_is_dict(self):
        assert isinstance(_SYNONYM_MAP, dict)

    def test_common_terms_have_synonyms(self):
        for term in ["mcp", "gbk", "dco", "pip", "git", "auth", "cron", "wsl"]:
            assert term in _SYNONYM_MAP, f"Missing synonym entry for {term}"
