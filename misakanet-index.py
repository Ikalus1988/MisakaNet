#!/usr/bin/env python3
"""
misakanet-index.py — 御坂网络知识索引生成器

从 lessons/ 目录读取所有 lesson 文件，提取 frontmatter + 摘要，
生成 lessons.json 供 CDN 分发。

用法:
  python3 misakanet-index.py                     # 输出到 stdout
  python3 misakanet-index.py --output lessons.json  # 写入文件

发布:
  GitHub Actions 或 cron 定时运行，将 lessons.json 推送到 CDN。
  也可直接用 raw.githubusercontent.com 从 GitHub 读取。
"""

import json
import os
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> dict | None:
    """解析 --- 包裹的 JSON frontmatter"""
    m = re.match(r"^---\s*\n(\{.*?\})\s*\n---", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def extract_summary(content: str, max_length: int = 160) -> str:
    """从内容中提取第一段有效文本作为摘要"""
    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("---") or stripped.startswith("{"):
            continue
        if stripped.startswith("#") or stripped.startswith("##"):
            continue
        if len(stripped) > max_length:
            return stripped[:max_length] + "…"
        return stripped
    return ""


def build_index(lessons_dir: str | Path) -> list[dict]:
    """扫描 lessons/ 目录，构建知识索引"""
    lessons_dir = Path(lessons_dir)
    if not lessons_dir.exists():
        print(f"[warn] {lessons_dir} 不存在，返回空索引", file=sys.stderr)
        return []

    index = []
    for f in sorted(lessons_dir.glob("*.md")):
        if f.name == "index.md" or f.name.startswith("."):
            continue

        content = f.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        entry = {
            "id": f.stem,
            "title": fm.get("title", f.stem) if fm else f.stem,
            "domain": fm.get("domain", "uncategorized") if fm else "uncategorized",
            "tags": fm.get("tags", []) if fm else [],
            "summary": extract_summary(content),
            "url": f"lessons/{f.name}",
            "updated": fm.get("updated", "") if fm else "",
        }
        index.append(entry)

    return index


def main():
    import argparse

    parser = argparse.ArgumentParser(description="御坂网络知识索引生成器")
    parser.add_argument(
        "--lessons-dir",
        default="lessons",
        help="lessons 目录路径 (默认: lessons)",
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径（默认输出到 stdout）",
    )
    args = parser.parse_args()

    index = build_index(args.lessons_dir)
    output = json.dumps(index, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"已写入 {args.output}: {len(index)} 条知识", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
