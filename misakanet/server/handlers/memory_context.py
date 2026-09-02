"""Memory context handler — proactive lesson injection at task start."""
from __future__ import annotations

from .search import _fallback_search, _get_search_state


def handle_memory_context(args: dict) -> dict:
    """Pull relevant lessons as context for a task description.

    Intended to be called at the start of a task, so the agent has
    failure-memory injected into its context before it begins work.
    """
    task = args.get("task", "")
    domain = args.get("domain")
    top_n = min(args.get("top_n", 5), 10)

    if not task:
        return {
            "error": "task is required",
            "hint": (
                "Describe the task you are about to perform"
                " (e.g. 'set up ChromaDB RAG pipeline')."
            ),
            "voice": "failure-warning",
        }

    HAS_SAG, SAG_DB, HAS_BM25, sag_search = _get_search_state()

    # Reuse the existing search infrastructure
    if HAS_SAG:
        results = sag_search(SAG_DB, task, domain=domain, top=top_n)
    elif HAS_BM25:
        from .._config import _load_docs_cached, _search_cached, LESSONS
        from misakanet.search.engine import _score_breakdown

        docs = _load_docs_cached(LESSONS, is_lesson=True)
        scored = _search_cached(task, docs)
        results = []
        for score, doc in scored[:top_n]:
            results.append({
                "title": doc.title,
                "path": str(doc.filepath),
                "score": round(score, 3),
                "domain": doc.domain,
                "status": doc.status,
            })
    else:
        results = _fallback_search(task, domain=domain, top=top_n)
        if results is None:
            results = []

    # Build condensed context block for agent injection
    context_lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        lesson_id = r.get("id") or r.get("path", "")
        problem = r.get("problem", "")
        fix = r.get("fix", "")
        entry = f"{i}. [{title}] ({lesson_id})"
        if problem:
            entry += f"\n   Problem: {problem[:200]}"
        if fix:
            entry += f"\n   Fix: {fix[:200]}"
        context_lines.append(entry)

    context_block = (
        "\n".join(context_lines)
        if context_lines
        else "(No matching lessons found)"
    )

    return {
        "task": task,
        "lesson_count": len(results),
        "lessons": results,
        "context_block": (
            f"## Relevant MisakaNet Lessons ({len(results)} found)\n"
            f"Task: {task}\n\n{context_block}\n\n"
            "Use these lessons to avoid known pitfalls. "
            "Search MisakaNet for more details if needed."
        ),
        "voice": "lesson-found" if results else "failure-warning",
    }
