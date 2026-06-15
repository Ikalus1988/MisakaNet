#!/usr/bin/env python3
"""CLI thin wrapper — core implementation in misakanet/search/engine.py

Ecosystem links:
    from misakanet_core import BM25, tokenize, rrf
"""
import sys
import time
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
        elif arg.startswith("--lang="):
            lang = arg.split("=", 1)[1]
        elif arg == "--lang":
            # handled below with value
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
        elif arg == "--lang" and i + 1 < len(search_args):
            lang = search_args[i + 1]
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
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only, lang)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"lessons/  (All {len(lessons_docs)} items)",
                               query=query)
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"reference/  (All {len(ref_docs)} items)",
                               query=query)
        found_any = found_any or found
    total_docs = len(lessons_docs) + len(ref_docs)
    if not found_any:
        print(f"\\n  ❌ Not found '{query}' related content")
        print(f"  If this is a new issue, please add it:")
        print(f"    python3 scripts/queue_lesson.py -t \"{query}\" ...")
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
