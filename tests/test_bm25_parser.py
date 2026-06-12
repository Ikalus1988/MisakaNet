import unittest
from misakanet.search import bm25_parser

class TestBM25Parser(unittest.TestCase):
    def test_consecutive_spaces(self):
        query = "pip    install"
        expected = ["pip", "install"]
        self.assertEqual(bm25_parser.parse_query(query), expected)

    def test_emojis(self):
        query = "🚀 install pip"
        expected = ["install", "pip"]
        self.assertEqual(bm25_parser.parse_query(query), expected)

    def test_punctuation(self):
        query = "pip !!! install"
        expected = ["pip", "install"]
        self.assertEqual(bm25_parser.parse_query(query), expected)

    def test_mixed_input(self):
        query = "pip    !!! 🚀 install"
        expected = ["pip", "install"]
        self.assertEqual(bm25_parser.parse_query(query), expected)

if __name__ == "__main__":
    unittest.main()