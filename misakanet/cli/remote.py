"""Remote (D1) corpus loading for the MisakaNet CLI.

Extracted from search_knowledge.py (audit 2026-09-05, T1.1 stage 2). The CLI
entry keeps the ``_load_docs_anywhere`` / ``_load_remote_docs`` names via a
module-level re-import.
"""
import json
import sys
from pathlib import Path

# ── Remote mode (PRD ④): search the D1 service instead of local files ──
# `python3 search_knowledge.py "query" --remote` pulls lessons from
# https://misakanet.org/api/lessons (D1-backed, no clone needed) and runs the
# same BM25 pipeline over them. `--local` (default) keeps the old behavior.

_REMOTE_API = "https://misakanet.org/api/lessons"
_REMOTE_CACHE_TTL = 300  # seconds


def _load_remote_docs(timeout: int = 30) -> list:
    """Fetch lesson index from the D1 service and build CachedDoc objects."""
    import urllib.request

    from misakanet.search.engine import CachedDoc
    repo_root = Path(__file__).resolve().parent.parent.parent

    # Use the structured filters endpoint when we can cache per-query; for a
    # plain corpus load, grab a large page and let BM25 rank locally.
    url = f"{_REMOTE_API}?limit=5000"
    headers = {"User-Agent": "misakanet-cli/remote", "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected /api/lessons response: {str(data)[:200]}")

    docs = []
    for item in data:
        body = item.get("description") or item.get("problem") or ""
        # Use an absolute path under the repo root so _doc_cache_id's
        # relative_to(REPO) works for remote docs too.
        rel = item.get("path") or f"lessons/remote/{item.get('id', 'remote.md')}.md"
        docs.append(CachedDoc(
            filename=item.get("id", ""),
            filepath=repo_root / rel,
            content=body,
            title=item.get("title", item.get("id", "")),
            domain=item.get("domain", ""),
            status=item.get("status", ""),
            tags=item.get("tags") or [],
            language=item.get("language", ""),
            is_lesson=True,
        ))
    return docs


def _load_docs_anywhere(
    mode: str,
    remote: bool,
    domain: str | None = None,
    status_filter: str | None = None,
    tags_filter: list[str] | None = None,
) -> list:
    """Load docs from remote D1 (--remote) or local repo (default)."""
    if remote:
        try:
            return _load_remote_docs()
        except Exception as e:
            print(f"  ⚠️ Remote search failed ({e}); falling back to local", file=sys.stderr)
    from misakanet.search.engine import LESSONS, _load_docs
    return _load_docs(LESSONS, is_lesson=True)


