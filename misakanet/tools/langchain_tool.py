import asyncio
import hashlib
import re
import sqlite3
import time
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

    def __init__(
        self,
        cache_path: str | Path | None = None,
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
        object.__setattr__(self, "cache_ttl_seconds", cache_ttl_seconds)

    def _run(self, query: str) -> str:
        cached = self._get_cached_result(query)
        if cached is not None:
            return cached

        result = self._execute_search(query)
        self._set_cached_result(query, result)
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
        return conn

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
