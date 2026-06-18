#!/usr/bin/env python3
"""CLI thin wrapper — core implementation in misakanet/search/engine.py

Ecosystem links:
    from misakanet_core import BM25, tokenize, rrf
"""
import sys
import time
import re
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
                           query=primary_sig)
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
    lang: Optional[str] = None
    domain: Optional[str] = None
    search_args = sys.argv[2:]
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

    # Language filter
    if lang:
        lessons_docs = [d for d in lessons_docs if d.language == lang]
        ref_docs = [d for d in ref_docs if d.language == lang]
        print(f"  🌐 Filtering by language: {lang}")

    # Domain filter (fix #229)
    if domain:
        lessons_docs = [d for d in lessons_docs if d.domain and d.domain.lower() == domain]
        ref_docs = [d for d in ref_docs if d.domain and d.domain.lower() == domain]
        print(f"  🏷️  Filtering by domain: {domain}")

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
    
    if lessons_docs:
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only)
        # Only show results above threshold
        filtered = [(s, d) for s, d in ranked if s >= MIN_SCORE_THRESHOLD]
        found = _format_output(filtered, titles_only, top_k,
                               mode_label=f"lessons/  (All {len(lessons_docs)} items)",
                               query=query)
        found_any = found_any or found
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False)
        # Only show results above threshold
        filtered = [(s, d) for s, d in ranked if s >= MIN_SCORE_THRESHOLD]
        found = _format_output(filtered, titles_only, top_k,
                               mode_label=f"reference/  (All {len(ref_docs)} items)",
                               query=query)
        found_any = found_any or found
    total_docs = len(lessons_docs) + len(ref_docs)
    if not found_any:
        # Feature #229: Smart fallback when no results
        print(f"\\n  ❌ No exact match for '{query}'")
        print()
        
        # Collect all domains for suggestions
        all_domains = set()
        for d in lessons_docs + ref_docs:
            if d.domain:
                all_domains.add(d.domain.lower())
        
        # 1. Domain suggestions
        q = query.lower()
        domain_matches = [d for d in all_domains if d in q or q in d]
        if domain_matches:
            print(f"  💡 Try domain filter:")
            for dm in domain_matches[:3]:
                print(f"     --domain {dm}")
        
        # 2. Broad mode hint
        print(f"  💡 Try broader search: --broad or --ref")
        
        # 3. Quick contribution link
        print(f"  💡 Add new knowledge:")
        print(f"     python3 scripts/queue_lesson.py -t \"{query}\" ...")
        
        # 4. Show top domains as examples
        if all_domains:
            top_domains = sorted(all_domains)[:8]
            print(f"  💡 Available domains: {', '.join(top_domains)}")
        
        print()
    _show_timing(time.time() - t0, total_docs)
    if found_any and not suggest:
        from misakanet.profile import increment_search
        increment_search()
    if found_any:
        print(f"  💡 View full content: cat lessons/<filename>.md")
        print(f"  💡 Contribute new knowledge: python3 scripts/queue_lesson.py -t 'title' -d domain 'content...'")
        print()


if __name__ == "__main__":
    main()
