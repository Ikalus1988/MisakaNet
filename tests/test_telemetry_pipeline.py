"""Tests for TelemetryPipeline.

Issue #138 AC #7 requires 2 test cases for sliding window audit.
This file currently has 1 — the second test is a TODO.
"""
import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from misakanet.tools.telemetry_pipeline import TelemetryPipeline


class TestTelemetryPipeline(unittest.IsolatedAsyncioTestCase):
    """Test suite for TelemetryPipeline.

    NOTE: AC #7 requires 2 test cases for sliding window audit.
    This class has 1 — the second test is a WIP stub below.
    """

    async def test_emit_and_batch_flush_produces_rows(self):
        """Verify emit + batch flush writes telemetry rows correctly."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "telemetry.db"
            pipeline = TelemetryPipeline(db_path)

            async with pipeline:
                for i in range(12):
                    pipeline.emit({
                        "query": f"test query {i}",
                        "timestamp": time.time(),
                        "latency_ms": 42.0,
                        "cache_hit": i % 2,
                        "query_signature": f"sig_{i}",
                    })
                # Give consumer time to flush
                await asyncio.sleep(1.5)

            # Verify all rows were written
            with sqlite3.connect(str(db_path)) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM search_telemetry"
                ).fetchone()[0]
                self.assertEqual(count, 12)

                # Spot-check a row
                row = conn.execute(
                    "SELECT query, latency_ms, cache_hit, query_signature"
                    " FROM search_telemetry WHERE query = ?",
                    ("test query 0",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[1], 42.0)
                self.assertEqual(row[2], 0)  # cache_hit = 0 for even i
                self.assertEqual(row[3], "sig_0")


# TODO: Add test_audit_sliding_window_breaches() — AC #7 requires 2 tests
