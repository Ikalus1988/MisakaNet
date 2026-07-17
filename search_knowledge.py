#!/usr/bin/env python3
"""CLI thin wrapper — core implementation in misakanet/search/engine.py

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
from misakanet.tools.lesson_scorer import DEFAULT_TELEMETRY, format_lesson_scores, score_lessons


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


# ── Heal mode: parse error logs, search lessons, return diagnosis ──
# 4-level cascading fallback: traceback → error signature → exit code → last N lines

# ANSI escape sequence pattern
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _strip_ansi(text: str) -> str:
    """Remove ANSI color codes from log text."""
    return _ANSI_RE.sub('', text)


def _parse_error_signature(log_text: str) -> str:
    """
    4-level cascading error signature extractor.
    Returns the most specific error signature found.
    """
    text = _strip_ansi(log_text)

    # Level 1: Traceback — find the last exception line
    tb_matches = re.findall(r'(?:[a-zA-Z0-9_]+Error|Exception|RuntimeError|Warning|Fault):\s*.+', text)
    if tb_matches:
        return tb_matches[-1]

    # Level 2: ERROR / Error: <message>
    err_match = re.search(r'(?:Error|ERROR|FATAL|CRITICAL):\s*(.+)', text)
    if err_match:
        return err_match.group(0)

    # Level 3: exit code / status
    exit_match = re.search(r'(?:exit code\s*|status\s*|returned\s*)(-?\d+)', text, re.IGNORECASE)
    if exit_match:
        return f"Process failed with exit code {exit_match.group(1)}"

    # Level 4: last 5 non-empty lines as raw keyword block
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return " ".join(lines[-5:]) if lines else text[:500]


def _read_log(source: str = "") -> str:
    """Read log from file or stdin. Caps at last 200 lines for safety."""
    if source:
        with open(source, 'r', errors='replace') as f:
            lines = f.readlines()
    else:
        print("[MisakaNet] 📡 Reading error log from stdin (pipe your agent's stderr)...", file=sys.stderr)
        lines = sys.stdin.readlines()

    if len(lines) > 200:
        lines = lines[-200:]

    return "".join(lines)


def _extract_all_signatures(log_text: str) -> list[str]:
    """Extract ALL error signatures from log (not just the last one)."""
    text = _strip_ansi(log_text)
    sigs = []

    # Level 1: all traceback exceptions
    tb_matches = re.findall(r'(?:[a-zA-Z0-9_]+Error|Exception|RuntimeError|Fault):\s*.+', text)
    sigs.extend(tb_matches)

    # Level 2: ERROR / FATAL / CRITICAL markers
    err_matches = re.findall(r'(?:^|\n)(?:\[?\s*(?:Error|ERROR|FATAL|CRITICAL)\s*\]?):\s*(.+)', text)
    sigs.extend([f"ERROR: {m.strip()}" for m in err_matches])

    # Level 3: exit codes
    exit_match = re.search(r'(?:exit code\s*|status\s*|returned\s*)(-?\d+)', text, re.IGNORECASE)
    if exit_match:
        sigs.append(f"Process failed with exit code {exit_match.group(1)}")

    # Fallback: if nothing found, use raw last lines
    if not sigs:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        sigs.append(" ".join(lines[-5:]) if lines else text[:500])

    # Deduplicate while preserving order
    seen = set()
    return [s for s in sigs if not (s in seen or seen.add(s))]


def heal(raw_log: str):
    """Diagnose error log: extract signatures → search lessons → coverage report."""
    # Step 1: Extract all error signatures
    signatures = _extract_all_signatures(raw_log)
    if not signatures or all(len(s.strip()) < 3 for s in signatures):
        print("[MisakaNet] ❌ No valid error patterns captured from input.")
        return

    print(f"\n[MisakaNet] 🔍 Extracted {len(signatures)} error signature(s)")
    print("-" * 50)

    # Step 2: Search lessons using existing BM25 engine
    from misakanet.search.engine import (
        _load_docs, _rank_docs, _format_output, _show_timing,
        LESSONS, REFERENCES,
    )

    t0 = time.time()
    lessons_docs = _load_docs(LESSONS, is_lesson=True)
    ref_docs = _load_docs(REFERENCES, is_lesson=False)
    all_docs = lessons_docs + ref_docs

    # ⑤ Coverage dashboard: track matched vs unmatched signatures
    import os
    import hashlib

    matched_count = 0
    unmatched_count = 0
    fixture_dir = "tests/fixtures/openclaw"

    for sig in signatures:
        ranked = _rank_docs(sig, all_docs, titles_only=False, broad_only=True)
        has_match = ranked and ranked[0][0] > 0.15  # meaningful match threshold

        if has_match:
            matched_count += 1
            top_score = ranked[0][0]
            top_title = ranked[0][1].title
            print(f"  ✅ [{top_score:.0%}] {sig[:80]}")
            print(f"      → matched: {top_title}")
        else:
            unmatched_count += 1
            print(f"  ❌ [uncovered] {sig[:80]}")

            # ⑥ Auto-generate fixture for unmatched signatures
            sig_hash = hashlib.md5(sig.encode()).hexdigest()[:8]
            os.makedirs(fixture_dir, exist_ok=True)
            fixture_path = os.path.join(fixture_dir, f"unmatched_{sig_hash}.log")
            with open(fixture_path, "w") as f:
                f.write(raw_log)
            print(f"      → fixture: {fixture_path}")

    # Coverage summary
    total = matched_count + unmatched_count
    coverage = (matched_count / total * 100) if total > 0 else 0
    print()
    print(f"  📊 Coverage: {matched_count}/{total} signatures matched ({coverage:.1f}%)")
    if coverage < 50:
        print(f"     ⚠️  Low coverage — consider submitting lessons for the unmatched signatures")
    print("-" * 50)

    # Show top results for primary signature
    primary_sig = signatures[0]
    ranked = _rank_docs(primary_sig, all_docs, titles_only=False, broad_only=True)
    found = _format_output(ranked, titles_only=False, top_k=5,
                           mode_label=f"lessons+reference  (All {len(all_docs)} items)",
                           query=primary_sig, explain=False,
                           all_docs=all_docs)
    _show_timing(time.time() - t0, len(all_docs))

    if unmatched_count > 0:
        print(f"\n  📝 {unmatched_count} unmatched signature(s) — auto-generated fixtures in {fixture_dir}/")
        print(f"     Submit a lesson to improve coverage:")
        print(f"     python3 scripts/queue_lesson.py -t 'your title' -d openclaw -f {fixture_dir}/unmatched_*.log")
    elif found:
        print(f"\n  ✅ All signatures covered by swarm knowledge.")
        print(f"     💡 Contribute back if you applied a new fix:")
        print(f"        python3 scripts/queue_lesson.py -t 'your title' -d <domain> 'content...'")

    print()


def _edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance — O(len(s1)*len(s2))."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(s2)]


def _typo_retry_search(
    query: str, docs: list, titles_only: bool, broad_only: bool, top_k: int
) -> tuple[list[tuple[float, object]], str]:
    """Retry search with edit-distance fuzzy matching on title keywords.

    For each query token, find title tokens within edit distance ≤2.
    Build a corrected query from the best matches, then re-rank.
    Returns (ranked_results, corrected_query) or ([], original_query).
    """
    query_tokens = query.lower().split()
    if not query_tokens:
        return [], query

    # Build vocabulary from all doc titles
    title_vocab: dict[str, list[str]] = {}  # token -> [original forms]
    for doc in docs:
        for tok in re.findall(r'\w+', doc.title.lower()):
            if len(tok) >= 2:
                title_vocab.setdefault(tok, []).append(tok)

    # For each query token, find best fuzzy match in title vocab
    corrected_tokens = []
    has_correction = False
    for qt in query_tokens:
        if qt in title_vocab:
            corrected_tokens.append(qt)
            continue
        best_dist = 999
        best_match = qt
        for vocab_tok in title_vocab:
            # Skip if length difference > 2 (pruning for speed)
            if abs(len(vocab_tok) - len(qt)) > 2:
                continue
            dist = _edit_distance(qt, vocab_tok)
            if dist <= 2 and dist < best_dist:
                best_dist = dist
                best_match = vocab_tok
        corrected_tokens.append(best_match)
        if best_match != qt:
            has_correction = True

    if not has_correction:
        return [], query

    corrected_query = " ".join(corrected_tokens)
    from misakanet.search.engine import _rank_docs_impl
    ranked = _rank_docs_impl(corrected_query, docs, titles_only, broad_only)
    filtered = [(s, d) for s, d in ranked if s >= 0.1]
    if not filtered:
        return [], query
    return filtered[:top_k], corrected_query


def _find_closest_matches(query: str, docs: list, top_n: int = 3) -> list:
    """Find closest matches by keyword overlap scoring."""
    query_words = set(re.findall(r'\w+', query.lower()))
    if not query_words:
        return []

    scored = []
    for doc in docs:
        doc_words = set(re.findall(r'\w+', (doc.title + " " + doc.content[:500]).lower()))
        if not doc_words:
            continue
        overlap = len(query_words & doc_words)
        if overlap > 0:
            score = overlap / len(query_words)
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]


def _suggest_relaxed_query(query: str) -> list:
    """Suggest relaxed queries by dropping stop words."""
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "being", "have", "has", "had", "do", "does", "did", "will",
                  "would", "could", "should", "may", "might", "can", "shall",
                  "of", "in", "on", "at", "to", "for", "with", "by", "from",
                  "as", "into", "through", "during", "before", "after", "and",
                  "but", "or", "not", "so", "very", "just", "than", "too"}
    words = query.lower().split()
    meaningful = [w for w in words if w not in stop_words]
    if len(meaningful) >= 2:
        # Suggest dropping last word
        return [" ".join(meaningful[:-1])]
    if len(meaningful) == 1:
        return [meaningful[0]]
    return []


def _log_zero_result(query: str):
    """Log zero-result query for gap analysis."""
    import datetime
    log_dir = Path.home() / ".misakanet"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "search_telemetry.jsonl"

    entry = {
        "query": query,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "result": "zero",
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Non-critical, don't fail search

    # Check if same query failed >3 times → suggest creating issue
    try:
        if log_file.exists():
            lines = log_file.read_text(encoding="utf-8").strip().split("\n")
            count = sum(1 for l in lines if f'"query": "{query}"' in l)
            if count >= 3:
                print(f"  ⚠️  This query has returned 0 results {count} times.")
                print(f"     Consider creating an issue for a missing lesson:")
                print(f"     https://github.com/Ikalus1988/MisakaNet/issues/new?title=Missing+lesson:+{query.replace(' ', '+')}")
                print()
    except Exception:
        pass


def _smart_fallback(query: str, docs: list):
    """Smart fallback when search returns 0 results."""
    print(f"\n  ❌ No exact match for '{query}'")
    print()

    # 1. Top-3 closest matches by keyword overlap
    closest = _find_closest_matches(query, docs, top_n=3)
    if closest:
        print(f"  📋 Closest matches:")
        for score, doc in closest:
            title = doc.title[:60] or doc.filename
            print(f"     [{score:.0%}] {title}")
        print()

    # 2. "Did you mean: ..." with relaxed query
    suggestions = _suggest_relaxed_query(query)
    if suggestions:
        print(f"  💡 Did you mean: \"{suggestions[0]}\"?")
        print()

    # 3. Domain suggestions
    all_domains = {d.domain.lower() for d in docs if d.domain}
    q = query.lower()
    domain_matches = [d for d in all_domains if d in q or q in d]
    if domain_matches:
        print(f"  💡 Try domain filter:")
        for dm in domain_matches[:3]:
            print(f"     --domain {dm}")

    # 4. Broad mode hint
    print(f"  💡 Try broader search: --broad or --ref")

    # 5. Contribution link
    print(f"  💡 Add new knowledge:")
    print(f"     python3 scripts/queue_lesson.py -t \"{query}\" ...")

    # 6. Available domains
    if all_domains:
        top_domains = sorted(all_domains)[:8]
        print(f"  💡 Available domains: {', '.join(top_domains)}")

    print()


def main():
    _ensure_utf8_stdout()
    args = sys.argv[1:]
    if "--harvest" in args or args[:1] == ["harvest"]:
        # Parse --from-file
        harvest_file = ""
        for i, arg in enumerate(args):
            if arg.startswith("--from-file="):
                harvest_file = arg.split("=", 1)[1]
            elif arg == "--from-file" and i + 1 < len(args):
                harvest_file = args[i + 1]

        if harvest_file:
            _harvest_from_file(harvest_file)
        else:
            print("🌾 misaka harvest: Knowledge Harvester")
            print()
            print("  Usage:")
            print("    python3 search_knowledge.py --harvest --from-file <path>")
            print()
            print("  Planned interfaces:")
            print("    misaka harvest --bash-history    Scan $HISTFILE")
            print("    misaka harvest --pipe             Accept stdin")
            print()
            print("  See misaka-protocol.json → ecosystem.tools.harvester for spec.")
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
        log = _read_log(heal_source)
        heal(log)
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
    suggest = False
    explain = False
    verbose = False
    agent_mode = False
    strict = False
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
        elif arg.startswith("--env="):
            env_filter = arg.split("=", 1)[1].lower()
        elif arg == "--env" and i + 1 < len(search_args):
            env_filter = search_args[i + 1].lower()
    # ── 轻量配额检查 ──
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

    # --suggest mode: list matching titles when query >= 2 chars
    if suggest and len(query) >= 2 and not json_output:
        q = query.lower()
        lessons_docs = _load_docs(LESSONS, is_lesson=True) if mode in ("all", "lessons") else []
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
        lessons_docs = _load_docs(LESSONS, is_lesson=True) if mode in ("all", "lessons") else []
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
        if results:
            from misakanet.profile import increment_search, consume_quota
            increment_search()
            consume_quota()
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if use_semantic:
        try:
            from hub.storage.vector_store import generate_embedding
            from hub.storage.vector_store import embedding_service_health
            health = embedding_service_health()
            if health.get("status") == "ok":
                print("  🔬 Semantic search enabled")
            else:
                print(f"  ⚠️ --semantic degraded: {health.get('message', 'backend unavailable')}")
                print("  ⚠️ Falling back to BM25 — semantic search is not available")
                use_semantic = False
        except ImportError:
            print("  ⚠️ --semantic requires sentence-transformers and hub.storage.vector_store")
            print("  ⚠️ Falling back to BM25")
            use_semantic = False
    MIN_SCORE_THRESHOLD = 0.1  # Minimum score to consider as "found"
    
    all_docs = lessons_docs + ref_docs
    if lessons_docs:
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only)
        # Only show results above threshold
        filtered = [(s, d) for s, d in ranked if s >= MIN_SCORE_THRESHOLD]
        found = _format_output(filtered, titles_only, top_k,
                               mode_label=f"lessons/  (All {len(lessons_docs)} items)",
                               query=query, explain=explain,
                               all_docs=all_docs)
        found_any = found_any or found
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False)
        # Only show results above threshold
        filtered = [(s, d) for s, d in ranked if s >= MIN_SCORE_THRESHOLD]
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
            found_any = True
    if not found_any:
        # Feature #301: Smart fallback with closest matches
        _smart_fallback(query, lessons_docs + ref_docs)

        # Log zero-result query for gap analysis
        _log_zero_result(query)
    _show_timing(time.time() - t0, total_docs)
    if found_any and not suggest:
        from misakanet.profile import increment_search, consume_quota
        increment_search()
        consume_quota()
    if found_any:
        print(f"  💡 View full content: cat lessons/<filename>.md")
        print(f"  💡 Contribute new knowledge: python3 scripts/queue_lesson.py -t 'title' -d domain 'content...'")
        print()


def _harvest_from_file(filepath: str):
    """Log Harvester prototype — parse error log and generate lesson draft."""
    from pathlib import Path
    import datetime as _dt
    path = Path(filepath)
    if not path.exists():
        print(f"❌ File not found: {filepath}")
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Extract lines that look like errors
    error_patterns = [
        r"(error|exception|traceback|failed|failure|fatal|crash|timeout|denied|not\s+found)",
        r"(killed|segfault|oom|out\s+of\s+memory|disk\s+full|permission\s+denied)",
        r"(exit\s+code\s+[1-9]|returned\s+non-zero|signal\s+\d+)",
        r"(traceback|most recent call last)",
    ]
    combined = re.compile("|".join(error_patterns), re.IGNORECASE)
    
    error_lines = []
    for i, line in enumerate(lines, 1):
        if combined.search(line):
            # Include a few lines of context
            start = max(0, i - 2)
            context = lines[start:i]
            error_lines.append((i, line.strip(), context))
    
    if not error_lines:
        print(f"⚠️  No error patterns found in {filepath}")
        print("   Try with a log file, error output, or stack trace.")
        return
    
    # Generate lesson draft
    query = path.stem.replace("-", " ").replace("_", " ")
    print("🌾 Harvest complete!")
    print()
    
    # Show first 10 errors
    print(f"📋 Found {len(error_lines)} error lines (showing first 10):")
    for lineno, line, _ in error_lines[:10]:
        print(f"  L{lineno}: {line[:120]}")
    print()
    
    # Generate SKP-compliant lesson draft
    print("=" * 50)
    print("📝 Generated Lesson Draft")
    print("=" * 50)
    print(f"""---
{{"title": "Fix: {query[:80]}", "domain": "general", "tags": ["harvester", "auto-generated"], "status": "draft", "created": "{_dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", "source": "harvester"}}
---

## Problem

Error encountered during `{query[:60]}`.

## Root Cause

"""
    )
    
    # Show first error as context
    first_line = error_lines[0][1]
    print(f"```text")
    for ctx_line in error_lines[0][2]:
        print(ctx_line[:200])
    print(error_lines[0][1][:200])
    print(f"```")
    print()
    print("## Solution")
    print()
    print("<!-- TODO: describe the fix -->")
    print()
    print("## Verification")
    print()
    print("<!-- TODO: add verification steps -->")
    print()
    print("## Notes")
    print()
    print(f"Auto-harvested from: {filepath}")
    print()
    print("=" * 50)
    print("💡 Save to lessons/ with:")
    print(f'   mv <this-output> lessons/contrib/{path.stem}.md')
    print("   Then run: python3 scripts/contribute.py lessons/contrib/<file>.md")


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
