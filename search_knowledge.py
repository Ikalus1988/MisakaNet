#!/usr/bin/env python3
"""CLI thin wrapper — core implementation in misakanet/search/engine.py

Ecosystem links:
    from misakanet_core import BM25, tokenize, rrf
"""
import sys
import time
import re

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


def heal(raw_log: str):
    """Diagnose error log: extract signature → search lessons → output."""
    # Step 1: Extract error signature
    query = _parse_error_signature(raw_log)
    if not query or len(query.strip()) < 3:
        print("[MisakaNet] ❌ No valid error pattern captured from input.")
        return

    print(f"\n[MisakaNet] 🔍 Error signature: {query}")
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

    ranked = _rank_docs(query, all_docs, titles_only=False, broad_only=True)
    found = _format_output(ranked, titles_only=False, top_k=5,
                           mode_label=f"lessons+reference  (All {len(all_docs)} items)",
                           query=query)
    _show_timing(time.time() - t0, len(all_docs))

    if found:
        print()
        print(f"  💡 Did this resolve your issue? If you applied a new fix,")
        print(f"     contribute back to the swarm:")
        print(f"     python3 scripts/queue_lesson.py -t 'your title' -d <domain> 'content...'")
    else:
        print(f"\n  📝 No matching lesson found for this error.")
        print(f"     This means your issue hasn't been documented yet.")
        print(f"     Contribute it to help others:")
        print(f"     python3 scripts/queue_lesson.py -t 'your title' -d <domain> 'content...'")

    print()


def main():
    _ensure_utf8_stdout()
    args = sys.argv[1:]
    if "--harvest" in args or args[:1] == ["harvest"]:
        print("🌾 misaka harvest: Knowledge Harvester (planned)")
        print()
        print("  Auto-generate SKP-compliant lessons from terminal history or logs.")
        print()
        print("  Planned interfaces:")
        print("    misaka harvest --bash-history    Scan $HISTFILE")
        print("    misaka harvest --from-file <path>  Parse a log file")
        print("    misaka harvest --pipe             Accept stdin")
        print()
        print("  See misaka-protocol.json → ecosystem.tools.harvester for spec.")
        print("  Status: planned — not yet implemented.")
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
    query = sys.argv[1]
    mode = "all"
    titles_only = False
    broad_only = False
    top_k = 10
    use_semantic = False
    suggest = False
    for arg in sys.argv[2:]:
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
        elif arg == "--semantic":
            use_semantic = True
    search_args = sys.argv[2:]
    for i, arg in enumerate(search_args):
        if arg == "--top" and i + 1 < len(search_args):
            try:
                top_k = int(search_args[i + 1])
            except ValueError:
                pass
    t0 = time.time()
    found_any = False

    # --suggest mode: list matching titles when query >= 2 chars
    if suggest and len(query) >= 2:
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

    lessons_docs = _load_docs(LESSONS, is_lesson=True) if mode in ("all", "lessons") else []
    ref_docs = _load_docs(REFERENCES, is_lesson=False) if mode in ("all", "ref") else []
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
    if lessons_docs:
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"lessons/  (All {len(lessons_docs)} items)",
                               query=query)
        found_any = found_any or found
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"reference/  (All {len(ref_docs)} items)",
                               query=query)
        found_any = found_any or found
    total_docs = len(lessons_docs) + len(ref_docs)
    if not found_any:
        _show_smart_fallback(query, lessons_docs, ref_docs)
        print()
    _show_timing(time.time() - t0, total_docs)
    if found_any and not suggest:
        from misakanet.profile import increment_search
        increment_search()
    if found_any:
        print(f"  💡 View full content: cat lessons/<filename>.md")
        print(f"  💡 Contribute new knowledge: python3 scripts/queue_lesson.py -t 'title' -d domain 'content...'")
        print()


def _show_smart_fallback(query: str, lessons_docs: list, ref_docs: list) -> None:
    """Smart fallback when search returns no results.

    Provides tiered suggestions:
    1. Domain suggestions if query matches known domains
    2. Partial match preview (top 3 closest results)
    3. Helpful action items
    """
    from difflib import SequenceMatcher

    print(f"\n  ❌ No exact match for '{query}'")
    print()

    # 1. Domain suggestions
    all_docs = lessons_docs + ref_docs
    domains = set()
    for doc in all_docs:
        if hasattr(doc, 'domain') and doc.domain:
            domains.add(doc.domain.lower())

    query_lower = query.lower()
    matched_domains = [d for d in domains if d in query_lower or query_lower in d]

    if matched_domains:
        print(f"  💡 Your query matches domain(s): {', '.join(matched_domains[:3])}")
        print(f"     Try: python3 search_knowledge.py \"{matched_domains[0]}\" --lessons")
        print()

    # 2. Partial match preview
    similarities = []
    for doc in all_docs:
        title_sim = SequenceMatcher(None, query_lower, doc.title.lower()).ratio()
        content_sim = SequenceMatcher(None, query_lower, doc.content[:200].lower()).ratio()
        max_sim = max(title_sim, content_sim)
        if max_sim > 0.2:  # Low threshold for "close enough"
            similarities.append((max_sim, doc))

    if similarities:
        similarities.sort(reverse=True, key=lambda x: x[0])
        top_3 = similarities[:3]
        print(f"  📋 Closest matches (may be related):")
        for sim, doc in top_3:
            domain_tag = f"[{doc.domain}]" if hasattr(doc, 'domain') and doc.domain else ""
            print(f"     • {doc.title} {domain_tag} (similarity: {sim:.0%})")
        print()

    # 3. Action items
    print(f"  📝 Suggestions:")
    print(f"     • Try broader keywords or synonyms")
    if domains:
        print(f"     • Browse by domain: python3 search_knowledge.py --lessons")
    print(f"     • Add new knowledge: python3 scripts/queue_lesson.py -t \"{query}\" ...")
    print()


if __name__ == "__main__":
    main()
