#!/usr/bin/env python3
"""Lesson 质量评分器 — 完整性 / 可验证性 / 结构评分。

用法:
  python3 scripts/score_lessons.py            # 评分全部 lessons
  python3 scripts/score_lessons.py --html     # 输出 HTML 报告
  python3 scripts/score_lessons.py --bottom=5 # 只看最低分 5 条
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"


def parse_frontmatter(text: str) -> dict:
    meta = {}
    m = re.match(r'^---\s*\n?(\{.*?\})\n?---', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if m:
        for line in m.group(1).split('\n'):
            if ':' not in line:
                continue
            k, _, v = line.partition(':')
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def score_lesson(path: Path) -> dict:
    """对单个 lesson 评分，返回分数和明细。"""
    content = path.read_text(encoding="utf-8", errors="replace")
    meta = parse_frontmatter(content)
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2]

    s = {"path": str(path.relative_to(LESSONS_DIR)), "title": meta.get("title", path.stem)}
    details = []
    total = 0.0

    # 1. 有 frontmatter title (+10)
    if meta.get("title"):
        total += 10; details.append(("✅ title", 10))
    else:
        details.append(("❌ 无 title", 0))

    # 2. 有 domain (+5)
    d = meta.get("domain", "")
    if d and d != "uncategorized":
        total += 5; details.append(("✅ domain", 5))
    else:
        details.append(("⚠️ domain 未分类", 0))

    # 3. 有 tags (+5)
    tags = meta.get("tags", [])
    if isinstance(tags, list) and len(tags) > 0:
        t = min(len(tags) * 2, 5)
        total += t; details.append((f"✅ tags [{len(tags)}个]", t))
    else:
        details.append(("⚠️ 无 tags", 0))

    # 4. 有 "问题" 小节 (+15)
    if re.search(r'##\s*(问题|Problem|症状|背景)', body, re.IGNORECASE):
        total += 15; details.append(("✅ 问题描述", 15))
    else:
        details.append(("❌ 无问题描述", 0))

    # 5. 有 "根因" 小节 (+15)
    if re.search(r'##\s*(根因|Root\s*Cause|原因|分析)', body, re.IGNORECASE):
        total += 15; details.append(("✅ 根因分析", 15))
    else:
        details.append(("⚠️ 无根因分析", 0))

    # 6. 有 "修复" 小节 (+20)
    if re.search(r'##\s*(修复|Fix|方案|解法|Solution)', body, re.IGNORECASE):
        total += 20; details.append(("✅ 修复方案", 20))
    else:
        details.append(("❌ 无修复方案", 0))

    # 7. 有 "验证" 小节 (+15)
    if re.search(r'##\s*(验证|Verify|确认|测试|Test)', body, re.IGNORECASE):
        total += 15; details.append(("✅ 验证步骤", 15))
    else:
        details.append(("⚠️ 无验证步骤", 0))

    # 8. 包含可执行命令代码块 (+10)
    blocks = re.findall(r'```(?:bash|sh|shell|python|yaml|json|toml|ini)?\n', body)
    if blocks:
        t = min(len(blocks) * 3, 10)
        total += t; details.append((f"✅ 代码块 [{len(blocks)}个]", t))
    else:
        details.append(("⚠️ 无可执行命令", 0))

    # 9. 内容长度 > 200 字 (+5)
    if len(body.strip()) > 200:
        total += 5; details.append(("✅ 内容充实", 5))
    else:
        details.append(("⚠️ 内容过短", 0))

    s["score"] = min(total, 100)
    s["details"] = details
    s["length"] = len(body.strip())
    s["domain"] = d
    return s


def main():
    parser = argparse.ArgumentParser(description="Lesson 质量评分")
    parser.add_argument("--html", action="store_true", help="输出 HTML 报告")
    parser.add_argument("--bottom", type=int, default=0, help="只看最低分 N 条")
    parser.add_argument("--domain", default="", help="筛选领域")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    results = []
    for f in sorted(LESSONS_DIR.glob("**/*.md")):
        if f.name == "index.md" or f.name.startswith("."):
            continue
        s = score_lesson(f)
        if args.domain and args.domain != s.get("domain", ""):
            continue
        results.append(s)

    results.sort(key=lambda x: x["score"])

    if args.bottom > 0:
        results = results[:args.bottom]

    if args.json:
        print(json.dumps([
            {"title": r["title"], "score": r["score"],
             "domain": r.get("domain", ""), "length": r["length"]}
            for r in results
        ], ensure_ascii=False, indent=2))
        return

    if args.html:
        avg = sum(r["score"] for r in results) / len(results)
        low = [r for r in results if r["score"] < 50]
        print(f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>Lesson 质量报告</title>
<style>
  body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
  .bar {{ height: 16px; border-radius: 3px; margin: 2px 0; }}
  .good {{ background: #2ecc71; }}
  .warn {{ background: #f39c12; }}
  .bad {{ background: #e74c3c; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #eee; }}
</style></head><body>
<h1>📊 Lesson 质量报告</h1>
<p>共 {len(results)} 篇 | 平均分 {avg:.0f}/100 | 低于50分: {len(low)} 篇</p>
<table>
<tr><th>分数</th><th>标题</th><th>领域</th><th>字数</th></tr>""")
        for r in reversed(results):
            cls = "good" if r["score"] >= 70 else ("warn" if r["score"] >= 50 else "bad")
            print(f'<tr><td><div class="bar {cls}" style="width:{r["score"]}%"></div> {r["score"]}</td><td>{r["title"][:40]}</td><td>{r.get("domain","")}</td><td>{r["length"]}</td></tr>')
        print("</table></body></html>")
        return

    print(f"\n📊 Lesson 质量评分 ({len(results)} 篇)")
    print("-" * 60)
    for r in (reversed(results) if not args.bottom else results):
        bar = "█" * max(1, int(r["score"]) // 5) + "░" * max(0, 20 - int(r["score"]) // 5)
        tag = f"[{r.get('domain','')}]" if r.get('domain') else ""
        print(f"  {bar} {int(r['score']):3d}%  {tag:<14} {r['title'][:50]}")
    avg = sum(r["score"] for r in results) / len(results)
    print(f"\n  平均分: {avg:.0f}/100")
    low = [r for r in results if r["score"] < 50]
    if low:
        print(f"  需改进: {len(low)} 篇 (低于50分)")


if __name__ == "__main__":
    main()
