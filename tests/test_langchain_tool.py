import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from misakanet.tools.langchain_tool import MisakaNetSearchTool


class TestMisakaNetSearchTool(unittest.TestCase):
    def test_cache_hit_and_expired_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "search.db"
            tool = MisakaNetSearchTool(cache_path=cache_path)
            tool._execute_search = Mock(return_value="fresh result")

            self.assertEqual(tool._run("cache me"), "fresh result")
            self.assertEqual(tool._run("cache me"), "fresh result")
            self.assertEqual(tool._execute_search.call_count, 1)

            with sqlite3.connect(cache_path) as conn:
                conn.execute(
                    "UPDATE langchain_search_cache SET created_at = ?",
                    (time.time() - tool.cache_ttl_seconds - 1,),
                )

            tool._execute_search.return_value = "expired result"
            self.assertEqual(tool._run("cache me"), "expired result")
            self.assertEqual(tool._execute_search.call_count, 2)

    def test_rrf_merges_multi_query_rankings(self):
        tool = MisakaNetSearchTool(cache_path=Path(tempfile.gettempdir()) / "unused-misakanet.db")
        doc_a = SimpleNamespace(filename="a.md", filepath=Path("a.md"))
        doc_b = SimpleNamespace(filename="b.md", filepath=Path("b.md"))
        doc_c = SimpleNamespace(filename="c.md", filepath=Path("c.md"))

        rankings = {
            "cache invalidation bug": [(0.9, doc_a), (0.5, doc_b)],
            "cache invalidation bug solution": [(0.7, doc_b), (0.4, doc_c)],
            "cache invalidation bug troubleshooting": [(0.8, doc_c), (0.3, doc_b)],
        }

        def ranker(subquery, docs):
            return rankings[subquery]

        tool._expand_query = Mock(
            return_value=[
                "cache invalidation bug",
                "cache invalidation bug solution",
                "cache invalidation bug troubleshooting",
            ]
        )

        ranked = tool._rank_with_rrf("cache invalidation bug", [doc_a, doc_b, doc_c], ranker)

        self.assertEqual(ranked[0][1], doc_b)
        self.assertEqual({doc.filename for _, doc in ranked}, {"a.md", "b.md", "c.md"})

    def test_expand_query_returns_three_distinct_queries(self):
        tool = MisakaNetSearchTool(cache_path=Path(tempfile.gettempdir()) / "unused-misakanet.db")

        expanded = tool._expand_query("async cache async cache")

        self.assertEqual(len(expanded), 3)
        self.assertEqual(len(set(expanded)), 3)
        self.assertEqual(expanded[0], "async cache async cache")

    def test_arun_uses_thread_offload(self):
        tool = MisakaNetSearchTool(cache_path=Path(tempfile.gettempdir()) / "unused-misakanet.db")

        async def run():
            with patch(
                "misakanet.tools.langchain_tool.asyncio.to_thread",
                new=AsyncMock(return_value="async result"),
            ) as to_thread:
                result = await tool._arun("async query")
                to_thread.assert_awaited_once_with(tool._run, "async query")
                return result

        self.assertEqual(asyncio.run(run()), "async result")


if __name__ == "__main__":
    unittest.main()
