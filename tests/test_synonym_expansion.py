#!/usr/bin/env python3
"""Tests for domain synonym query expansion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from misakanet.search.engine import _SYNONYM_MAP, _expand_query


class TestSynonymExpansion:
    def test_expand_mcp(self):
        result = _expand_query("mcp tool not showing")
        assert "setup" in result
        assert "tools/list" in result

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
