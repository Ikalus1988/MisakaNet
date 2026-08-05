import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import misaka_search_json


class TestMisakaSearchJson(unittest.TestCase):
    def test_make_snippet_prefers_query_match(self):
        content = "---\ntitle: Example\n---\n" + "prefix " * 40 + "sqlite database locked fix " + "suffix " * 40

        snippet = misaka_search_json.make_snippet(content, "database locked", max_chars=120)

        self.assertIn("database locked", snippet)
        self.assertLessEqual(len(snippet), 122)  # allow leading/trailing ellipses

    def test_search_returns_title_score_path_and_snippet(self):
        results = misaka_search_json.search("pip install", top=2, include_reference=False)

        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIsInstance(result["title"], str)
            self.assertIsInstance(result["score"], float)
            self.assertIsInstance(result["path"], str)
            self.assertIsInstance(result["snippet"], str)
            self.assertTrue(result["title"])
            self.assertTrue(result["path"].startswith("lessons/"))
            self.assertTrue(result["snippet"])

    def test_main_emits_parseable_json(self):
        # Exercise the CLI code path with a small top-k and parse the same payload
        # Continue consumes from stdout.
        import io
        import contextlib

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = misaka_search_json.main(["pip install", "--top", "1", "--lessons-only"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["query"], "pip install")
        self.assertEqual(payload["top"], 1)
        self.assertEqual(len(payload["results"]), 1)
        self.assertIn("title", payload["results"][0])
        self.assertIn("score", payload["results"][0])
        self.assertIn("snippet", payload["results"][0])


if __name__ == "__main__":
    unittest.main()
