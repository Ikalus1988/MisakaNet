#!/usr/bin/env python3
"""Emit MisakaNet search results as JSON for editor/agent integrations.

The regular ``search_knowledge.py`` command is optimized for humans. Integrations
such as Continue custom context providers need stable, machine-readable records
that include title, score, and a compact relevant snippet.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Iterable

# Allow running this file directly from any working directory.
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from misakanet.search.engine import LESSONS, REFERENCES, _load_docs, _rank_docs  # noqa: E402


def _tokens(query: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[\w\u00c0-\u024f]+|[\u4e00-\u9fff]", query)]


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.DOTALL).strip()


def make_snippet(content: str, query: str, max_chars: int = 260) -> str:
    """Return a compact snippet near the first query token match."""
    text = re.sub(r"\s+", " ", _strip_frontmatter(content)).strip()
    if len(text) <= max_chars:
        return text

    lowered = text.lower()
    hit = -1
    for token in sorted(_tokens(query), key=len, reverse=True):
        if not token:
            continue
        hit = lowered.find(token)
        if hit >= 0:
            break

    if hit < 0:
        return text[: max_chars - 1].rstrip() + "…"

    start = max(0, hit - max_chars // 3)
    end = min(len(text), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)
    snippet = text[start:end].strip()
    if start:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def search(query: str, top: int = 5, include_reference: bool = True) -> list[dict]:
    """Search lessons/reference and return serializable result dictionaries."""
    # The cache layer may print cache migration/status messages. Keep stdout pure
    # JSON for callers that parse this command.
    with contextlib.redirect_stdout(io.StringIO()):
        docs = _load_docs(LESSONS, is_lesson=True)
        if include_reference:
            docs += _load_docs(REFERENCES, is_lesson=False)
        ranked = _rank_docs(query, docs, titles_only=False, broad_only=False)

    results = []
    for score, doc in ranked[:top]:
        rel_path = doc.filepath.relative_to(REPO).as_posix()
        results.append(
            {
                "title": doc.title,
                "score": round(float(score), 4),
                "path": rel_path,
                "domain": doc.domain,
                "status": doc.status,
                "source": doc.source,
                "snippet": make_snippet(doc.content, query),
            }
        )
    return results


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search MisakaNet and emit JSON results.")
    parser.add_argument("query", help="Search query, for example: 'database locked'")
    parser.add_argument("--top", type=int, default=5, help="Number of results to emit (default: 5)")
    parser.add_argument(
        "--lessons-only",
        action="store_true",
        help="Search only lessons, excluding reference documents.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    payload = {
        "query": args.query,
        "top": args.top,
        "results": search(args.query, top=args.top, include_reference=not args.lessons_only),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
