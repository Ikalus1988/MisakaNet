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
    """从 HTML 中提取结构化内容用于 lesson 生成。

    兼容 scrapling 0.4.9+（.text 属性，非 .text() 方法）。
    回退到内置 html.parser + regex 提取。
    """
    title_text = ""
    body_text = ""
    code_blocks = []

    # ── 方式 1: scrapling Selector ──
    try:
        from scrapling.parser import Selector
        # 兼容 bytes / str
        html_str = html_text.decode("utf-8", errors="replace") if isinstance(html_text, bytes) else html_text
        nav = Selector(html_str)

        # 标题
        t = nav.css("h1")
        if t:
            title_text = str(t[0].text or "").strip()
        if not title_text:
            t = nav.css("title")
            if t:
                title_text = str(t[0].text or "").strip()

        # 段落
        paragraphs = nav.css("p")
        parts = []
        for p in paragraphs:
            txt = str(p.text or "").strip()
            if txt:
                parts.append(txt)
        body_text = "\n".join(parts)

        # 代码块
        codes = nav.css("pre code, code")
        for c in codes:
            txt = str(c.text or "").strip()
            if txt and len(txt) > 20:
                code_blocks.append(txt)

        if body_text:
            return {
                "title": title_text[:120] if title_text else "Untitled",
                "body": body_text[:5000],
                "code_blocks": code_blocks[:5],
            }
    except Exception:
        pass

    # ── 方式 2: regex 回退 ──
    import re as _re
    html_str2 = html_text.decode("utf-8", errors="replace") if isinstance(html_text, bytes) else html_text
    m = _re.search(r'<h1[^>]*>(.*?)</h1>', html_str2, _re.S | _re.I)
    if m:
        title_text = _re.sub(r'<[^>]+>', '', m.group(1)).strip()
    if not title_text:
        m = _re.search(r'<title[^>]*>(.*?)</title>', html_text, _re.S | _re.I)
        if m:
            title_text = _re.sub(r'<[^>]+>', '', m.group(1)).strip()

    paragraphs = _re.findall(r'<p[^>]*>(.*?)</p>', html_str2, _re.S | _re.I)
    body_text = "\n".join(
        _re.sub(r'<[^>]+>', '', p).strip() for p in paragraphs
        if _re.sub(r'<[^>]+>', '', p).strip()
    )

    code_raw = _re.findall(r'<(?:pre|code)[^>]*>(.*?)</(?:pre|code)>', html_str2, _re.S | _re.I)
    for c in code_raw:
        txt = _re.sub(r'<[^>]+>', '', c).strip()
        if txt and len(txt) > 20:
            code_blocks.append(txt)

    return {
        "title": title_text[:120] if title_text else "Untitled",
        "body": body_text[:5000],
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
            nav = Fetcher().get(url)
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
