"""Tests for TelemetryPipeline — async producer-consumer pipeline."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path

from misakanet.tools.telemetry_pipeline import (
    BATCH_SIZE,
    QUEUE_MAXSIZE,
    TelemetryPipeline,
    _ensure_schema,
)


def _count_rows(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM search_telemetry").fetchone()[0]
        return count
    finally:
        conn.close()


def _get_all_rows(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT query, latency_ms, cache_hit FROM search_telemetry ORDER BY timestamp"
        ).fetchall()
        return rows
    finally:
        conn.close()


class TestTelemetryPipeline(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test_telemetry.db"

    async def asyncTearDown(self):
        pass  # tmpdir cleaned up by OS

    async def test_emit_and_batch_flush(self):
        """Emit events and verify they're flushed to DB."""
        async with TelemetryPipeline(self.db_path) as pipeline:
            for i in range(5):
                await pipeline.emit(f"query_{i}", float(i * 10), cache_hit=(i % 2 == 0))

            # Wait for consumer to flush
            await asyncio.sleep(2.0)

        # After shutdown, all events should be flushed
        rows = _get_all_rows(self.db_path)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0][0], "query_0")
        self.assertEqual(rows[0][2], 1)  # cache_hit = True -> 1
        self.assertEqual(rows[1][2], 0)  # cache_hit = False -> 0

    async def test_batch_size_trigger(self):
        """Verify flush triggers at BATCH_SIZE threshold."""
        async with TelemetryPipeline(self.db_path) as pipeline:
            # Emit exactly BATCH_SIZE events
            for i in range(BATCH_SIZE):
                await pipeline.emit(f"batch_{i}", 1.0, cache_hit=False)

            # Should flush immediately (batch size reached)
            await asyncio.sleep(0.5)

        rows = _get_all_rows(self.db_path)
        self.assertEqual(len(rows), BATCH_SIZE)

    async def test_backpressure_fallback(self):
        """Fill queue to capacity, verify fallback to sync write."""
        async with TelemetryPipeline(self.db_path) as pipeline:
            # Fill the queue completely
            for i in range(QUEUE_MAXSIZE):
                await pipeline.emit(f"fill_{i}", 1.0, cache_hit=False)

            # Next emit should trigger fallback
            await pipeline.emit("overflow", 1.0, cache_hit=True)

            # Wait for consumer
            await asyncio.sleep(2.0)

        # All events should be persisted (some via fallback)
        total = _count_rows(self.db_path)
        self.assertEqual(total, QUEUE_MAXSIZE + 1)

    async def test_graceful_shutdown_flushes(self):
        """Shutdown should flush remaining events in queue."""
        pipeline = TelemetryPipeline(self.db_path)
        await pipeline.start()

        # Emit some events
        for i in range(3):
            await pipeline.emit(f"shutdown_{i}", 2.0, cache_hit=True)

        # Shutdown before consumer has a chance to flush
        await pipeline.shutdown()

        # All events should be flushed
        rows = _get_all_rows(self.db_path)
        self.assertEqual(len(rows), 3)

    async def test_get_summary_empty(self):
        """Summary on empty DB returns zeros."""
        async with TelemetryPipeline(self.db_path) as pipeline:
            summary = await pipeline.get_summary()

        self.assertEqual(summary["total_searches"], 0)
        self.assertEqual(summary["cache_hit_rate"], 0.0)
        self.assertEqual(summary["avg_latency_ms"], 0.0)
        self.assertEqual(summary["saved_time_ms"], 0)

    async def test_get_summary_with_data(self):
        """Summary returns correct aggregates."""
        async with TelemetryPipeline(self.db_path) as pipeline:
            # 3 cache hits, 2 misses
            await pipeline.emit("q1", 10.0, cache_hit=True)
            await pipeline.emit("q2", 20.0, cache_hit=False)
            await pipeline.emit("q3", 30.0, cache_hit=True)
            await pipeline.emit("q4", 40.0, cache_hit=False)
            await pipeline.emit("q5", 50.0, cache_hit=True)

            await asyncio.sleep(2.0)
            summary = await pipeline.get_summary()

        self.assertEqual(summary["total_searches"], 5)
        self.assertAlmostEqual(summary["cache_hit_rate"], 0.6)
        self.assertAlmostEqual(summary["avg_latency_ms"], 30.0)

    async def test_schema_creation(self):
        """Verify schema is created correctly."""
        conn = sqlite3.connect(str(self.db_path))
        _ensure_schema(conn)

        # Check search_telemetry table
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(search_telemetry)").fetchall()
        }
        self.assertIn("query", columns)
        self.assertIn("timestamp", columns)
        self.assertIn("latency_ms", columns)
        self.assertIn("cache_hit", columns)
        self.assertIn("query_signature", columns)

        # Check local_blacklist table
        bl_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(local_blacklist)").fetchall()
        }
        self.assertIn("blocked_until", bl_columns)
        self.assertIn("reason", bl_columns)
        self.assertIn("hit_count", bl_columns)

        conn.close()

    async def test_query_signature_stored(self):
        """Verify query_signature is stored correctly."""
        async with TelemetryPipeline(self.db_path) as pipeline:
            await pipeline.emit("test_query", 15.0, cache_hit=False, query_signature="sig_123")
            await asyncio.sleep(2.0)

        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT query_signature FROM search_telemetry LIMIT 1"
            ).fetchone()
            self.assertEqual(row[0], "sig_123")
        finally:
            conn.close()

    async def test_double_shutdown_idempotent(self):
        """Calling shutdown twice should not raise."""
        pipeline = TelemetryPipeline(self.db_path)
        await pipeline.start()
        await pipeline.emit("q", 1.0, cache_hit=False)
        await pipeline.shutdown()
        # Second shutdown should be a no-op
        await pipeline.shutdown()

        rows = _get_all_rows(self.db_path)
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
