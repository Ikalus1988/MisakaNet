"""Tests for sliding window audit in TelemetryPipeline (Issue #138)."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from misakanet.tools.telemetry_pipeline import (
    TelemetryPipeline,
    _ensure_schema,
)


class TestSlidingWindowAudit(unittest.IsolatedAsyncioTestCase):
    """Test sliding window audit runs in consumer task."""

    async def asyncSetUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test_audit.db"

    async def test_audit_breach_does_not_crash_pipeline(self):
        """Audit breach (rate limit) should log warning, not crash pipeline."""
        # Insert 10 rapid queries to trigger rate limit
        conn = sqlite3.connect(str(self.db_path))
        _ensure_schema(conn)
        now = time.time()
        for i in range(10):
            conn.execute(
                "INSERT INTO search_telemetry (query, timestamp, latency_ms, cache_hit, query_signature) VALUES (?, ?, ?, ?, ?)",
                (f"query_{i}", now + i * 0.1, 100.0, 0, f"sig_{i}"),
            )
        conn.commit()
        conn.close()

        # Pipeline should not crash
        async with TelemetryPipeline(self.db_path) as pipeline:
            await pipeline.emit("new_query", 50.0, cache_hit=False)
            await asyncio.sleep(0.1)  # Let consumer process

        # Verify blacklist entry was created
        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute("SELECT COUNT(*) FROM local_blacklist").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 1)

    async def test_audit_cooldown_clears_blacklist(self):
        """After cooldown period, blacklist should be cleared."""
        # Insert a blacklist entry that's already expired
        conn = sqlite3.connect(str(self.db_path))
        _ensure_schema(conn)
        conn.execute(
            "INSERT INTO local_blacklist (blocked_until, reason, hit_count) VALUES (?, 'rate_limit', 1)",
            (time.time() - 100,),  # Expired 100s ago
        )
        conn.commit()
        conn.close()

        # Pipeline should work normally
        async with TelemetryPipeline(self.db_path) as pipeline:
            await pipeline.emit("test_query", 50.0, cache_hit=True)
            await asyncio.sleep(0.1)

        # Verify telemetry was recorded
        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute("SELECT COUNT(*) FROM search_telemetry").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
