"""Tests for BM25 keyword parsing edge cases in search_knowledge engine.

Extended with additional edge cases from Issue #169:
- Consecutive spaces
- Emojis
- Punctuation (e.g., `pip    install !!! 🚀`)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from misakanet.search.engine import _tokenize, _compute_bm25_scores, CachedDoc


# ── Existing tests (preserved) ──

def test_tokenize_empty_query():
    tokens = _tokenize("")
    assert tokens == []

def test_tokenize_whitespace_only():
    tokens = _tokenize("   \n\t  ")
    assert tokens == []

def test_tokenize_special_characters():
    tokens = _tokenize("hello@world!#$%^&*()")
    assert "hello" in tokens
    assert "world" in tokens

def test_tokenize_chinese_characters():
    tokens = _tokenize("测试中文")
    assert "测" in tokens
    assert "试" in tokens
    assert "中" in tokens
    assert "文" in tokens

def test_tokenize_mixed_english_chinese():
    tokens = _tokenize("hello 测试 world")
    assert "hello" in tokens
    assert "world" in tokens
    assert "测" in tokens
    assert "试" in tokens

def test_tokenize_single_word():
    tokens = _tokenize("python")
    assert tokens == ["python"]

def test_tokenize_single_word_uppercase():
    tokens = _tokenize("PYTHON")
    assert tokens == ["python"]

def test_tokenize_long_query_over_500_chars():
    long_query = "a " * 300
    tokens = _tokenize(long_query)
    assert len(tokens) == 300
    assert all(t == "a" for t in tokens)

def test_tokenize_very_long_query_1000_chars():
    long_query = "test " * 250
    tokens = _tokenize(long_query)
    assert len(tokens) == 250

def test_tokenize_unicode_special_chars():
    tokens = _tokenize("café naïve résumé 🎉")
    assert "café" in tokens
    assert "naïve" in tokens
    assert "résumé" in tokens

def test_tokenize_numbers_and_symbols():
    tokens = _tokenize("version 2.0.1 beta-test_123")
    assert "version" in tokens
    assert "2" in tokens
    assert "0" in tokens
    assert "1" in tokens
    assert "beta" in tokens
    assert "test_123" in tokens

def test_compute_bm25_scores_empty_query():
    docs = [
        CachedDoc(filename="test1.md", filepath=Path("test1.md"), content="test content", title="Test"),
        CachedDoc(filename="test2.md", filepath=Path("test2.md"), content="another document", title="Another"),
    ]
    scores = _compute_bm25_scores("", docs)
    assert all(score == 0.0 for score in scores)

def test_compute_bm25_scores_no_match():
    docs = [
        CachedDoc(filename="test1.md", filepath=Path("test1.md"), content="python programming", title="Python"),
        CachedDoc(filename="test2.md", filepath=Path("test2.md"), content="java development", title="Java"),
    ]
    scores = _compute_bm25_scores("javascript", docs)
    assert all(score == 0.0 for score in scores)

def test_compute_bm25_scores_partial_match():
    docs = [
        CachedDoc(filename="test1.md", filepath=Path("test1.md"), content="python programming tutorial", title="Python"),
        CachedDoc(filename="test2.md", filepath=Path("test2.md"), content="java development guide", title="Java"),
    ]
    scores = _compute_bm25_scores("python", docs)
    assert scores[0] > scores[1]

def test_compute_bm25_scores_single_doc():
    docs = [
        CachedDoc(filename="test1.md", filepath=Path("test1.md"), content="single doc content", title="Single"),
    ]
    scores = _compute_bm25_scores("content", docs)
    assert len(scores) == 1
    assert scores[0] > 0


# ── New edge case tests (Issue #169) ──

def test_tokenize_consecutive_spaces():
    """Consecutive spaces should be collapsed into single delimiter."""
    tokens = _tokenize("pip    install    package")
    assert tokens == ["pip", "install", "package"]

def test_tokenize_tabs_and_newlines():
    """Tabs and newlines should act as delimiters."""
    tokens = _tokenize("pip\tinstall\npackage")
    assert tokens == ["pip", "install", "package"]

def test_tokenize_emoji_only():
    """Emoji-only query should not crash."""
    tokens = _tokenize("🚀🎉💡")
    # Emojis may be stripped or tokenized - should not crash
    assert isinstance(tokens, list)

def test_tokenize_emoji_with_text():
    """Emojis mixed with text should not crash."""
    tokens = _tokenize("pip install 🚀")
    assert "pip" in tokens
    assert "install" in tokens

def test_tokenize_exclamation_marks():
    """Multiple exclamation marks should be handled."""
    tokens = _tokenize("hello!!! world")
    assert "hello" in tokens
    assert "world" in tokens

def test_tokenize_question_marks():
    """Question marks should be stripped."""
    tokens = _tokenize("what is python???")
    assert "what" in tokens
    assert "is" in tokens
    assert "python" in tokens

def test_tokenize_mixed_punctuation():
    """Mixed punctuation should be stripped."""
    tokens = _tokenize("pip... install!!! package???")
    assert "pip" in tokens
    assert "install" in tokens
    assert "package" in tokens

def test_tokenize_real_world_messy_query():
    """Real-world messy query from Issue #169."""
    tokens = _tokenize("pip    install !!! 🚀")
    assert "pip" in tokens
    assert "install" in tokens
    # Should not crash, emojis/punctuation handled gracefully

def test_tokenize_html_tags():
    """HTML tags should be stripped or handled."""
    tokens = _tokenize("<b>bold</b> text")
    assert "bold" in tokens or "b" in tokens
    assert "text" in tokens

def test_tokenize_markdown_syntax():
    """Markdown syntax should be handled."""
    tokens = _tokenize("**bold** _italic_ `code`")
    assert "bold" in tokens
    assert "italic" in tokens
    assert "code" in tokens

def test_tokenize_urls():
    """URLs should be tokenized into components."""
    tokens = _tokenize("visit https://example.com/path")
    assert "visit" in tokens
    # URL components may be split

def test_tokenize_file_paths():
    """File paths should be handled."""
    tokens = _tokenize("/usr/local/bin/python")
    assert "usr" in tokens or "python" in tokens

def test_compute_bm25_scores_consecutive_spaces():
    """BM25 should work with consecutive spaces in query."""
    docs = [
        CachedDoc(filename="test.md", filepath=Path("test.md"), content="pip install package", title="Test"),
    ]
    scores = _compute_bm25_scores("pip    install", docs)
    assert scores[0] > 0

def test_compute_bm25_scores_emoji_query():
    """BM25 should not crash on emoji queries."""
    docs = [
        CachedDoc(filename="test.md", filepath=Path("test.md"), content="test content", title="Test"),
    ]
    scores = _compute_bm25_scores("🚀 test", docs)
    assert len(scores) == 1


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
