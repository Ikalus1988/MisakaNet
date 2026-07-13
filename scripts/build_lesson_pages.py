#!/usr/bin/env python3
"""Generate static lesson and topic pages from lessons.json for SEO.

Usage:
    python3 scripts/build_lesson_pages.py

Output:
    docs/lessons/<slug>/index.html  — one page per lesson
    docs/topics/<domain>/index.html — one page per domain
"""

import json
import os
from pathlib import Path

LESSONS_JSON = Path("data/lessons.json")
LESSONS_DIR = Path("docs/lessons")
TOPICS_DIR = Path("docs/topics")
SITE_URL = "https://misakanet.org"

# Top domains to generate topic pages for
TOP_DOMAINS = [
    "devops", "feishu", "fanuc", "development", "rag",
    "agent-network", "general", "uncategorized"
]

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — MisakaNet</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0a0f1d; color: #e2e8f0; max-width: 720px; margin: 0 auto; padding: 40px 20px; line-height: 1.6; }}
  a {{ color: #58a6ff; }}
  h1 {{ font-size: 24px; margin-bottom: 8px; }}
  .meta {{ color: #8b949e; font-size: 13px; margin-bottom: 24px; }}
  .section {{ margin-bottom: 24px; }}
  .section h2 {{ font-size: 16px; color: #58a6ff; margin-bottom: 8px; }}
  .section p {{ color: #c9d1d9; font-size: 14px; }}
  .tags {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0; }}
  .tag {{ background: rgba(88,166,255,0.1); color: #58a6ff; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
  .related {{ margin-top: 32px; }}
  .related a {{ display: block; padding: 8px 0; border-bottom: 1px solid rgba(88,166,255,0.1); }}
  .back {{ margin-top: 32px; font-size: 13px; }}
</style>
</head>
<body>
{body}
<div class="back"><a href="/">← Back to MisakaNet</a> · <a href="/search/">Search lessons</a></div>
</body>
</html>"""

TOPIC_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — MisakaNet</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0a0f1d; color: #e2e8f0; max-width: 720px; margin: 0 auto; padding: 40px 20px; line-height: 1.6; }}
  a {{ color: #58a6ff; }}
  h1 {{ font-size: 24px; margin-bottom: 8px; }}
  .count {{ color: #8b949e; font-size: 14px; margin-bottom: 24px; }}
  .lesson {{ padding: 12px 0; border-bottom: 1px solid rgba(88,166,255,0.1); }}
  .lesson a {{ font-weight: 600; }}
  .lesson .summary {{ color: #8b949e; font-size: 13px; margin-top: 4px; }}
  .back {{ margin-top: 32px; font-size: 13px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="count">{count} lessons in this domain</div>
{lessons}
<div class="back"><a href="/">← Back to MisakaNet</a> · <a href="/search/">Search lessons</a></div>
</body>
</html>"""


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].strip('-')


def build_lesson_page(lesson: dict) -> str:
    """Generate HTML for a single lesson."""
    title = lesson.get("title", "Untitled")
    domain = lesson.get("domain", "general")
    summary = lesson.get("summary", "")
    tags = lesson.get("tags", [])
    url = lesson.get("url", "")
    source_url = f"https://github.com/Ikalus1988/MisakaNet/blob/main/{url}" if url else ""
    canonical = f"{SITE_URL}/lessons/{slugify(title)}/"

    description = f"{summary[:150]}..." if len(summary) > 150 else summary
    if not description:
        description = f"Verified failure lesson: {title}. From MisakaNet — Git-backed failure lesson network."

    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags[:6])

    body = f"""<h1>{title}</h1>
<div class="meta">Domain: <a href="/topics/{domain}/">{domain}</a></div>
<div class="tags">{tags_html}</div>
<div class="section">
  <h2>Summary</h2>
  <p>{summary or 'See source for full details.'}</p>
</div>"""

    if source_url:
        body += f'\n<div class="section"><h2>Source</h2><p><a href="{source_url}">View on GitHub →</a></p></div>'

    body += f'\n<div class="section"><h2>Search</h2><p><a href="/search/?q={title}">Find related lessons →</a></p></div>'

    return HTML_TEMPLATE.format(title=title, description=description, canonical=canonical, body=body)


def build_topic_page(domain: str, lessons: list) -> str:
    """Generate HTML for a topic/domain page."""
    title = f"{domain.title()} Lessons"
    description = f"{len(lessons)} verified failure lessons about {domain}. From MisakaNet — Git-backed failure lesson network."
    canonical = f"{SITE_URL}/topics/{domain}/"

    lessons_html = ""
    for l in lessons[:20]:
        slug = slugify(l.get("title", ""))
        lesson_title = l.get("title", "Untitled")
        summary = l.get("summary", "")[:120]
        lessons_html += f"""
<div class="lesson">
  <a href="/lessons/{slug}/">{lesson_title}</a>
  <div class="summary">{summary}</div>
</div>"""

    return TOPIC_TEMPLATE.format(
        title=title,
        description=description,
        canonical=canonical,
        count=len(lessons),
        lessons=lessons_html
    )


def main():
    lessons = json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
    print(f"Loaded {len(lessons)} lessons")

    # Build lesson pages
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for lesson in lessons:
        title = lesson.get("title", "")
        if not title:
            continue
        slug = slugify(title)
        out_dir = LESSONS_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        html = build_lesson_page(lesson)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        count += 1
    print(f"Generated {count} lesson pages")

    # Build topic pages
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    by_domain = {}
    for l in lessons:
        domain = l.get("domain", "general")
        by_domain.setdefault(domain, []).append(l)

    for domain in TOP_DOMAINS:
        if domain not in by_domain:
            continue
        out_dir = TOPICS_DIR / domain
        out_dir.mkdir(parents=True, exist_ok=True)
        html = build_topic_page(domain, by_domain[domain])
        (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Generated {len(by_domain)} topic pages")


if __name__ == "__main__":
    main()
