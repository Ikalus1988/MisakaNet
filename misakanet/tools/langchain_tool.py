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


REPO = Path(__file__).resolve().parents[2]
_CACHE_TTL_SECONDS = 300
_CACHE_DB = REPO / ".cache" / "langchain_tool_cache.db"
_RRF_K = 60


def _query_key(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()


def _cache_conn() -> sqlite3.Connection:
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_CACHE_DB))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS search_cache (
            query_key TEXT PRIMARY KEY,
            query TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    return conn


def _cache_lookup(query: str) -> str | None:
    cutoff = time.time() - _CACHE_TTL_SECONDS
    with _cache_conn() as conn:
        conn.execute("DELETE FROM search_cache WHERE created_at < ?", (cutoff,))
        row = conn.execute(
            "SELECT result FROM search_cache WHERE query_key = ? AND created_at >= ?",
            (_query_key(query), cutoff),
        ).fetchone()
    return row[0] if row else None


def _cache_store(query: str, result: str) -> None:
    with _cache_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO search_cache (query_key, query, result, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (_query_key(query), query, result, time.time()),
        )


def _expand_query(query: str) -> list[str]:
    compact = " ".join(query.split())
    if not compact:
        return ["", "keywords", "summary"]

    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "for",
        "from",
        "how",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "what",
        "when",
        "where",
        "why",
    }
    tokens = [
        token
        for token in re.findall(r"[\w\u4e00-\u9fff]+", compact.lower())
        if token not in stopwords
    ]

    variants = [compact]
    if tokens:
        variants.append(" ".join(tokens[:8]))
        variants.append(" ".join(tokens[-8:]))

    # Keep exactly three distinct local variants without relying on an LLM.
    for suffix in ("troubleshooting", "solution", "implementation"):
        if len({v for v in variants if v}) >= 3:
            break
        variants.append(f"{compact} {suffix}")

    distinct = []
    seen = set()
    for variant in variants:
        normalized = " ".join(variant.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            distinct.append(normalized)
        if len(distinct) == 3:
            break
    while len(distinct) < 3:
        distinct.append(compact)
    return distinct


def _load_search_docs():
    from misakanet.search.engine import LESSONS, REFERENCES, _load_docs

    lessons_docs = _load_docs(LESSONS, is_lesson=True)
    ref_docs = _load_docs(REFERENCES, is_lesson=False)
    return lessons_docs + ref_docs


def _rank_subquery(query: str, docs):
    from misakanet.search.engine import _rank_docs

    return _rank_docs(query, docs)


def _rrf_merge(result_sets, k: int = _RRF_K):
    doc_map = {}
    scores = {}
    best_rank = {}

    for ranked in result_sets:
        for rank, (_score, doc) in enumerate(ranked, start=1):
            doc_id = str(getattr(doc, "filepath", getattr(doc, "filename", id(doc))))
            doc_map[doc_id] = doc
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            best_rank[doc_id] = min(best_rank.get(doc_id, rank), rank)

    merged = [(score, doc_map[doc_id], best_rank[doc_id]) for doc_id, score in scores.items()]
    merged.sort(key=lambda item: (-item[0], item[2], getattr(item[1], "filename", "")))
    return [(score, doc) for score, doc, _rank in merged]


def _format_doc_path(doc) -> str:
    filepath = getattr(doc, "filepath", None)
    if filepath:
        try:
            return str(Path(filepath).relative_to(REPO)).replace("\\", "/")
        except ValueError:
            return str(filepath).replace("\\", "/")
    return getattr(doc, "filename", "unknown")


def _format_results(query: str, ranked) -> str:
    if not ranked:
        return f"No results found in MisakaNet for '{query}'"

    results = []
    for score, doc in ranked[:3]:
        preview = getattr(doc, "content", "").replace("\r\n", "\n").split("\n")
        preview_lines = [line for line in preview if line.strip() and not line.startswith("---")][:8]
        content_preview = "\n".join(preview_lines)
        results.append(
            "\n".join(
                [
                    f"File: {_format_doc_path(doc)}",
                    f"Title: {getattr(doc, 'title', '')}",
                    f"Domain: {getattr(doc, 'domain', '')}",
                    f"RRF Score: {score:.6f}",
                    "Preview:",
                    content_preview,
                ]
            )
        )
    return "\n" + "\n----------------------------------------\n".join(results)


class MisakaNetSearchTool(BaseTool):
    name: str = "misakanet_search"
    description: str = (
        "Search the MisakaNet distributed knowledge base for solved developer bugs and "
        "experience."
    )

    def __init__(self, **kwargs):
        if HAS_LANGCHAIN:
            super().__init__(**kwargs)
        else:
            # Standalone mock implementation fields
            pass

    def _run(self, query: str) -> str:
        cached = _cache_lookup(query)
        if cached is not None:
            return cached

        all_docs = _load_search_docs()
        result_sets = [_rank_subquery(subquery, all_docs) for subquery in _expand_query(query)]
        ranked = _rrf_merge(result_sets)
        result = _format_results(query, ranked)
        _cache_store(query, result)
        return result

    def run(self, query: str) -> str:
        return self._run(query)

    async def _arun(self, query: str) -> str:
        return await asyncio.to_thread(self._run, query)
