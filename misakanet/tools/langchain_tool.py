import asyncio
import hashlib
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

# Try to import langchain BaseTool, fallback to a standalone class if not available
try:
    from langchain_core.tools import BaseTool
    HAS_LANGCHAIN = True
except ImportError:
    try:
        from langchain.tools import BaseTool
        HAS_LANGCHAIN = True
    except ImportError:
        BaseTool = object
        HAS_LANGCHAIN = False


class MisakaNetSearchTool(BaseTool):
    name: str = "misakanet_search"
    description: str = (
        "Search the MisakaNet distributed knowledge base for solved developer bugs and experience."
    )
    cache_ttl_seconds: int = 300
    cache_path: Path | None = None
    telemetry_path: Path | None = None

    def __init__(
        self,
        cache_path: str | Path | None = None,
        telemetry_path: str | Path | None = None,
        cache_ttl_seconds: int = 300,
        **kwargs,
    ):
        if HAS_LANGCHAIN:
            super().__init__(**kwargs)
        else:
            # Standalone mock implementation fields
            pass
        repo_root = Path(__file__).resolve().parents[2]
        object.__setattr__(
            self,
            "cache_path",
            Path(cache_path)
            if cache_path is not None
            else repo_root / ".cache" / "langchain_tool_cache.db",
        )
        object.__setattr__(
            self,
            "telemetry_path",
            Path(telemetry_path)
            if telemetry_path is not None
            else repo_root / ".cache" / "langchain_telemetry.db",
        )
        object.__setattr__(self, "cache_ttl_seconds", cache_ttl_seconds)

    def _run(self, query: str) -> str:
        self._audit_sliding_window()
        self._check_blacklist()
        started = time.perf_counter()
        query_signature = self._query_signature(
            query,
            (time.perf_counter() - started) * 1000,
        )
        if self._has_repeated_query_signature(query_signature):
            return "[Rate Limited] Repeated query pattern detected."

        cache_hit = 0
        cached = self._get_cached_result(query)
        if cached is not None:
            self._record_telemetry(query, started, cache_hit=1, query_signature=query_signature)
            return cached

        result = self._execute_search(query)
        self._set_cached_result(query, result)
        self._record_telemetry(query, started, cache_hit=cache_hit, query_signature=query_signature)
        return result

    def _execute_search(self, query: str) -> str:
        # Import core engine elements
        from misakanet.search.engine import _load_docs, _rank_docs, LESSONS, REFERENCES
        
        lessons_docs = _load_docs(LESSONS, is_lesson=True)
        ref_docs = _load_docs(REFERENCES, is_lesson=False)
        all_docs = lessons_docs + ref_docs
        
        # Rank docs using expanded local queries and Reciprocal Rank Fusion.
        ranked = self._rank_with_rrf(query, all_docs, _rank_docs)
        if not ranked:
            return f"No results found in MisakaNet for '{query}'"
            
        results = []
        for score, doc in ranked[:3]:
            # Clean preview
            preview = doc.content.replace('\r\n', '\n').split('\n')
            preview_lines = [l for l in preview if l.strip() and not l.startswith('---')][:8]
            content_preview = '\n'.join(preview_lines)
            results.append(
                f"📄 File: lessons/{doc.filename}\n"
                f"📌 Title: {doc.title}\n"
                f"🔍 Domain: {doc.domain}\n"
                f"📝 Preview:\n{content_preview}\n"
            )
            
        return "\n" + "\n----------------------------------------\n".join(results)

    def run(self, query: str) -> str:
        return self._run(query)

    def search(self, query: str) -> str:
        return self._run(query)

    async def _arun(self, query: str) -> str:
        return await asyncio.to_thread(self._run, query)

    def _expand_query(self, query: str) -> list[str]:
        base = " ".join(query.split())
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", base.lower())
        unique_tokens = list(dict.fromkeys(tokens))

        candidates = [
            base,
            " ".join(unique_tokens),
            " ".join(reversed(unique_tokens)),
        ]
        if unique_tokens:
            candidates.extend([
                f"{base} solution",
                f"{base} troubleshooting",
                " ".join(unique_tokens[: max(1, len(unique_tokens) // 2)]),
            ])

        expanded = []
        seen = set()
        for candidate in candidates:
            normalized = " ".join(candidate.split())
            if normalized and normalized not in seen:
                expanded.append(normalized)
                seen.add(normalized)
            if len(expanded) == 3:
                return expanded

        while len(expanded) < 3:
            fallback = f"{base} variant {len(expanded) + 1}".strip()
            if fallback not in seen:
                expanded.append(fallback)
                seen.add(fallback)
        return expanded

    def _rank_with_rrf(self, query: str, docs: list, ranker) -> list[tuple[float, object]]:
        fused: dict[str, dict[str, object]] = {}
        for subquery in self._expand_query(query):
            for rank, (score, doc) in enumerate(ranker(subquery, docs), start=1):
                doc_key = str(getattr(doc, "filepath", getattr(doc, "filename", id(doc))))
                filename = str(getattr(doc, "filename", doc_key))
                item = fused.setdefault(
                    doc_key,
                    {
                        "score": 0.0,
                        "doc": doc,
                        "best_rank": rank,
                        "filename": filename,
                    },
                )
                item["score"] = float(item["score"]) + 1.0 / (60 + rank)
                item["best_rank"] = min(int(item["best_rank"]), rank)
                item["filename"] = min(str(item["filename"]), filename)

        ranked = sorted(
            fused.values(),
            key=lambda item: (
                -float(item["score"]),
                int(item["best_rank"]),
                str(item["filename"]),
            ),
        )
        return [(float(item["score"]), item["doc"]) for item in ranked]

    def _cache_key(self, query: str) -> str:
        return hashlib.sha256(query.strip().encode("utf-8")).hexdigest()

    def _query_signature(self, query: str, latency_ms: float) -> str:
        latency_bucket = round(latency_ms / 100) * 100
        payload = f"{query.strip().lower()}\0{latency_bucket}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @contextmanager
    def _cache_connection(self):
        assert self.cache_path is not None
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.cache_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS langchain_search_cache (
                cache_key TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                created_at REAL NOT NULL,
                result TEXT NOT NULL
            )
            """
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_cached_result(self, query: str) -> str | None:
        now = time.time()
        key = self._cache_key(query)
        with self._cache_connection() as conn:
            cutoff = now - self.cache_ttl_seconds
            conn.execute("DELETE FROM langchain_search_cache WHERE created_at < ?", (cutoff,))
            row = conn.execute(
                "SELECT result, created_at FROM langchain_search_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            result, created_at = row
            if now - float(created_at) <= self.cache_ttl_seconds:
                return result
            conn.execute("DELETE FROM langchain_search_cache WHERE cache_key = ?", (key,))
        return None

    def _set_cached_result(self, query: str, result: str) -> None:
        with self._cache_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO langchain_search_cache
                    (cache_key, query, created_at, result)
                VALUES (?, ?, ?, ?)
                """,
                (self._cache_key(query), query, time.time(), result),
            )

    @contextmanager
    def _telemetry_connection(self):
        assert self.telemetry_path is not None
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.telemetry_path), timeout=5)
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
            row[1] for row in conn.execute("PRAGMA table_info(search_telemetry)").fetchall()
        }
        if "query_signature" not in columns:
            conn.execute("ALTER TABLE search_telemetry ADD COLUMN query_signature TEXT")
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
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _has_repeated_query_signature(self, query_signature: str) -> bool:
        cutoff = time.time() - 60
        with self._telemetry_connection() as conn:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM search_telemetry
                    WHERE query_signature = ?
                      AND timestamp >= ?
                    """,
                    (query_signature, cutoff),
                ).fetchone()[0]
            )
        return count >= 5

    def _check_blacklist(self) -> None:
        """Pre-flight check: raise PermissionError if currently blacklisted."""
        now = time.time()
        with self._telemetry_connection() as conn:
            row = conn.execute(
                "SELECT blocked_until, reason FROM local_blacklist WHERE blocked_until > ? LIMIT 1",
                (now,),
            ).fetchone()
            if row is not None:
                raise PermissionError(
                    "MisakaNet Anti-Abuse Shield: Node access suspended due to anomalous behaviors."
                )

    def _audit_sliding_window(self) -> None:
        """Run sliding window audit over last 10 telemetry rows."""
        with self._telemetry_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM search_telemetry"
            ).fetchone()[0]
            if count < 10:
                return

            rows = conn.execute(
                "SELECT timestamp, cache_hit FROM search_telemetry ORDER BY timestamp DESC LIMIT 10"
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
            # Condition Beta: Low quality — cache hit rate below 10%
            elif cache_hit_rate < 0.10:
                conn.execute(
                    """
                    INSERT INTO local_blacklist (blocked_until, reason, hit_count)
                    VALUES (?, 'low_quality', 1)
                    """,
                    (now + 300,),
                )

    def _record_telemetry(
        self,
        query: str,
        started: float,
        cache_hit: int,
        query_signature: str | None = None,
    ) -> None:
        latency_ms = (time.perf_counter() - started) * 1000
        if query_signature is None:
            query_signature = self._query_signature(query, latency_ms)
        with self._telemetry_connection() as conn:
            conn.execute(
                """
                INSERT INTO search_telemetry
                    (query, timestamp, latency_ms, cache_hit, query_signature)
                VALUES (?, ?, ?, ?, ?)
                """,
                (query, time.time(), latency_ms, cache_hit, query_signature),
            )

    def get_telemetry_summary(self) -> dict:
        with self._telemetry_connection() as conn:
            total_searches = int(
                conn.execute("SELECT COUNT(*) FROM search_telemetry").fetchone()[0]
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
                conn.execute("SELECT AVG(latency_ms) FROM search_telemetry").fetchone()[0]
                or 0.0
            )
            avg_hit_latency = conn.execute(
                "SELECT AVG(latency_ms) FROM search_telemetry WHERE cache_hit = 1"
            ).fetchone()[0]
            avg_miss_latency = conn.execute(
                "SELECT AVG(latency_ms) FROM search_telemetry WHERE cache_hit = 0"
            ).fetchone()[0]

        saved_time_ms = 0
        if hit_count and avg_hit_latency is not None and avg_miss_latency is not None:
            saved_time_ms = (float(avg_miss_latency) - float(avg_hit_latency)) * hit_count

        return {
            "total_searches": total_searches,
            "cache_hit_rate": hit_count / total_searches,
            "avg_latency_ms": avg_latency_ms,
            "saved_time_ms": saved_time_ms,
        }
