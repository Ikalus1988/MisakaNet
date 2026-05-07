#!/usr/bin/env python3
"""
虫群知识检索 — lessons + reference 轻量搜索
用法:
  search_knowledge.py "微信安装失败"           # 搜 lessons + reference
  search_knowledge.py "虫群记忆" --ref          # 只搜 reference
  search_knowledge.py "wxauto" --lessons        # 只搜 lessons
  search_knowledge.py "rag" --titles            # 只看标题
  search_knowledge.py "wxauto" --broad           # 只看跨平台通用 lessons
"""
import sys
import os
from pathlib import Path

REPO = Path(__file__).parent
LESSONS = REPO / "lessons"
REFERENCES = REPO / "reference"
INDEX = LESSONS / "index.md"


def search_lessons(query, titles_only=False):
    results = []
    for f in sorted(LESSONS.glob("*.md")):
        if f.name == "index.md":
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        if query.lower() not in content.lower():
            continue
        # 提取 title
        title = f.name.replace(".md", "")
        if content.startswith("---"):
            for line in content.split("---", 2)[1].split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
                    break
        # 提取 domain
        domain = ""
        for line in content.split("---", 2)[1].split("\n"):
            if line.startswith("domain:"):
                domain = line.split(":", 1)[1].strip()
                break
        # 提取 reference 字段
        ref = ""
        for line in content.split("---", 2)[1].split("\n"):
            if line.startswith("reference:"):
                ref = line.split(":", 1)[1].strip()
                break
        score = content.lower().count(query.lower())
        results.append((score, domain, title, f.name, ref))
    results.sort(key=lambda x: -x[0])
    return results


def search_references(query):
    results = []
    for f in sorted(REFERENCES.glob("*.md")):
        content = f.read_text(encoding="utf-8", errors="replace")
        if query.lower() not in content.lower():
            continue
        title = f.name.replace(".md", "")
        if content.startswith("---"):
            for line in content.split("---", 2)[1].split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
                    break
        # 提取 type
        rtype = ""
        for line in content.split("---", 2)[1].split("\n"):
            if line.startswith("type:"):
                rtype = line.split(":", 1)[1].strip()
                break
        results.append((rtype or "general", title, f.name))
    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    query = sys.argv[1]
    mode = "all"
    titles_only = False
    broad_only = False
    
    if "--ref" in sys.argv:
        mode = "ref"
    if "--lessons" in sys.argv:
        mode = "lessons"
    if "--titles" in sys.argv:
        titles_only = True
    if "--broad" in sys.argv:
        broad_only = True
    
    found_any = False
    
    if mode in ("all", "lessons"):
        hits = search_lessons(query, titles_only)
        if broad_only:
            # scope:broad 是 YAML frontmatter 中的 tags 字段 (如 tags: [scope:broad, wsl])
            hits = [h for h in hits if 'scope:broad' in open(LESSONS / h[3], encoding='utf-8', errors='replace').read()]
        if hits:
            found_any = True
            print(f"\n📋 lessons/ ({len(hits)} 条匹配)")
            print("-" * 50)
            for score, domain, title, filename, ref in hits[:10]:
                domain_tag = f"[{domain}]" if domain else ""
                rel_path = f"lessons/{filename}"
                print(f"  {domain_tag:<20} {title}")
                if titles_only:
                    continue
                print(f"  {'':>20} → less {rel_path}")
                if ref:
                    print(f"  {'':>20} → 详细方案: less {ref}")
                print()
    
    if mode in ("all", "ref"):
        hits = search_references(query)
        if hits:
            found_any = True
            print(f"\n📋 reference/ ({len(hits)} 条匹配)")
            print("-" * 50)
            for rtype, title, filename in hits:
                type_tag = f"[{rtype}]" if rtype else ""
                print(f"  {type_tag:<20} {title}")
                print(f"  {'':>20} → less reference/{filename}")
                print()
    
    if not found_any:
        print(f"\n  ❌ 未找到 '{query}' 相关内容")
        print(f"  如果这是一个新踩坑，请入库:")
        print(f"    python3 misakanet/scripts/queue_lesson.py -t \"{query}\" ...")


if __name__ == "__main__":
    main()
