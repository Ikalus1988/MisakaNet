"""MisakaNet GraphQL Schema — Issue #316.

Provides GraphQL API for lesson queries:
- search(q, domain, tags): full-text search
- lesson(id): get single lesson by ID
- lessons(limit, offset): paginated listing

Requires: pip install graphql-core (optional dependency)

Usage:
    from misakanet.graphql.schema import execute_query
    result = execute_query('{ lessons(limit: 5) { title domain } }')
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Lazy import: graphql-core is optional
_graphql = None

def _get_graphql():
    global _graphql
    if _graphql is None:
        try:
            import graphql as _g
            _graphql = _g
        except ImportError:
            raise ImportError(
                "graphql-core is required for GraphQL API. "
                "Install with: pip install graphql-core"
            )
    return _graphql

from misakanet.search.engine import (
    LESSONS,
    CachedDoc,
    _load_docs_cached,
    _rank_docs_impl,
)


# ── Data loading ──

def _get_lessons() -> list[CachedDoc]:
    """Load all lessons from disk."""
    return _load_docs_cached(LESSONS, is_lesson=True)


# ── GraphQL Types ──

def _build_schema():
    """Build GraphQL schema (lazy, only called when --graphql is used)."""
    g = _get_graphql()

    LessonType = g.GraphQLObjectType(
        "Lesson",
        lambda: {
            "title": g.GraphQLField(g.GraphQLString),
            "domain": g.GraphQLField(g.GraphQLString),
            "tags": g.GraphQLField(g.GraphQLList(g.GraphQLString)),
            "status": g.GraphQLField(g.GraphQLString),
            "language": g.GraphQLField(g.GraphQLString),
            "path": g.GraphQLField(g.GraphQLString),
            "preview": g.GraphQLField(g.GraphQLString),
        },
    )

    SearchResultType = g.GraphQLObjectType(
        "SearchResult",
        lambda: {
            "score": g.GraphQLField(g.GraphQLString),
            "lesson": g.GraphQLField(LessonType),
        },
    )

    QueryType = g.GraphQLObjectType(
        "Query",
        {
            "lessons": g.GraphQLField(
                g.GraphQLList(LessonType),
                args={
                    "limit": g.GraphQLArgument(g.GraphQLInt, default_value=10),
                    "offset": g.GraphQLArgument(g.GraphQLInt, default_value=0),
                },
                resolve=_resolve_lessons,
            ),
            "lesson": g.GraphQLField(
                LessonType,
                args={
                    "id": g.GraphQLArgument(g.GraphQLNonNull(g.GraphQLString)),
                },
                resolve=_resolve_lesson,
            ),
            "search": g.GraphQLField(
                g.GraphQLList(SearchResultType),
                args={
                    "q": g.GraphQLArgument(g.GraphQLNonNull(g.GraphQLString)),
                    "domain": g.GraphQLArgument(g.GraphQLString),
                    "tags": g.GraphQLArgument(g.GraphQLString),
                    "limit": g.GraphQLArgument(g.GraphQLInt, default_value=10),
                },
                resolve=_resolve_search,
            ),
        },
    )

    return g.GraphQLSchema(query=QueryType)


# ── Resolvers ──

def _resolve_lessons(root: Any, info: Any, limit: int = 10, offset: int = 0) -> list[dict]:
    """Paginated lesson listing."""
    docs = _get_lessons()
    # Filter out drafts and index
    visible = [d for d in docs if not d.is_draft and d.filename != "index.md"]
    page = visible[offset:offset + limit]
    return [_doc_to_dict(d) for d in page]


def _resolve_lesson(root: Any, info: Any, id: str) -> Optional[dict]:
    """Get single lesson by filename (ID)."""
    docs = _get_lessons()
    for d in docs:
        if d.filename == id or d.filename == f"{id}.md":
            return _doc_to_dict(d)
    return None


def _resolve_search(root: Any, info: Any, q: str, domain: Optional[str] = None, tags: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Full-text search with optional domain/tags filter."""
    docs = _get_lessons()
    # Filter out drafts
    visible = [d for d in docs if not d.is_draft]

    # Apply domain filter
    if domain:
        visible = [d for d in visible if d.domain and d.domain.lower() == domain.lower()]

    # Apply tags filter
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",")]
        visible = [d for d in visible if any(t in [gt.lower() for gt in d.tags] for t in tag_list)]

    # Rank
    ranked = _rank_docs_impl(q, visible, titles_only=False, broad_only=False)

    results = []
    for score, doc in ranked[:limit]:
        if score >= 0.1:
            results.append({
                "score": str(round(float(score), 4)),
                "lesson": _doc_to_dict(doc),
            })
    return results


def _doc_to_dict(doc: CachedDoc) -> dict:
    """Convert CachedDoc to GraphQL-friendly dict."""
    preview = doc.content[:200].replace("\n", " ").strip() if doc.content else ""
    return {
        "title": doc.title or "",
        "domain": doc.domain or "",
        "tags": list(doc.tags) if doc.tags else [],
        "status": doc.status or "",
        "language": doc.language or "",
        "path": str(doc.filepath.relative_to(doc.filepath.parent.parent)) if doc.filepath else "",
        "preview": preview,
    }


# ── Schema + Execution ──

def execute_query(query: str, variables: Optional[dict] = None) -> dict:
    """Execute a GraphQL query and return the result."""
    g = _get_graphql()
    schema = _build_schema()
    result = g.graphql_sync(schema, query, variable_values=variables)
    return {
        "data": result.data,
        "errors": [{"message": str(e)} for e in result.errors] if result.errors else None,
    }
