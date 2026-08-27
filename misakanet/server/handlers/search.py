"""MisakaNet search handler with progressive disclosure."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .._config import REPO_ROOT, _init_search

# Lazy init on first call
_SEARCH_STATE = None


def _get_search_state():
    global _SEARCH_STATE
    if _SEARCH_STATE is None:
        _SEARCH_STATE = _init_search()
    return _SEARCH_STATE


def _fallback_search(query: str, domain: str = None, top: int = 5) -> list | None:
    """Lightweight keyword search from lessons.json — zero dependencies.

    Used when SAG-Lite and BM25 are both unavailable (e.g. Glama sandbox).
    Returns None if lessons.json is not found (caller should show error).
    Returns [] if lessons.json exists but no matches (caller should show empty results).
    """
    # Try multiple locations for lessons.json
    candidates = [
        REPO_ROOT / "data" / "lessons.json",
        REPO_ROOT / "lessons.json",
    ]
    lessons = None
    for path in candidates:
        if path.exists():
            try:
                lessons = json.loads(
                    path.read_text(encoding="utf-8", errors="replace")
                )
                break
            except Exception:
                continue

    if not lessons or not isinstance(lessons, list):
        return None

    q = query.lower()
    q_words = [w for w in q.split() if len(w) > 2]
    scored = []

    for lesson in lessons:
        if not isinstance(lesson, dict):
            continue
        if domain and lesson.get("domain", "").lower() != domain.lower():
            continue

        title = (lesson.get("title") or "").lower()
        summary = (lesson.get("summary") or "").lower()
        lesson_domain = (lesson.get("domain") or "").lower()
        tags = (
            " ".join(lesson.get("tags", [])).lower()
            if isinstance(lesson.get("tags"), list)
            else ""
        )
        text = f"{title} {summary} {lesson_domain} {tags}"

        score = 0
        if q in text:
            score += 10
        for w in q_words:
            if w in text:
                score += 2
            if w in title:
                score += 1

        if score > 0:
            scored.append((score, lesson))

    scored.sort(key=lambda x: -x[0])
    return [
        {
            "title": entry.get("title", ""),
            "path": entry.get("url", entry.get("path", "")),
            "score": round(s, 3),
            "domain": entry.get("domain", ""),
            "status": entry.get("status", ""),
        }
        for s, entry in scored[:top]
    ]


def _extract_problem_fix(content: str) -> tuple[str, str]:
    """Extract one-line problem and fix from lesson markdown content."""
    import re

    problem = ""
    fix = ""
    # Look for ## Problem / ## Root Cause / ## Symptom sections
    for section_re in [
        r"##\s*(?:Problem|Root\s*Cause|Symptom)\s*\n(.*?)(?=\n##|\Z)",
    ]:
        m = re.search(section_re, content, re.DOTALL | re.IGNORECASE)
        if m:
            for line in m.group(1).strip().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    problem = line[:120]
                    break
        if problem:
            break
    # Look for ## Solution / ## Fix / ## Workaround
    for section_re in [
        r"##\s*(?:Solution|Fix|Workaround|Resolution)\s*\n(.*?)(?=\n##|\Z)",
    ]:
        m = re.search(section_re, content, re.DOTALL | re.IGNORECASE)
        if m:
            for line in m.group(1).strip().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    fix = line[:120]
                    break
        if fix:
            break
    return problem, fix


def _freshness(date_str: str) -> str:
    """Classify lesson freshness from date string."""
    if not date_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(date_str.replace(" UTC", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
        if days < 30:
            return "fresh"
        if days < 180:
            return "recent"
        if days < 365:
            return "aging"
        return "stale"
    except (ValueError, TypeError):
        return "unknown"


def _compact_result(lesson: dict) -> dict:
    """Build compact result (~80 tokens/lesson)."""
    return {
        "id": lesson.get("id", ""),
        "title": lesson.get("title", ""),
        "problem": lesson.get("summary", "")[:120],
        "freshness": _freshness(
            lesson.get("updated", lesson.get("created", ""))
        ),
        "evidence_level": lesson.get("evidence_level", ""),
    }


def _summary_result(lesson: dict, content: str = "") -> dict:
    """Build summary result (~200 tokens/lesson)."""
    result = _compact_result(lesson)
    if content:
        problem, fix = _extract_problem_fix(content)
        result["problem"] = problem or result.get("problem", "")
        result["fix"] = fix
    result["tags"] = lesson.get("tags", [])
    result["domain"] = lesson.get("domain", "")
    return result


def _apply_detail_level(results: list[dict], detail: str) -> list[dict]:
    """Transform search results to the requested detail level."""
    if detail == "summary":
        return [_summary_result(r) for r in results]
    # compact — keep core fields, trim verbose ones
    compact = []
    for r in results:
        compact.append({
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "problem": r.get("summary", r.get("problem", ""))[:120],
            "freshness": r.get("freshness", ""),
            "evidence_level": r.get("evidence_level", ""),
            # Preserve score if present (BM25/SAG rank)
            **({"score": r["score"]} if "score" in r else {}),
        })
    return compact


def handle_search(args: dict) -> dict:
    """Search MisakaNet lessons."""
    HAS_SAG, SAG_DB, HAS_BM25, sag_search = _get_search_state()  # noqa: N806

    query = args.get("query", "")
    domain = args.get("domain")
    top = args.get("top", 5)
    explain = bool(args.get("explain", False))
    detail = args.get("detail", "compact")  # compact | summary | full

    # Per-request weight overrides (Issue #1001)
    weights = {}
    for wkey in ("bm25_weight", "metadata_weight", "baseline_weight"):
        val = args.get(wkey)
        if val is not None:
            try:
                weights[wkey] = float(val)
            except (ValueError, TypeError):
                pass

    if not query:
        return {
            "error": "query is required",
            "hint": 'Try: {"query": "python async", "domain": "core"}',
            "examples": [
                '{"query": "machine learning"}',
                '{"query": "REST API", "top": 3}',
                '{"query": "tutorial", "domain": "core"}',
            ],
            "guidance": (
                "Provide a search term (e.g. 'pip install timeout'). "
                "For broader results, try shorter keywords."
            ),
            "voice": "failure-warning",
        }

    source = ""
    results = []

    if HAS_SAG and not explain:
        results = sag_search(SAG_DB, query, domain=domain, top=top)
        source = "sag-lite"
    elif HAS_BM25:
        from misakanet.search.engine import (
            LESSONS,
            _load_docs_cached,
            _score_breakdown,
            _search_cached,
        )

        docs = _load_docs_cached(LESSONS, is_lesson=True)
        scored = _search_cached(query, docs, weights=weights or None)
        for score, doc in scored[:top]:
            result = {
                "title": doc.title,
                "path": str(doc.filepath),
                "score": round(score, 3),
                "domain": doc.domain,
                "status": doc.status,
            }
            if explain:
                result["score_breakdown"] = _score_breakdown(
                    query, doc, docs=docs
                )
            results.append(result)
        source = "bm25"
    else:
        # Fallback: lightweight keyword search from lessons.json
        results = _fallback_search(query, domain=domain, top=top)
        if results is None:
            return {
                "error": "Search engine unavailable — index not built",
                "action": (
                    "Run: python3 scripts/build_sag_index.py"
                    " to enable BM25/SAG search"
                ),
                "fallback": (
                    "Browse lessons via misaka://lessons/index"
                    " resource instead"
                ),
                "guidance": (
                    "To obtain a token or search lessons, refer to"
                    " docs/integrations/mcp-remote.md."
                ),
                "voice": "failure-warning",
            }
        source = "fallback"

    # ── Progressive disclosure: transform by detail level ──

    if results and detail in ("compact", "summary"):
        results = _apply_detail_level(results, detail)

    voice = "lesson-found" if results else "failure-warning"
    return {
        "results": results,
        "source": source,
        "detail": detail,
        "voice": voice,
    }
