"""MisakaNet search handler with progressive disclosure."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .._config import REPO_ROOT, _init_search

# ── Query-intent routing (Issue #1441) ──
_LESSON_INTENT_RE = re.compile(
    r"(lesson|lessons|learned|踩坑|记录|经验|memory|remember|preference)",
    re.IGNORECASE,
)
_EVIDENCE_INTENT_RE = re.compile(
    r"(evidence|被用过|多少人|E4|验证|verification|引用次数|usage)",
    re.IGNORECASE,
)


def _detect_kind(query: str, explicit_kind: str | None = None) -> str:
    """Detect search kind from query intent or explicit parameter.

    Priority: explicit > auto-detected > 'all'.
    """
    if explicit_kind and explicit_kind != "all":
        return explicit_kind
    if _LESSON_INTENT_RE.search(query):
        return "lessons"
    if _EVIDENCE_INTENT_RE.search(query):
        return "evidence"
    return "all"

# Gap analysis: log zero-result queries (Issue #1164)
_GAPS_FILE = REPO_ROOT / "data" / "search_gaps.jsonl"


def _log_search_gap(query: str, source: str) -> None:
    """Log a zero-result search query for gap analysis."""
    try:
        entry = {
            "query": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result_count": 0,
            "source": source,
        }
        _GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_GAPS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Non-critical, don't break search


def _no_match_feedback(query: str) -> dict:
    """Return an actionable continuation for a query with no lesson match."""
    return {
        "no_match": True,
        "query": query,
        "suggestion": (
            "No MisakaNet lesson matched this query. Call "
            "misakanet_submit_intake with kind=\"missing_lesson\" to report "
            "the knowledge gap."
        ),
        "intake": {
            "tool": "misakanet_submit_intake",
            "args": {
                "kind": "missing_lesson",
                "problem": "<short description of the failure>",
                "error": query,
                "source": "mcp",
            },
        },
    }

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


def _filter_by_kind(results: list[dict], kind: str) -> list[dict]:
    """Filter search results by kind.

    - lessons: results that are lesson files (have id/title, not pure evidence)
    - evidence: results with evidence_refs, high evidence_level, or verification
    - related: results with tag overlap or cross-references
    """
    if kind == "lessons":
        return [r for r in results if _is_lesson_result(r)]
    if kind == "evidence":
        return [r for r in results if _is_evidence_result(r)]
    if kind == "related":
        return [r for r in results if _is_related_result(r)]
    return results


def _is_lesson_result(r: dict) -> bool:
    """A result is a lesson if it has a title and path (standard lesson file)."""
    return bool(r.get("title") and r.get("path"))


def _is_evidence_result(r: dict) -> bool:
    """A result is evidence if it has evidence_refs, high evidence_level, or verification."""
    if r.get("evidence_refs"):
        return True
    ev = (r.get("evidence_level") or "").lower()
    if ev in ("verified", "confirmed", "high"):
        return True
    # Check for verification section in content
    content = (r.get("content") or r.get("summary") or "").lower()
    if "## verification" in content or "## verify" in content:
        return True
    return False


def _is_related_result(r: dict) -> bool:
    """A result is related if it has tags or cross-references."""
    if r.get("tags"):
        return True
    if r.get("related_lessons"):
        return True
    return False


def _classify_result_kind(r: dict) -> str:
    """Classify a result's kind when kind='all'."""
    if _is_evidence_result(r):
        return "evidence"
    if _is_related_result(r):
        return "related"
    return "lessons"


def handle_search(args: dict, search_state=None) -> dict:
    """Search MisakaNet lessons."""
    if search_state is None:
        search_state = _get_search_state()
    HAS_SAG, SAG_DB, HAS_BM25, sag_search = search_state  # noqa: N806

    query = args.get("query", "")
    domain = args.get("domain")
    top = args.get("top", 5)
    explain = bool(args.get("explain", False))
    detail = args.get("detail", "compact")  # compact | summary | full
    kind = _detect_kind(query, args.get("kind"))
    include_stale = bool(args.get("include_stale", False))

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
        scored = _search_cached(query, docs, weights=weights or None, include_stale=include_stale)
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

    # ── Kind filtering (Issue #1441) ──
    if results and kind != "all":
        results = _filter_by_kind(results, kind)

    # ── Progressive disclosure: transform by detail level ──

    if results and detail in ("compact", "summary"):
        results = _apply_detail_level(results, detail)

    # ── Gap analysis: log zero-result queries (Issue #1164) ──
    if not results:
        _log_search_gap(query, source)

    # Tag each result with its kind
    for r in results:
        if "kind" not in r:
            r["kind"] = kind if kind != "all" else _classify_result_kind(r)

    voice = "lesson-found" if results else "failure-warning"
    response = {
        "results": results,
        "source": source,
        "detail": detail,
        "kind": kind,
        "voice": voice,
    }
    if not results:
        response.update(_no_match_feedback(query))
    return response
