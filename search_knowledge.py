#!/usr/bin/env python3
"""CLI thin wrapper — core implementation in misakanet/search/engine.py

Search modes:
    python3 search_knowledge.py "pip timeout"            # local repo BM25 (needs clone)
    python3 search_knowledge.py "pip timeout" --remote   # D1 service (PRD ④, no clone)

Ecosystem links:
    from misakanet_core import BM25, tokenize, rrf
"""
import contextlib
import io
import json
import sys
import time
import re
from pathlib import Path
from typing import Optional

# ── 生态核心声明 ──
from misakanet_core import BM25 as _  # noqa: F401  (ecosystem assertion)

try:
    from misakanet.search.engine import *
except ImportError as e:
    if "misakanet_core" in str(e):
        print("Error: 'misakanet-core' is required. Run: pip install misakanet-core", file=sys.stderr)
        sys.exit(1)
    raise
from misakanet.cli.heal import _read_log, heal
from misakanet.tools.lesson_scorer import DEFAULT_TELEMETRY, format_lesson_scores, score_lessons
from misakanet.cli.remote import _load_docs_anywhere, _load_remote_docs
from misakanet.cli.typo import (
    _edit_distance,
    _find_closest_matches,
    _log_zero_result,
    _smart_fallback,
    _suggest_relaxed_query,
    _typo_retry_search,
)


def _json_result(score, doc, query: str = "", verbose: bool = False) -> dict:
    """Convert a ranked document to the stable public JSON schema."""
    from misakanet.search.engine import (
        REPO,
        _classify_confidence,
        _classify_result_type,
        _get_match_reason,
        _get_preview,
        _get_why_matched,
        _highlight_plain,
        _score_breakdown,
    )

    try:
        path = doc.filepath.relative_to(REPO).as_posix()
    except ValueError:
        path = doc.filepath.as_posix()
    preview = _get_preview(doc.content, max_chars=120)
    result = {
        "title": doc.title,
        "domain": doc.domain,
        "tags": list(doc.tags),
        "score": round(float(score), 6),
        "path": path,
        "preview": preview,
    }
    if query:
        from misakanet.search.engine import _get_search_boost, _get_signal_level
        match_reason = _get_match_reason(query, doc, score)
        result["match_reason"] = match_reason
        result["preview_highlighted"] = _highlight_plain(preview, query)
        confidence = _classify_confidence(doc, query, match_reason, score)
        result_type = _classify_result_type(doc, confidence)
        signal_level = _get_signal_level(doc, confidence)
        result["confidence"] = confidence
        result["result_type"] = result_type
        result["signal_level"] = signal_level
        result["search_boost"] = round(_get_search_boost(signal_level, confidence), 2)
        result["why_matched"] = _get_why_matched(match_reason)
    if verbose and query:
        result["score_breakdown"] = _score_breakdown(query, doc)
    # Freshness badge (tier info)
    try:
        from misakanet.freshness import compute_freshness_from_content
        freshness = compute_freshness_from_content(doc.content)
        result["freshness"] = {
            "score": freshness["score"],
            "tier": freshness["tier"]["tier"],
            "badge": freshness["tier"]["badge"],
        }
    except Exception:
        pass  # freshness is non-critical
    return result


def _print_json_error(message: str) -> None:
    """Emit a machine-readable error without contaminating it with CLI prose."""
    print(json.dumps({"error": message}, ensure_ascii=False))


def _ensure_utf8_stdout():
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass


def _feedback_log_path() -> Path:
    """Path for durable local search feedback (no PII; query + result ids only)."""
    return Path(__file__).resolve().parent / "data" / "search-feedback.jsonl"


def _collect_feedback(query: str, result_ids: list) -> None:
    """Prompt for search usefulness and append one JSONL record.

    Acceptance (issue #604):
    - Prompt: Was this helpful? (y/n/comment)
    - Log to data/search-feedback.jsonl: query, results shown, feedback, timestamp
    - No external dependencies; no PII beyond the free-text comment the user typed
    """
    import datetime

    print()
    try:
        answer = input("  Was this helpful? (y/n/comment): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not answer:
        return

    # Normalize short answers; keep free-text comments capped
    if answer.lower() in ("y", "yes"):
        feedback = "helpful"
    elif answer.lower() in ("n", "no"):
        feedback = "not_helpful"
    else:
        feedback = answer[:200]

    # Stable result identifiers only (filenames / lesson ids — not user data)
    clean_ids: list[str] = []
    for rid in result_ids or []:
        s = str(rid).strip()
        if s:
            clean_ids.append(s[:200])

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "query": (query or "")[:500],
        "results": clean_ids,
        "feedback": feedback,
    }

    try:
        log_path = _feedback_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"  ✅ Feedback logged to {log_path.relative_to(Path(__file__).resolve().parent)}. Thank you!")
    except OSError as e:
        print(f"  ⚠️  Could not log feedback: {e}", file=sys.stderr)


def main():
    _ensure_utf8_stdout()
    args = sys.argv[1:]
    # ── Harvest mode: log → lesson draft prototype ──
    if "--harvest" in args or args[:1] == ["harvest"]:
        from misakanet.cli.harvest import run_harvest
        run_harvest(args)
        return
    # ── GraphQL mode: interactive query playground ──
    if "--graphql" in args:
        from misakanet.cli.graphql_repl import run_graphql_repl
        run_graphql_repl(args)
        return
    # ── Heal mode: diagnose error logs ──
    use_heal = "--heal" in args
    heal_source = ""
    for i, arg in enumerate(args):
        if arg == "--heal" and i + 1 < len(args) and not args[i + 1].startswith("--"):
            heal_source = args[i + 1]
        elif arg.startswith("--from-file="):
            heal_source = arg.split("=", 1)[1]
        elif arg == "--from-file" and i + 1 < len(args):
            heal_source = args[i + 1]

    if use_heal:
        write_fixtures = "--write" in args  # audit 2026-09-05 QW5: fixtures opt-in
        log = _read_log(heal_source)
        heal(log, write_fixtures=write_fixtures)
        return

    if "--score" in args:
        top_k = None
        telemetry_path = DEFAULT_TELEMETRY
        for i, arg in enumerate(args):
            if arg.startswith("--top="):
                try:
                    top_k = int(arg.split("=", 1)[1])
                except ValueError:
                    pass
            elif arg == "--top" and i + 1 < len(args):
                try:
                    top_k = int(args[i + 1])
                except ValueError:
                    pass
            elif arg.startswith("--telemetry="):
                telemetry_path = arg.split("=", 1)[1]
        print(format_lesson_scores(score_lessons(telemetry_path), limit=top_k))
        return

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    json_output = "--json" in args
    positional_args = [arg for arg in args if arg != "--json"]
    if not positional_args or positional_args[0].startswith("--"):
        if json_output:
            _print_json_error("a search query is required")
        else:
            print(__doc__)
        sys.exit(1)
    query = positional_args[0]
    mode = "all"
    titles_only = False
    broad_only = False
    top_k = 10
    use_semantic = False
    use_rerank = False
    suggest = False
    explain = False
    verbose = False
    agent_mode = False
    strict = False
    use_feedback = False
    remote = "--remote" in args
    env_filter: Optional[str] = None
    lang: Optional[str] = None
    domain: Optional[str] = None
    status_filter: Optional[str] = None
    tags_filter: list[str] = []
    search_args = positional_args[1:]
    for i, arg in enumerate(search_args):
        if arg == "--ref":
            mode = "ref"
        elif arg == "--lessons":
            mode = "lessons"
        elif arg == "--titles":
            titles_only = True
        elif arg == "--broad":
            broad_only = True
        elif arg == "--suggest":
            suggest = True
        elif arg.startswith("--top="):
            try:
                top_k = int(arg.split("=")[1])
            except ValueError:
                pass
        elif arg == "--top" and i + 1 < len(search_args):
            try:
                top_k = int(search_args[i + 1])
            except ValueError:
                pass
        elif arg.startswith("--lang="):
            lang = arg.split("=", 1)[1]
        elif arg == "--lang" and i + 1 < len(search_args):
            lang = search_args[i + 1]
        elif arg == "--semantic":
            use_semantic = True
        elif arg == "--rerank":
            use_rerank = True
        elif arg.startswith("--domain="):
            domain = arg.split("=", 1)[1].lower()
        elif arg == "--domain" and i + 1 < len(search_args):
            domain = search_args[i + 1].lower()
        elif arg.startswith("--status="):
            status_filter = arg.split("=", 1)[1].lower()
        elif arg == "--status" and i + 1 < len(search_args):
            status_filter = search_args[i + 1].lower()
        elif arg.startswith("--tags="):
            tags_filter = [t.strip().lower() for t in arg.split("=", 1)[1].split(",")]
        elif arg == "--tags" and i + 1 < len(search_args):
            tags_filter = [t.strip().lower() for t in search_args[i + 1].split(",")]
        elif arg == "--explain":
            explain = True
        elif arg == "--verbose":
            verbose = True
            explain = True
        elif arg == "--agent":
            agent_mode = True
        elif arg == "--strict":
            strict = True
        elif arg == "--feedback":
            use_feedback = True
        elif arg.startswith("--env="):
            env_filter = arg.split("=", 1)[1].lower()
        elif arg == "--env" and i + 1 < len(search_args):
            env_filter = search_args[i + 1].lower()
    # ── 轻量配额检查 ──
    # Remote mode queries the D1 service, whose quota (5 free reads/day per
    # IP, PRD ④) is enforced server-side — skip the local node quota so a
    # fresh clone without a profile can still search.
    if not remote:
        from misakanet.profile import check_quota as _check_quota
        allowed, quota_msg = _check_quota()
        if not allowed:
            if json_output:
                _print_json_error(quota_msg)
            else:
                print(quota_msg, file=sys.stderr)
            sys.exit(1)
        if quota_msg and not json_output:
            print(quota_msg, file=sys.stderr)
            print("", file=sys.stderr)

    t0 = time.time()
    found_any = False
    # Result ids shown this run (for --feedback jsonl). Filenames only, no PII.
    shown_result_ids: list[str] = []

    # --suggest mode: list matching titles when query >= 2 chars
    if suggest and len(query) >= 2 and not json_output:
        q = query.lower()
        lessons_docs = _load_docs_anywhere(mode, remote) if mode in ("all", "lessons") else []
        ref_docs = _load_docs(REFERENCES, is_lesson=False) if mode in ("all", "ref") else []
        all_docs = lessons_docs + ref_docs
        matches = []
        for d in all_docs:
            if q in d.title.lower() or q in d.domain.lower():
                matches.append(d)
        if matches:
            print("  Suggestions:")
            for d in matches[:top_k]:
                tag = f"[{d.domain}]" if d.domain else ""
                print(f"    {tag:<18} {d.title}")
        else:
            print(f"  (No matches)")
        _show_timing(time.time() - t0, len(all_docs))
        return

    # Cache migrations can report status to stdout. Capture those messages in
    # JSON mode so stdout remains directly pipeable to jq.
    output_context = contextlib.redirect_stdout(io.StringIO()) if json_output else contextlib.nullcontext()
    with output_context:
        lessons_docs = _load_docs_anywhere(mode, remote) if mode in ("all", "lessons") else []
        ref_docs = _load_docs(REFERENCES, is_lesson=False) if mode in ("all", "ref") else []

    # Language filter
    if lang:
        lessons_docs = [d for d in lessons_docs if d.language == lang]
        ref_docs = [d for d in ref_docs if d.language == lang]
        if not json_output:
            print(f"  🌐 Filtering by language: {lang}")

    # Domain filter (fix #229)
    if domain:
        lessons_docs = [d for d in lessons_docs if d.domain and d.domain.lower() == domain]
        ref_docs = [d for d in ref_docs if d.domain and d.domain.lower() == domain]
        if not json_output:
            print(f"  🏷️  Filtering by domain: {domain}")

    # Environment filter (--env)
    if env_filter:
        lessons_docs = [d for d in lessons_docs if any(env_filter in t.lower() for t in d.tags)]
        ref_docs = [d for d in ref_docs if any(env_filter in t.lower() for t in d.tags)]
        if not json_output:
            print(f"  💻 Filtering by environment: {env_filter}")

    # Status filter (fix #308)
    if status_filter:
        lessons_docs = [d for d in lessons_docs if d.status and d.status.lower() == status_filter]
        ref_docs = [d for d in ref_docs if d.status and d.status.lower() == status_filter]
        if not json_output:
            print(f"  📋 Filtering by status: {status_filter}")

    # Tags filter (fix #308) - AND logic
    if tags_filter:
        lessons_docs = [d for d in lessons_docs if d.tags and all(t.lower() in [tag.lower() for tag in d.tags] for t in tags_filter)]
        ref_docs = [d for d in ref_docs if d.tags and all(t.lower() in [tag.lower() for tag in d.tags] for t in tags_filter)]
        if not json_output:
            print(f"  🏷️  Filtering by tags (AND): {', '.join(tags_filter)}")

    if json_output:
        all_docs = lessons_docs + ref_docs
        with contextlib.redirect_stdout(io.StringIO()):
            ranked = _rank_docs(query, all_docs, titles_only, broad_only)
        results = [
            _json_result(score, doc, query=query, verbose=verbose)
            for score, doc in ranked
            if score >= 0.1
        ]
        # Feature #314: Typo tolerance for JSON mode
        if not results and not strict:
            typo_results, corrected = _typo_retry_search(
                query, all_docs, titles_only, broad_only, top_k
            )
            if typo_results:
                results = [
                    _json_result(score, doc, query=corrected, verbose=verbose)
                    for score, doc in typo_results
                ]
                for r in results:
                    r["typo_corrected"] = True
                    r["original_query"] = query
                    r["corrected_query"] = corrected
        # Agent mode: only return actionable/high-confidence results
        if agent_mode:
            results = [r for r in results if r.get("result_type") == "actionable" and r.get("confidence") != "low"]
        results = results[:top_k]
        if results and not remote:
            from misakanet.profile import increment_search, consume_quota
            increment_search()
            consume_quota()
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if use_semantic:
        try:
            from misakanet.search.embeddings import generate_embedding
            from misakanet.search.embeddings import embedding_service_health
            health = embedding_service_health()
            if health.get("status") == "ok":
                print("  🔬 Semantic search enabled")
            else:
                print(f"  ⚠️ --semantic degraded: {health.get('message', 'backend unavailable')}")
                print("  ⚠️ Falling back to BM25 — semantic search is not available")
                use_semantic = False
        except ImportError:
            print("  ⚠️ --semantic requires sentence-transformers and misakanet.search.embeddings")
            print("  ⚠️ Falling back to BM25")
            use_semantic = False
    MIN_SCORE_THRESHOLD = 0.1  # Minimum score to consider as "found"
    
    all_docs = lessons_docs + ref_docs
    if lessons_docs:
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only, rerank=use_rerank)
        # Only show results above threshold
        filtered = [(s, d) for s, d in ranked if s >= MIN_SCORE_THRESHOLD]
        for _score, doc in filtered[:top_k]:
            rid = getattr(doc, "filename", None) or getattr(doc, "title", None) or ""
            if rid:
                shown_result_ids.append(str(rid))
        found = _format_output(filtered, titles_only, top_k,
                               mode_label=f"lessons/  (All {len(lessons_docs)} items)",
                               query=query, explain=explain,
                               all_docs=all_docs)
        found_any = found_any or found
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False, rerank=use_rerank)
        # Only show results above threshold
        filtered = [(s, d) for s, d in ranked if s >= MIN_SCORE_THRESHOLD]
        for _score, doc in filtered[:top_k]:
            rid = getattr(doc, "filename", None) or getattr(doc, "title", None) or ""
            if rid:
                shown_result_ids.append(str(rid))
        found = _format_output(filtered, titles_only, top_k,
                               mode_label=f"reference/  (All {len(ref_docs)} items)",
                               query=query, explain=explain,
                               all_docs=all_docs)
        found_any = found_any or found
    total_docs = len(lessons_docs) + len(ref_docs)
    if not found_any and not strict:
        # Feature #314: Typo tolerance — retry with edit distance ≤2
        all_docs_for_typo = lessons_docs + ref_docs
        typo_results, corrected = _typo_retry_search(
            query, all_docs_for_typo, titles_only, broad_only, top_k
        )
        if typo_results:
            print(f"\n  🔍 Showing results for '{corrected}' (searched: '{query}')\n")
            for score, doc in typo_results:
                tag = f"[{doc.domain}]" if doc.domain else ""
                title = doc.title[:60] or doc.filename
                print(f"  {score:.3f}  {tag:<18} {title}")
                rid = getattr(doc, "filename", None) or title
                if rid:
                    shown_result_ids.append(str(rid))
            found_any = True
    if not found_any:
        # Feature #301: Smart fallback with closest matches
        _smart_fallback(query, lessons_docs + ref_docs)

        # Log zero-result query for gap analysis
        _log_zero_result(query)
    _show_timing(time.time() - t0, total_docs)
    if found_any and not suggest and not remote:
        from misakanet.profile import increment_search, consume_quota
        increment_search()
        consume_quota()
    if found_any:
        if remote:
            print(f"  💡 Full content: https://misakanet.org/lessons/<slug>/  (or MCP misakanet_get_lesson)")
        else:
            print(f"  💡 View full content: cat lessons/<filename>.md")
        print(f"  💡 Contribute new knowledge: python3 scripts/queue_lesson.py -t 'title' -d domain 'content...'")
        if use_feedback and not json_output:
            _collect_feedback(query, shown_result_ids)
        print()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        if "--json" in sys.argv:
            _print_json_error(str(exc))
            raise SystemExit(1)
        raise

