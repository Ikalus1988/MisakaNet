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

# User-intent topic pages: map topic slug to matching keywords
INTENT_TOPICS = {
    "dco": {"title": "DCO Sign-off Failures", "keywords": ["dco", "signoff", "signed-off-by"], "description": "Fix Developer Certificate of Origin failures in CI and local commits."},
    "github-token": {"title": "GitHub Token & Authentication", "keywords": ["github token", "credential", "pat", "authentication", "401", "403"], "description": "Fix GitHub token, PAT, credential helper, and authentication issues."},
    "pip-timeout": {"title": "pip Install Failures", "keywords": ["pip", "timeout", "ssl", "install"], "description": "Fix Python pip install timeout, SSL, and dependency issues."},
    "feishu": {"title": "Feishu / Lark API Issues", "keywords": ["feishu", "lark"], "description": "Fix Feishu/Lark API integration, webhook, and bot issues."},
    "fanuc": {"title": "FANUC Industrial Robot", "keywords": ["fanuc", "karel", "profinet"], "description": "Fix FANUC robot programming, Karel, and PROFINET communication issues."},
    "wsl": {"title": "WSL & Windows Issues", "keywords": ["wsl", "windows", "ntfs", "gbk", "unicode", "encoding"], "description": "Fix WSL, Windows terminal, encoding, and permission issues."},
    "feishu-mcp": {"title": "Feishu MCP Integration", "keywords": ["feishu mcp", "feishu-mcp"], "description": "Fix Feishu MCP server setup and configuration."},
}

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


def unique_slug(title: str, seen_slugs: dict) -> str:
    """Generate unique slug, adding short hash on collision."""
    import hashlib
    base = slugify(title)
    if base not in seen_slugs:
        seen_slugs[base] = title
        return base
    # Collision: add short hash
    short_hash = hashlib.md5(title.encode()).hexdigest()[:6]
    return f"{base}-{short_hash}"


def build_lesson_page(lesson: dict) -> str:
    """Generate HTML for a single lesson."""
    title = lesson.get("title", "Untitled")
    domain = lesson.get("domain", "general")
    summary = lesson.get("summary", "")
    tags = lesson.get("tags", [])
    url = lesson.get("url", "")
    source_url = f"https://github.com/Ikalus1988/MisakaNet/blob/main/{url}" if url else ""
    slug = lesson.get("_slug", slugify(title))
    canonical = f"{SITE_URL}/lessons/{slug}/"

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


def build_topic_page(domain: str, lessons: list, description: str = "") -> str:
    """Generate HTML for a topic/domain page."""
    title = domain if " " in domain else f"{domain.title()} Lessons"
    if not description:
        description = f"{len(lessons)} verified failure lessons about {domain}. From MisakaNet — Git-backed failure lesson network."
    slug = domain.lower().replace(" ", "-").replace("/", "-")
    canonical = f"{SITE_URL}/topics/{slug}/"

    lessons_html = ""
    for l in lessons[:20]:
        lesson_slug = l.get("_slug", slugify(l.get("title", "")))
        lesson_title = l.get("title", "Untitled")
        summary = l.get("summary", "")[:120]
        lessons_html += f"""
<div class="lesson">
  <a href="/lessons/{lesson_slug}/">{lesson_title}</a>
  <div class="summary">{summary}</div>
</div>"""

    return TOPIC_TEMPLATE.format(
        title=title,
        description=description,
        canonical=canonical,
        count=len(lessons),
        lessons=lessons_html
    )


def generate_sitemap(lesson_slugs: list, domains: list) -> str:
    """Generate sitemap.xml with all pages."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    # Static pages
    static = [
        ("https://misakanet.org/", "weekly", "1.0"),
        ("https://misakanet.org/search/", "weekly", "0.9"),
        ("https://misakanet.org/troubleshooting/", "weekly", "0.8"),
    ]
    for url, freq, prio in static:
        lines.append(f"  <url><loc>{url}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>")

    # Topic pages
    for domain in domains:
        lines.append(f"  <url><loc>{SITE_URL}/topics/{domain}/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")

    # Lesson pages
    for slug in lesson_slugs:
        lines.append(f"  <url><loc>{SITE_URL}/lessons/{slug}/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>")

    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


def main():
    lessons = json.loads(LESSONS_JSON.read_text(encoding="utf-8"))
    print(f"Loaded {len(lessons)} lessons")

    # Build lesson pages with unique slugs
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    seen_slugs = {}
    lesson_slugs = []
    count = 0
    for lesson in lessons:
        title = lesson.get("title", "")
        if not title:
            continue
        slug = unique_slug(title, seen_slugs)
        lesson["_slug"] = slug
        lesson_slugs.append(slug)
        out_dir = LESSONS_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        html = build_lesson_page(lesson)
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        count += 1
    print(f"Generated {count} lesson pages ({len(seen_slugs)} unique slugs)")

    # Build topic pages
    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    by_domain = {}
    for l in lessons:
        domain = l.get("domain", "general")
        by_domain.setdefault(domain, []).append(l)

    generated_domains = []
    for domain in by_domain:
        out_dir = TOPICS_DIR / domain
        out_dir.mkdir(parents=True, exist_ok=True)
        html = build_topic_page(domain, by_domain[domain])
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        generated_domains.append(domain)

    # Build user-intent topic pages
    intent_slugs = []
    for topic_slug, config in INTENT_TOPICS.items():
        keywords = config["keywords"]
        matched = [l for l in lessons if any(
            kw in (l.get("title", "") + " " + l.get("summary", "") + " " + " ".join(l.get("tags", []))).lower()
            for kw in keywords
        )]
        if not matched:
            continue
        out_dir = TOPICS_DIR / topic_slug
        out_dir.mkdir(parents=True, exist_ok=True)
        html = build_topic_page(config["title"], matched, description=config["description"])
        (out_dir / "index.html").write_text(html, encoding="utf-8")
        intent_slugs.append(topic_slug)

    all_topics = generated_domains + intent_slugs
    print(f"Generated {len(generated_domains)} domain + {len(intent_slugs)} intent topic pages")

    # Generate sitemap
    sitemap = generate_sitemap(lesson_slugs, all_topics)
    sitemap_path = Path("docs") / "sitemap.xml"
    sitemap_path.write_text(sitemap, encoding="utf-8")
    print(f"Generated sitemap: {len(lesson_slugs)} lessons + {len(generated_domains)} topics + 2 static = {len(lesson_slugs) + len(generated_domains) + 2} URLs")


if __name__ == "__main__":
    main()
