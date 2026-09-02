#!/usr/bin/env python3
"""MisakaNet Web Knowledge Harvester — 使用 Scrapling 从网页提取并创建 lesson。

用法:
  python3 scripts/misaka_harvest.py --url <url> --domain <domain> [--title "<title>"]

依赖:
  pip install scrapling  (基础解析引擎)
  pip install "scrapling[fetchers]"  (如需绕过反爬/JS渲染)

生成的 lesson 文件将写入 lessons/contrib/ 并带有标准 frontmatter。
"""

import sys
import json
import re
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
CONTRIB = REPO / "lessons" / "contrib"


def extract_content(html_text: str) -> dict:
    """从 HTML 中提取结构化内容用于 lesson 生成。"""
    try:
        from scrapling.parser import Selector
    except ImportError:
        print("Error: 'scrapling' is required. Run: pip install scrapling")
        sys.exit(1)

    nav = Selector(html_text)

    # 提取标题
    title_el = nav.css("h1::text").get()
    title_text = str(title_el).strip() if title_el else ""

    # 提取段落
    paragraphs = nav.css("p")
    body_text = "\n".join(
        str(p).strip() for p in paragraphs if str(p).strip()
    ) if paragraphs else ""

    # 提取代码块
    codes = nav.css("pre code, code")
    code_blocks = []
    for c in codes:
        text = str(c).strip()
        if text and len(text) > 20:
            code_blocks.append(text)

    return {
        "title": title_text[:120] if title_text else "Untitled",
        "body": body_text[:5000] if body_text else "",
        "code_blocks": code_blocks[:5],
    }


def generate_lesson(url: str, domain: str, title: str = "", body: str = "") -> Optional[Path]:
    """从 URL 抓取内容并生成 lesson markdown 文件。"""
    try:
        from scrapling.fetchers import Fetcher
    except ImportError:
        print("Info: fetchers not available, using parser-only mode")
        print("  Install: pip install 'scrapling[fetchers]'")
        if not body:
            print("Error: no --body provided and fetchers unavailable")
            return None
        content = {"title": title, "body": body, "code_blocks": []}
    else:
        try:
            nav = Fetcher.get(url)
            content = extract_content(nav.body)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    # 使用标题或 URL 生成文件名
    lesson_title = title or content["title"] or url
    safe_name = re.sub(r'[^a-z0-9]+', '-', lesson_title.lower())[:60].strip('-')
    if not safe_name:
        safe_name = f"web-harvest-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    filepath = CONTRIB / f"web-{safe_name}.md"

    # 构建 lesson
    lines = [
        "---",
        json.dumps({
            "title": lesson_title,
            "domain": domain,
            "tags": [domain, "web-harvested"],
            "status": "draft",
            "source": url,
            "created": datetime.now().isoformat(),
        }, ensure_ascii=False),
        "---",
        "",
        f"## Problem",
        "",
        content["body"][:500] if content["body"] else f"Extracted from {url}",
        "",
        f"## Reference",
        "",
        f"Source: [{url}]({url})",
        "",
    ]

    if content.get("code_blocks"):
        lines.append("## Code Reference")
        lines.append("")
        for i, cb in enumerate(content["code_blocks"], 1):
            lines.append(f"```")
            lines.append(cb[:1000])
            lines.append("```")
            lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Harvest web content as MisakaNet lesson")
    parser.add_argument("--url", help="URL to harvest")
    parser.add_argument("--domain", default="web", help="Domain tag for the lesson")
    parser.add_argument("--title", default="", help="Lesson title (optional)")
    parser.add_argument("--body", default="", help="Content body (if fetchers not available")
    parser.add_argument("--list-domains", action="store_true", help="List known domains")

    args = parser.parse_args()

    if args.list_domains:
        domains = set()
        for f in CONTRIB.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            m = re.search(r'"domain"\s*:\s*"([^"]+)"', content)
            if m:
                domains.add(m.group(1))
        print("Known domains:")
        for d in sorted(domains):
            print(f"  {d}")
        return

    if not args.url and not args.body:
        parser.print_help()
        return

    result = generate_lesson(args.url, args.domain, args.title, args.body)

    if result:
        print(f"✅ Lesson created: {result.relative_to(REPO)}")
        print(f"   Title: {result.stem}")
        print(f"   Status: draft (edit to mark as published)")
    else:
        print("❌ Failed to create lesson")
        sys.exit(1)


if __name__ == "__main__":
    main()
