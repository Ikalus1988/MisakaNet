import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from misakanet.tools import langchain_tool as tool_module


def _doc(name, title=None):
    return SimpleNamespace(
        filename=name,
        filepath=Path(name),
        title=title or name,
        domain="test",
        content=f"{title or name} body",
        status="published",
        reference="",
        is_lesson=True,
    )


class TestLangChainTool(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.original_db = tool_module._CACHE_DB
        self.original_ttl = tool_module._CACHE_TTL_SECONDS
        tool_module._CACHE_DB = Path(self.tmpdir.name) / "tool-cache.db"
        tool_module._CACHE_TTL_SECONDS = 300
        self.addCleanup(self._restore_cache_settings)

    def _restore_cache_settings(self):
        tool_module._CACHE_DB = self.original_db
        tool_module._CACHE_TTL_SECONDS = self.original_ttl

    def test_cache_hit_and_expired_miss(self):
        doc = _doc("cache.md", "Cache result")
        calls = {"rank": 0}

        def fake_rank(_query, _docs):
            calls["rank"] += 1
            return [(1.0, doc)]

        search_tool = tool_module.MisakaNetSearchTool()
        with patch.object(tool_module, "_load_search_docs", return_value=[doc]), patch.object(
            tool_module, "_rank_subquery", side_effect=fake_rank
        ):
            first = search_tool._run("cache query")
            second = search_tool._run("cache query")

            self.assertEqual(first, second)
            self.assertEqual(calls["rank"], 3)

            with sqlite3.connect(tool_module._CACHE_DB) as conn:
                conn.execute("UPDATE search_cache SET created_at = ?", (time.time() - 301,))

            third = search_tool._run("cache query")
            self.assertEqual(third, first)
            self.assertEqual(calls["rank"], 6)

    def test_rrf_prefers_consistently_high_ranked_docs(self):
        doc_a = _doc("a.md")
        doc_b = _doc("b.md")
        doc_c = _doc("c.md")

        merged = tool_module._rrf_merge(
            [
                [(10.0, doc_a), (9.0, doc_b)],
                [(10.0, doc_b), (9.0, doc_a)],
                [(10.0, doc_b), (9.0, doc_c)],
            ]
        )

        self.assertEqual(merged[0][1].filename, "b.md")
        self.assertEqual([doc.filename for _score, doc in merged], ["b.md", "a.md", "c.md"])

    def test_arun_does_not_block_event_loop(self):
        search_tool = tool_module.MisakaNetSearchTool()
        ticks = []

        def slow_run(_self, _query):
            time.sleep(0.2)
            return "ok"

        async def marker():
            await asyncio.sleep(0.02)
            ticks.append(time.perf_counter())

        async def scenario():
            start = time.perf_counter()
            with patch.object(tool_module.MisakaNetSearchTool, "_run", slow_run):
                result, _ = await asyncio.gather(search_tool._arun("async query"), marker())
            return result, ticks[0] - start

        result, tick_elapsed = asyncio.run(scenario())

        self.assertEqual(result, "ok")
        self.assertLess(tick_elapsed, 0.16)


if __name__ == "__main__":
    unittest.main()
