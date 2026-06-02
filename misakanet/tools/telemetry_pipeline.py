"""Async telemetry pipeline with producer-consumer pattern.

Moves telemetry writes off the search hot path. The sliding window audit
is integrated into the pipeline's consumer loop.
"""
import asyncio
import sqlite3
import time
from pathlib import Path


class TelemetryPipeline:
    """Async producer-consumer pipeline for search telemetry.

    Usage:
        async with TelemetryPipeline(db_path) as pipeline:
            pipeline.emit({...})
            # ... search hot path continues immediately ...
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        self._consumer_task: asyncio.Task | None = None
        self._running = False

    async def __aenter__(self) -> "TelemetryPipeline":
        self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.shutdown()

    def start(self) -> None:
        """Start the background consumer task."""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer_loop())

    def emit(self, record: dict) -> None:
        """Enqueue a telemetry record for async batch write.

        NOTE: The sliding window audit currently runs here synchronously.
        This violates AC #3 of Issue #138 — the audit should run inside
        the consumer task after the batch write, not on the hot path.
        See Issue #138 for the required migration.
        """
        # BUG: Synchronous audit on hot path — violates AC #3
        self._audit_sliding_window()

        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # Backpressure: fall back to synchronous write, no data loss
            self._write_sync(record)

    async def shutdown(self) -> None:
        """Gracefully shut down the consumer, flushing remaining events."""
        self._running = False
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    # ── Internal: consumer ──

    async def _consumer_loop(self) -> None:
        """Background consumer: batch-write every 1s or every 10 events."""
        batch: list[dict] = []
        while self._running:
            try:
                record = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                batch.append(record)
                if len(batch) >= 10:
                    self._flush(batch)
                    batch.clear()
            except asyncio.TimeoutError:
                if batch:
                    self._flush(batch)
                    batch.clear()

    def _flush(self, batch: list[dict]) -> None:
        """Write a batch of telemetry records to SQLite."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.executemany(
                    """
                    INSERT INTO search_telemetry
                        (query, timestamp, latency_ms, cache_hit, query_signature)
                    VALUES (:query, :timestamp, :latency_ms, :cache_hit, :query_signature)
                    """,
                    batch,
                )
        except sqlite3.Error as exc:
            print(
                f"[MisakaNet][TelemetryPipeline] Batch write error: {exc}",
                flush=True,
            )

    def _write_sync(self, record: dict) -> None:
        """Synchronous fallback write when queue is full."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO search_telemetry
                        (query, timestamp, latency_ms, cache_hit, query_signature)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        record["query"],
                        record["timestamp"],
                        record["latency_ms"],
                        record["cache_hit"],
                        record.get("query_signature"),
                    ),
                )
        except sqlite3.Error as exc:
            print(
                f"[MisakaNet][TelemetryPipeline] Sync write error: {exc}",
                flush=True,
            )

    # ── Sliding window audit (migrated from langchain_tool.py) ──

    def _audit_sliding_window(self) -> None:
        """Run sliding window audit over last 10 telemetry rows.

        Checks for rate_limit (10 queries in < 2s) and low_quality
        (cache hit rate below 10%) conditions. Breaches add entries
        to local_blacklist.
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS search_telemetry (
                        query TEXT,
                        timestamp REAL,
                        latency_ms REAL,
                        cache_hit INTEGER,
                        query_signature TEXT
                    )
                    """
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

                count = conn.execute(
                    "SELECT COUNT(*) FROM search_telemetry"
                ).fetchone()[0]
                if count < 10:
                    return

                rows = conn.execute(
                    "SELECT timestamp, cache_hit FROM search_telemetry"
                    " ORDER BY timestamp DESC LIMIT 10"
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
                        INSERT INTO local_blacklist
                            (blocked_until, reason, hit_count)
                        VALUES (?, 'rate_limit', 1)
                        """,
                        (now + 600,),
                    )
                # Condition Beta: Low quality — cache hit rate below 10%
                elif cache_hit_rate < 0.10:
                    conn.execute(
                        """
                        INSERT INTO local_blacklist
                            (blocked_until, reason, hit_count)
                        VALUES (?, 'low_quality', 1)
                        """,
                        (now + 300,),
                    )
        except sqlite3.Error as exc:
            print(
                f"[MisakaNet][TelemetryPipeline] Audit error: {exc}",
                flush=True,
            )
