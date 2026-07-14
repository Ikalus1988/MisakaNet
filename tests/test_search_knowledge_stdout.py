import io
import json
import unittest
from pathlib import Path
from unittest import mock

import search_knowledge


class ReconfigurableStdout(io.StringIO):
    def __init__(self):
        super().__init__()
        self.reconfigure_calls = []

    def reconfigure(self, **kwargs):
        self.reconfigure_calls.append(kwargs)


class TestSearchKnowledgeStdout(unittest.TestCase):
    def test_ensure_utf8_stdout_reconfigures_stream(self):
        stdout = ReconfigurableStdout()

        with mock.patch.object(search_knowledge.sys, "stdout", stdout):
            search_knowledge._ensure_utf8_stdout()

        self.assertEqual(
            stdout.reconfigure_calls,
            [{"encoding": "utf-8", "errors": "replace"}],
        )

    def test_ensure_utf8_stdout_ignores_unsupported_stream(self):
        stdout = io.StringIO()

        with mock.patch.object(search_knowledge.sys, "stdout", stdout):
            search_knowledge._ensure_utf8_stdout()

    def test_json_result_uses_required_schema(self):
        doc = mock.Mock(
            title="Database locked",
            domain="database",
            tags=["sqlite", "locking"],
            filepath=Path(search_knowledge.__file__).parent / "lessons" / "example.md",
            content="---\ntitle: Example\n---\n\nA useful preview.",
        )

        result = search_knowledge._json_result(0.12345678, doc)

        self.assertEqual(
            set(result), {"title", "domain", "tags", "score", "path", "preview"}
        )
        self.assertEqual(result["path"], "lessons/example.md")
        self.assertEqual(result["score"], 0.123457)

    def test_json_error_is_parseable(self):
        stdout = io.StringIO()
        with mock.patch.object(search_knowledge.sys, "stdout", stdout):
            search_knowledge._print_json_error("query failed")

        self.assertEqual(json.loads(stdout.getvalue()), {"error": "query failed"})


if __name__ == "__main__":
    unittest.main()
