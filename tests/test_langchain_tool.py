import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from misakanet.tools.langchain_tool import MisakaNetSearchTool


class TestMisakaNetSearchTool(unittest.TestCase):
    def test_cache_hit_and_expired_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "search.db"
            telemetry_path = Path(tmp) / "telemetry.db"
            tool = MisakaNetSearchTool(cache_path=cache_path, telemetry_path=telemetry_path)
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

    def test_telemetry_summary_reports_cache_hit_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "search.db"
            telemetry_path = Path(tmp) / "telemetry.db"
            tool = MisakaNetSearchTool(cache_path=cache_path, telemetry_path=telemetry_path)
            tool._execute_search = Mock(side_effect=lambda query: f"fresh result: {query}")

            self.assertEqual(tool._run("cache me"), "fresh result: cache me")
            self.assertEqual(tool._run("cache me"), "fresh result: cache me")
            self.assertEqual(tool._run("cache other"), "fresh result: cache other")

            summary = tool.get_telemetry_summary()

            self.assertEqual(summary["total_searches"], 3)
            self.assertAlmostEqual(summary["cache_hit_rate"], 1 / 3)
            self.assertGreater(summary["avg_latency_ms"], 0)

    def test_telemetry_summary_calculates_saved_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry_path = Path(tmp) / "telemetry.db"
            tool = MisakaNetSearchTool(
                cache_path=Path(tmp) / "search.db",
                telemetry_path=telemetry_path,
            )

            self.assertEqual(tool.get_telemetry_summary()["saved_time_ms"], 0)

            with tool._telemetry_connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO search_telemetry
                        (query, timestamp, latency_ms, cache_hit)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        ("hit one", 1.0, 10.0, 1),
                        ("hit two", 2.0, 20.0, 1),
                        ("miss one", 3.0, 100.0, 0),
                        ("miss two", 4.0, 120.0, 0),
                    ],
                )

            summary = tool.get_telemetry_summary()

            self.assertEqual(summary["total_searches"], 4)
            self.assertAlmostEqual(summary["cache_hit_rate"], 0.5)
            self.assertAlmostEqual(summary["avg_latency_ms"], 62.5)
            self.assertAlmostEqual(summary["saved_time_ms"], 190.0)

    def test_repeated_query_signature_short_circuits_without_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "search.db"
            telemetry_path = Path(tmp) / "telemetry.db"
            tool = MisakaNetSearchTool(cache_path=cache_path, telemetry_path=telemetry_path)
            tool._execute_search = Mock(return_value="should not run")
            now = time.time()
            signature = tool._query_signature(" repeated query ", 0.0)

            with tool._telemetry_connection() as conn:
                for i in range(5):
                    conn.execute(
                        """
                        INSERT INTO search_telemetry
                            (query, timestamp, latency_ms, cache_hit, query_signature)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        ("Repeated Query", now - i, 10.0, 0, signature),
                    )

            result = tool._run("REPEATED QUERY")

            self.assertEqual(result, "[Rate Limited] Repeated query pattern detected.")
            tool._execute_search.assert_not_called()
            with tool._telemetry_connection() as conn:
                count = conn.execute("SELECT COUNT(*) FROM search_telemetry").fetchone()[0]
            self.assertEqual(count, 5)

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

    def test_rrf_uses_rank_and_filename_tiebreakers(self):
        tool = MisakaNetSearchTool(cache_path=Path(tempfile.gettempdir()) / "unused-misakanet.db")
        doc_a = SimpleNamespace(filename="a.md", filepath=Path("a.md"))
        doc_b = SimpleNamespace(filename="b.md", filepath=Path("b.md"))
        doc_c = SimpleNamespace(filename="c.md", filepath=Path("c.md"))

        rankings = {
            "query one": [(0.9, doc_b), (0.8, doc_a), (0.7, doc_c)],
            "query two": [(0.6, doc_c), (0.5, doc_a), (0.4, doc_b)],
        }

        def ranker(subquery, docs):
            return rankings[subquery]

        tool._expand_query = Mock(return_value=["query one", "query two"])

        ranked = tool._rank_with_rrf("query", [doc_a, doc_b, doc_c], ranker)

        self.assertEqual([doc.filename for _, doc in ranked], ["b.md", "c.md", "a.md"])

    def test_expand_query_returns_three_distinct_queries(self):
        tool = MisakaNetSearchTool(cache_path=Path(tempfile.gettempdir()) / "unused-misakanet.db")

        expanded = tool._expand_query("async cache async cache")

        self.assertEqual(len(expanded), 3)
        self.assertEqual(len(set(expanded)), 3)
        self.assertEqual(expanded[0], "async cache async cache")

    def test_arun_runs_blocking_work_concurrently(self):
        tool = MisakaNetSearchTool(cache_path=Path(tempfile.gettempdir()) / "unused-misakanet.db")

        async def run():
            def slow_run(query):
                time.sleep(0.2)
                return f"async result: {query}"

            tool._run = slow_run
            started = time.perf_counter()
            results = await asyncio.gather(
                tool._arun("first query"),
                tool._arun("second query"),
            )
            elapsed = time.perf_counter() - started
            return results, elapsed

        results, elapsed = asyncio.run(run())

        self.assertEqual(
            results,
            ["async result: first query", "async result: second query"],
        )
        self.assertLess(elapsed, 0.35)


    def test_anti_abuse_rate_limit_trigger(self):
        """10 rapid queries within 1 second should trigger PermissionError."""
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "search.db"
            telemetry_path = Path(tmp) / "telemetry.db"
            tool = MisakaNetSearchTool(cache_path=cache_path, telemetry_path=telemetry_path)
            tool._execute_search = Mock(return_value="result")

            # Insert 9 rapid telemetry rows (within 1 second)
            now = time.time()
            with tool._telemetry_connection() as conn:
                for i in range(9):
                    conn.execute(
                        """
                        INSERT INTO search_telemetry (query, timestamp, latency_ms, cache_hit)
                        VALUES (?, ?, ?, ?)
                        """,
                        (f"rapid-{i}", now + i * 0.05, 10.0, 0),
                    )

            # 10th call records telemetry + triggers audit → blacklist entry created
            tool._run("rapid-9")

            # 11th call should raise PermissionError (blacklisted from audit)
            with self.assertRaises(PermissionError) as ctx:
                tool._run("trigger-block")
            self.assertIn("Anti-Abuse Shield", str(ctx.exception))

    def test_anti_abuse_low_quality_trigger(self):
        """10 continuous cache misses should trigger PermissionError."""
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "search.db"
            telemetry_path = Path(tmp) / "telemetry.db"
            tool = MisakaNetSearchTool(cache_path=cache_path, telemetry_path=telemetry_path)
            tool._execute_search = Mock(return_value="result")

            # Insert 9 cache-miss telemetry rows spread over 30 seconds
            now = time.time()
            with tool._telemetry_connection() as conn:
                for i in range(9):
                    conn.execute(
                        """
                        INSERT INTO search_telemetry (query, timestamp, latency_ms, cache_hit)
                        VALUES (?, ?, ?, ?)
                        """,
                        (f"miss-{i}", now + i * 3, 100.0, 0),
                    )

            # 10th call records telemetry (cache miss) + triggers audit → blacklist entry
            tool._run("miss-9")

            # 11th call should raise PermissionError (blacklisted from audit)
            with self.assertRaises(PermissionError) as ctx:
                tool._run("trigger-low-quality")
            self.assertIn("Anti-Abuse Shield", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
