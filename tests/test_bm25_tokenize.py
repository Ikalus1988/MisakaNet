import sys
import unittest
from pathlib import Path

# Add project root to sys.path so we can import from misakanet
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from misakanet.search.engine import _tokenize


class TestBM25Tokenize(unittest.TestCase):
    """Edge case unit tests for BM25 keyword parsing (_tokenize function)."""

    def test_empty_string(self):
        """Empty string should return empty list."""
        self.assertEqual(_tokenize(""), [])

    def test_only_whitespace(self):
        """Only whitespace should return empty list."""
        self.assertEqual(_tokenize("   "), [])
        self.assertEqual(_tokenize("\t\n\r"), [])
        self.assertEqual(_tokenize(" \t \n "), [])

    def test_only_punctuation(self):
        """Only punctuation/special chars should return empty list."""
        self.assertEqual(_tokenize("!@#$%^&*()"), [])
        self.assertEqual(_tokenize(".,;:!?"), [])
        self.assertEqual(_tokenize("---"), [])
        self.assertEqual(_tokenize("..."), [])

    def test_simple_english_words(self):
        """Simple English words should be tokenized and lowercased."""
        self.assertEqual(_tokenize("hello world"), ["hello", "world"])
        self.assertEqual(_tokenize("Hello World"), ["hello", "world"])
        self.assertEqual(_tokenize("HELLO WORLD"), ["hello", "world"])

    def test_mixed_case_lowercased(self):
        """Mixed case should be lowercased."""
        self.assertEqual(_tokenize("CaMeLcAsE"), ["camelcase"])
        self.assertEqual(_tokenize("MiXeD CaSe"), ["mixed", "case"])

    def test_numbers_kept_as_tokens(self):
        """Numbers should be kept as tokens."""
        self.assertEqual(_tokenize("version 2.0"), ["version", "2", "0"])
        self.assertEqual(_tokenize("error 404"), ["error", "404"])
        self.assertEqual(_tokenize("2024-01-15"), ["2024", "01", "15"])

    def test_hyphenated_words_split(self):
        """Hyphens are replaced with spaces, so hyphenated words split."""
        self.assertEqual(_tokenize("well-known"), ["well", "known"])
        self.assertEqual(_tokenize("state-of-the-art"), ["state", "of", "the", "art"])
        self.assertEqual(_tokenize("pre-process"), ["pre", "process"])

    def test_underscores_kept(self):
        """Underscores are word characters, so they're kept."""
        self.assertEqual(_tokenize("variable_name"), ["variable_name"])
        self.assertEqual(_tokenize("snake_case_example"), ["snake_case_example"])
        self.assertEqual(_tokenize("a_b c_d"), ["a_b", "c_d"])

    def test_chinese_characters_split_individually(self):
        """Chinese characters should be split into individual characters."""
        self.assertEqual(_tokenize("中文"), ["中", "文"])
        self.assertEqual(_tokenize("测试"), ["测", "试"])
        self.assertEqual(_tokenize("你好世界"), ["你", "好", "世", "界"])

    def test_mixed_english_and_chinese(self):
        """Mixed English and Chinese: English words kept whole, Chinese split."""
        self.assertEqual(_tokenize("hello 中文 world"), ["hello", "中", "文", "world"])
        self.assertEqual(_tokenize("RAG 检索"), ["rag", "检", "索"])
        self.assertEqual(_tokenize("BM25 关键词 搜索"), ["bm25", "关", "键", "词", "搜", "索"])

    def test_emojis_and_symbols_removed(self):
        """Emojis and symbols should be removed (replaced with space)."""
        self.assertEqual(_tokenize("hello 😊 world"), ["hello", "world"])
        self.assertEqual(_tokenize("test 🔥🚀"), ["test"])
        self.assertEqual(_tokenize("😀😃😄"), [])

    def test_multiple_spaces_collapsed(self):
        """Multiple consecutive spaces should be collapsed."""
        self.assertEqual(_tokenize("hello    world"), ["hello", "world"])
        self.assertEqual(_tokenize("hello\tworld"), ["hello", "world"])
        self.assertEqual(_tokenize("hello\nworld"), ["hello", "world"])
        self.assertEqual(_tokenize("hello \t \n world"), ["hello", "world"])

    def test_leading_trailing_whitespace_trimmed(self):
        """Leading and trailing whitespace should be ignored."""
        self.assertEqual(_tokenize("  hello world  "), ["hello", "world"])
        self.assertEqual(_tokenize("\nhello\n"), ["hello"])
        self.assertEqual(_tokenize("\thello\t"), ["hello"])

    def test_very_long_query(self):
        """Very long queries should be handled without error."""
        long_query = "word " * 1000  # 4000+ characters
        tokens = _tokenize(long_query)
        self.assertEqual(len(tokens), 1000)
        self.assertTrue(all(t == "word" for t in tokens))

    def test_special_regex_characters_in_input(self):
        """Special regex characters in input should be handled safely."""
        self.assertEqual(_tokenize("test (parentheses)"), ["test", "parentheses"])
        self.assertEqual(_tokenize("path/to/file"), ["path", "to", "file"])
        self.assertEqual(_tokenize("a+b=c"), ["a", "b", "c"])
        self.assertEqual(_tokenize("var[0]"), ["var", "0"])
        self.assertEqual(_tokenize("regex.*"), ["regex"])

    def test_alphanumeric_mixed_tokens(self):
        """Alphanumeric mixed tokens should be kept as single tokens."""
        self.assertEqual(_tokenize("var123"), ["var123"])
        self.assertEqual(_tokenize("test123abc"), ["test123abc"])
        self.assertEqual(_tokenize("v2.0"), ["v2", "0"])  # dot replaced with space

    def test_cjk_punctuation_handling(self):
        """CJK punctuation should be replaced with spaces."""
        self.assertEqual(_tokenize("你好，世界"), ["你", "好", "世", "界"])
        self.assertEqual(_tokenize("测试。完成"), ["测", "试", "完", "成"])
        self.assertEqual(_tokenize("标题：《测试》"), ["标", "题", "测", "试"])

    def test_japanese_korean_characters(self):
        """Japanese Hiragana/Katakana and Korean Hangul ARE word chars in Unicode, so kept as whole tokens."""
        # These match \w in Python regex, so they're NOT replaced and kept as single tokens
        # (unlike Chinese which are split into individual chars)
        self.assertEqual(_tokenize("こんにちは"), ["こんにちは"])  # Hiragana
        self.assertEqual(_tokenize("カタカナ"), ["カタカナ"])  # Katakana
        self.assertEqual(_tokenize("한글"), ["한글"])          # Hangul
        self.assertEqual(_tokenize("hello こんにちは world"), ["hello", "こんにちは", "world"])

    def test_mixed_chinese_english_with_punctuation(self):
        """Mixed Chinese/English with punctuation should handle correctly."""
        self.assertEqual(_tokenize("RAG (Retrieval-Augmented Generation) 检索"), 
                         ["rag", "retrieval", "augmented", "generation", "检", "索"])
        self.assertEqual(_tokenize("BM25+语义搜索"), ["bm25", "语", "义", "搜", "索"])

    def test_single_character_tokens(self):
        """Single characters should work."""
        self.assertEqual(_tokenize("a"), ["a"])
        self.assertEqual(_tokenize("我"), ["我"])
        self.assertEqual(_tokenize("1"), ["1"])

    def test_newlines_and_tabs_in_middle(self):
        """Newlines and tabs in middle of text should act as separators."""
        self.assertEqual(_tokenize("line1\nline2"), ["line1", "line2"])
        self.assertEqual(_tokenize("col1\tcol2"), ["col1", "col2"])
        self.assertEqual(_tokenize("a\n\tb"), ["a", "b"])

    def test_return_type_is_list_of_strings(self):
        """Return type should always be list of strings."""
        result = _tokenize("test")
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(t, str) for t in result))

    def test_no_none_return(self):
        """Should never return None."""
        self.assertIsNotNone(_tokenize(""))
        self.assertIsNotNone(_tokenize("!@#"))
        self.assertIsNotNone(_tokenize("hello"))


if __name__ == "__main__":
    unittest.main()
