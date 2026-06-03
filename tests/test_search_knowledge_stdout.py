import io
import unittest
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


if __name__ == "__main__":
    unittest.main()
