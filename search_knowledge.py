#!/usr/bin/env python3
"""CLI 薄包装层 — 核心实现在 misakanet/search/engine.py"""
import sys
import time
from misakanet.search.engine import *

def main():
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
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            try:
                top_k = int(args[i + 1])
            except ValueError:
                pass
    t0 = time.time()
    found_any = False

    # --suggest 模式：≥2字符时列出匹配标题
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
            print("  建议:")
            for d in matches[:top_k]:
                tag = f"[{d.domain}]" if d.domain else ""
                print(f"    {tag:<18} {d.title}")
        else:
            print(f"  (无匹配)")
        _show_timing(time.time() - t0, len(all_docs))
        return

    lessons_docs = _load_docs(LESSONS, is_lesson=True) if mode in ("all", "lessons") else []
    ref_docs = _load_docs(REFERENCES, is_lesson=False) if mode in ("all", "ref") else []
    if use_semantic:
        try:
            from storage.vector_store import generate_embedding
            print("  🔬 语义检索已启用")
        except ImportError:
            print("  ⚠️ --semantic 需要 sentence-transformers，降级为 BM25")
    if lessons_docs:
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"lessons/  (全部 {len(lessons_docs)} 篇)",
                               query=query)
        found_any = found_any or found
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"reference/  (全部 {len(ref_docs)} 篇)",
                               query=query)
        found_any = found_any or found
    total_docs = len(lessons_docs) + len(ref_docs)
    if not found_any:
        print(f"\\n  ❌ 未找到 '{query}' 相关内容")
        print(f"  如果这是一个新踩坑，请入库:")
        print(f"    python3 misakanet/scripts/queue_lesson.py -t \"{query}\" ...")
        print()
    _show_timing(time.time() - t0, total_docs)
    if found_any and not suggest:
        from misakanet.profile import increment_search
        increment_search()
    if found_any:
        print(f"  💡 查看完整内容: cat lessons/<filename>.md")
        print(f"  💡 贡献新知识: python3 misakanet/scripts/queue_lesson.py -t '标题' -d domain '内容...'")
        print()


if __name__ == "__main__":
    main()
