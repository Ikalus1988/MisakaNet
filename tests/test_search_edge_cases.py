"""Edge-case unit tests for BM25 keyword parsing logic.

Issue: https://github.com/Ikalus1988/MisakaNet/issues/192
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "MisakaNet"))

try:
    from misakanet.search.engine import _tokenize, _compute_bm25_scores
    from misakanet.search.engine import CachedDoc
except ImportError:
    from search_knowledge import _tokenize, _compute_bm25_scores
    from search_knowledge import CachedDoc


def _make_doc(content: str, title: str = "test") -> CachedDoc:
    return CachedDoc(
        filename=f"{title}.md",
        filepath=None,
        content=content,
        title=title,
        domain="test",
        status="published",
    )


class TestTokenizeEdgeCases(unittest.TestCase):

    def test_empty_query(self):
        self.assertEqual(_tokenize(""), [])

    def test_only_whitespace(self):
        self.assertEqual(_tokenize("   "), [])

    def test_only_special_chars(self):
        self.assertEqual(_tokenize("!!! @@@ ### $$$"), [])

    def test_only_emoji(self):
        self.assertEqual(_tokenize("🚀🎯🔥"), [])

    def test_consecutive_spaces(self):
        result = _tokenize("pip    install    timeout")
        self.assertEqual(result, ["pip", "install", "timeout"])

    def test_punctuation_around_words(self):
        result = _tokenize("pip install !!! 🚀")
        self.assertEqual(result, ["pip", "install"])

    def test_mixed_cjk_and_latin(self):
        result = _tokenize("python 安装 pip")
        self.assertIn("python", result)
        self.assertIn("pip", result)
        self.assertTrue(any('\u4e00' <= c <= '\u9fff' for c in result))

    def test_single_word(self):
        result = _tokenize("pip")
        self.assertEqual(result, ["pip"])

    def test_extremely_long_query(self):
        long_query = "pip " * 300
        result = _tokenize(long_query)
        self.assertEqual(len(result), 300)
        self.assertTrue(all(t == "pip" for t in result))

    def test_url_in_query(self):
        result = _tokenize("how to fix https://github.com/error")
        self.assertIn("how", result)
        self.assertIn("fix", result)
        self.assertIn("https", result)
        self.assertIn("github", result)

    def test_numbers_and_symbols(self):
        result = _tokenize("error code 404 not_found")
        self.assertIn("error", result)
        self.assertIn("code", result)
        self.assertIn("404", result)
        self.assertIn("not_found", result)

    def test_case_insensitivity(self):
        result_upper = _tokenize("PIP INSTALL TIMEOUT")
        result_lower = _tokenize("pip install timeout")
        self.assertEqual(result_upper, result_lower)

    def test_newlines_and_tabs(self):
        result = _tokenize("pip\ninstall\ttimeout")
        self.assertEqual(result, ["pip", "install", "timeout"])

    def test_leading_trailing_whitespace(self):
        result = _tokenize("  pip install timeout  ")
        self.assertEqual(result, ["pip", "install", "timeout"])


class TestBM25EdgeCases(unittest.TestCase):

    def test_single_word_match(self):
        docs = [_make_doc("pip install timeout on windows")]
        scores = _compute_bm25_scores("pip", docs)
        self.assertEqual(len(scores), 1)
        self.assertGreater(scores[0], 0)

    def test_no_match_returns_zero(self):
        docs = [_make_doc("something completely unrelated")]
        scores = _compute_bm25_scores("pip", docs)
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0], 0.0)

    def test_empty_query_all_zero(self):
        docs = [_make_doc("pip install timeout")]
        scores = _compute_bm25_scores("", docs)
        self.assertEqual(scores, [0.0])

    def test_empty_docs(self):
        scores = _compute_bm25_scores("pip", [])
        self.assertEqual(scores, [])

    def test_partial_word_match(self):
        docs = [_make_doc("pip install pipenv")]
        scores = _compute_bm25_scores("pip", docs)
        self.assertGreater(scores[0], 0)

    def test_special_chars_in_docs(self):
        docs = [_make_doc("pip install !!! 🚀 timeout")]
        scores = _compute_bm25_scores("pip timeout", docs)
        self.assertGreater(scores[0], 0)

    def test_multi_word_query_ordering_stable(self):
        docs = [
            _make_doc("pip install timeout fix"),
            _make_doc("install timeout common"),
            _make_doc("pip common tool"),
        ]
        scores = _compute_bm25_scores("pip install timeout", docs)
        self.assertEqual(len(scores), 3)

    def test_very_long_doc_content(self):
        docs = [_make_doc("pip " * 10000)]
        scores = _compute_bm25_scores("pip", docs)
        self.assertGreater(scores[0], 0)

    def test_query_with_only_special_chars(self):
        docs = [_make_doc("pip install timeout")]
        scores = _compute_bm25_scores("!!! 🚀 @@@", docs)
        self.assertEqual(scores, [0.0])


class TestCJKEdgeCases(unittest.TestCase):

    def test_chinese_query_tokenization(self):
        result = _tokenize("安装 pip 超时")
        self.assertIn("pip", result)
        self.assertIn("装", result)
        self.assertIn("时", result)

    def test_mixed_chinese_english_punctuation(self):
        result = _tokenize("pip安装超时!")
        self.assertIn("p", result)
        self.assertIn("装", result)
        self.assertIn("时", result)

    def test_japanese_characters(self):
        result = _tokenize("pip インストール タイムアウト")
        self.assertIn("pip", result)


if __name__ == "__main__":
    unittest.main()
