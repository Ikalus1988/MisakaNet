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
    """解析 --- 包裹的 JSON frontmatter（支持空行）"""
    m = re.match(r"^---[ \t]*\n(.*?)\n[ \t]*---", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def extract_summary(content: str, max_length: int = 160) -> str:
    """从内容中提取第一段有效文本作为摘要"""
    import re
    # Remove frontmatter (both ---{json}--- and ---\nyaml\n--- formats)
    m = re.match(r"^---.*?---\s*", content, re.DOTALL)
    if m:
        content = content[m.end():]

    lines = content.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("---") or stripped.startswith("{"):
            continue
        if stripped.startswith("#") or stripped.startswith("##"):
            continue
        if stripped.startswith("```"):
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
    # Scan both core and contrib subdirectories
    for subdir in ["core", "contrib"]:
        subdir_path = lessons_dir / subdir
        if not subdir_path.exists():
            continue
        for f in sorted(subdir_path.glob("*.md")):
            if f.name == "index.md" or f.name.startswith("."):
                continue

            content = f.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)

            # Domain: use frontmatter domain, fallback to subdirectory
            domain = fm.get("domain", "") if fm else ""
            if not domain or domain == "contrib":
                domain = fm.get("subdomain", subdir) if fm else subdir

            entry = {
                "id": f.stem,
                "title": fm.get("title", f.stem) if fm else f.stem,
                "domain": domain,
                "tags": fm.get("tags", []) if fm else [],
                "summary": extract_summary(content),
                "url": f"lessons/{subdir}/{f.name}",
                "created": fm.get("created", "") if fm else "",
                "updated": fm.get("updated", "") if fm else "",
                "validity_period_days": fm.get("validity_period_days", 365) if fm else 365,
                "environment_version": fm.get("environment_version", "") if fm else "",
                "confidence": fm.get("confidence", 0.5) if fm else 0.5,
                "status": fm.get("status", "active") if fm else "active",
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
