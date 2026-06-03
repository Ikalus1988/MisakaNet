"""Async producer-consumer pipeline for search telemetry.

Decouples telemetry writes from the search hot path using an async
producer-consumer pattern. The consumer task batch-writes events to
SQLite every 1 second or every 10 events, whichever comes first.

Python stdlib only — no third-party dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Batch flush thresholds
BATCH_SIZE = 10
FLUSH_INTERVAL_S = 1.0
QUEUE_MAXSIZE = 500


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables and columns if they don't exist."""
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS search_telemetry (
            query TEXT,
            timestamp REAL,
            latency_ms REAL,
            cache_hit INTEGER
        )
        """
    )
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(search_telemetry)").fetchall()
    }
    if "query_signature" not in columns:
        conn.execute(
            "ALTER TABLE search_telemetry ADD COLUMN query_signature TEXT"
        )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS local_blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blocked_until REAL,
            reason TEXT,
            hit_count INTEGER DEFAULT 1
        )
        """
    )


class TelemetryPipeline:
    """Async producer-consumer pipeline for search telemetry.

    Usage::

        async with TelemetryPipeline(db_path) as pipeline:
            await pipeline.emit("query", 42.0, cache_hit=False)
            summary = await pipeline.get_summary()
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=QUEUE_MAXSIZE
        )
        self._consumer_task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()
        self._closed = False

    # -- async context manager --------------------------------------------------

    async def __aenter__(self) -> TelemetryPipeline:
        await self.start()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.shutdown()

    # -- lifecycle --------------------------------------------------------------

    async def start(self) -> None:
        """Start the background consumer task."""
        if self._consumer_task is not None:
            return
        self._shutdown_event.clear()
        self._closed = False
        self._consumer_task = asyncio.create_task(self._consumer_loop())

    async def shutdown(self) -> None:
        """Flush remaining events and stop the consumer task."""
        if self._closed:
            return
        self._closed = True
        self._shutdown_event.set()
        if self._consumer_task is not None:
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

    # -- producer ---------------------------------------------------------------

    async def emit(
        self,
        query: str,
        latency_ms: float,
        cache_hit: bool,
        query_signature: str | None = None,
    ) -> None:
        """Enqueue a telemetry event. Non-blocking, O(1).

        On queue full, falls back to a synchronous write so no data is lost.
        """
        event: dict[str, Any] = {
            "query": query,
            "timestamp": time.time(),
            "latency_ms": latency_ms,
            "cache_hit": 1 if cache_hit else 0,
            "query_signature": query_signature or "",
        }
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Telemetry queue full (%d), falling back to sync write",
                self._queue.maxsize,
            )
            self._sync_write([event])

    # -- consumer ---------------------------------------------------------------

    async def _consumer_loop(self) -> None:
        """Background consumer: batch-writes every 1s or every 10 events."""
        while not self._shutdown_event.is_set():
            batch: list[dict[str, Any]] = []
            try:
                # Wait for first event or shutdown
                event = await asyncio.wait_for(
                    self._queue.get(), timeout=FLUSH_INTERVAL_S
                )
                batch.append(event)
                # Drain up to BATCH_SIZE - 1 more without blocking
                for _ in range(BATCH_SIZE - 1):
                    try:
                        batch.append(self._queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
            except asyncio.TimeoutError:
                # No events within flush interval — loop back
                continue

            if batch:
                self._sync_write(batch)
                self._run_sliding_window_audit()

        # Shutdown: flush remaining events
        await self._drain_queue()

    async def _drain_queue(self) -> None:
        """Flush all remaining events in the queue."""
        batch: list[dict[str, Any]] = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            self._sync_write(batch)

    # -- synchronous DB operations (run in executor to avoid blocking) ----------

    def _sync_write(self, batch: list[dict[str, Any]]) -> None:
        """Write a batch of events to SQLite synchronously."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path), timeout=5)
            try:
                _ensure_schema(conn)
                conn.executemany(
                    """
                    INSERT INTO search_telemetry
                        (query, timestamp, latency_ms, cache_hit, query_signature)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            e["query"],
                            e["timestamp"],
                            e["latency_ms"],
                            e["cache_hit"],
                            e["query_signature"],
                        )
                        for e in batch
                    ],
                )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.error("Telemetry batch write failed", exc_info=True)
            finally:
                conn.close()
        except Exception:
            logger.error("Telemetry DB connection failed", exc_info=True)

    def _run_sliding_window_audit(self) -> None:
        """Run sliding window audit over last 10 telemetry rows.

        Mirrors the audit logic from MisakaNetSearchTool._audit_sliding_window.
        """
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=5)
            try:
                _ensure_schema(conn)
                count = conn.execute(
                    "SELECT COUNT(*) FROM search_telemetry"
                ).fetchone()[0]
                if count < 10:
                    return

                rows = conn.execute(
                    """
                    SELECT timestamp, cache_hit
                    FROM search_telemetry
                    ORDER BY timestamp DESC
                    LIMIT 10
                    """
                ).fetchall()

                timestamps = [r[0] for r in rows]
                cache_hits = [r[1] for r in rows]
                window_span = max(timestamps) - min(timestamps)
                cache_hit_rate = sum(cache_hits) / len(cache_hits)

                now = time.time()

                # Condition Alpha: Rate limit — 10 queries in < 2 seconds
                if window_span < 2.0:
                    conn.execute(
                        """
                        INSERT INTO local_blacklist (blocked_until, reason, hit_count)
                        VALUES (?, 'rate_limit', 1)
                        """,
                        (now + 600,),
                    )
                    conn.commit()
                    logger.warning(
                        "Sliding window audit: rate limit trigger (10 queries in %.1fs)",
                        window_span,
                    )
                # Condition Beta: Low quality — cache hit rate below 10%
                elif cache_hit_rate < 0.10:
                    conn.execute(
                        """
                        INSERT INTO local_blacklist (blocked_until, reason, hit_count)
                        VALUES (?, 'low_quality', 1)
                        """,
                        (now + 300,),
                    )
                    conn.commit()
                    logger.warning(
                        "Sliding window audit: low quality trigger (cache hit rate %.1f%%)",
                        cache_hit_rate * 100,
                    )
            except Exception:
                conn.rollback()
                logger.error("Sliding window audit failed", exc_info=True)
            finally:
                conn.close()
        except Exception:
            logger.error("Sliding window audit DB connection failed", exc_info=True)

    # -- read-only queries ------------------------------------------------------

    async def get_summary(self) -> dict[str, Any]:
        """Read-only aggregate query over telemetry data."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._sync_summary
        )

    def _sync_summary(self) -> dict[str, Any]:
        """Synchronous summary query."""
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=5)
            try:
                _ensure_schema(conn)
                total_searches = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM search_telemetry"
                    ).fetchone()[0]
                )
                if total_searches == 0:
                    return {
                        "total_searches": 0,
                        "cache_hit_rate": 0.0,
                        "avg_latency_ms": 0.0,
                        "saved_time_ms": 0,
                    }

                hit_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM search_telemetry WHERE cache_hit = 1"
                    ).fetchone()[0]
                )
                avg_latency_ms = float(
                    conn.execute(
                        "SELECT AVG(latency_ms) FROM search_telemetry"
                    ).fetchone()[0]
                    or 0.0
                )
                avg_hit_latency = conn.execute(
                    "SELECT AVG(latency_ms) FROM search_telemetry WHERE cache_hit = 1"
                ).fetchone()[0]
                avg_miss_latency = conn.execute(
                    "SELECT AVG(latency_ms) FROM search_telemetry WHERE cache_hit = 0"
                ).fetchone()[0]

                saved_time_ms = 0
                if (
                    hit_count
                    and avg_hit_latency is not None
                    and avg_miss_latency is not None
                ):
                    saved_time_ms = (
                        float(avg_miss_latency) - float(avg_hit_latency)
                    ) * hit_count

                return {
                    "total_searches": total_searches,
                    "cache_hit_rate": hit_count / total_searches,
                    "avg_latency_ms": avg_latency_ms,
                    "saved_time_ms": saved_time_ms,
                }
            finally:
                conn.close()
        except Exception:
            logger.error("Telemetry summary query failed", exc_info=True)
            return {
                "total_searches": 0,
                "cache_hit_rate": 0.0,
                "avg_latency_ms": 0.0,
                "saved_time_ms": 0,
            }
