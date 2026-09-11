#!/usr/bin/env python3
"""Generate static lesson and topic pages from lessons.json for SEO.

Usage:
    python3 scripts/build_lesson_pages.py            # write/refresh every page
    python3 scripts/build_lesson_pages.py --check    # report drift, write nothing (exit 1 if stale)

Output:
    docs/lessons/<slug>/index.html   — one page per lesson
    docs/topics/<slug>/index.html    — one page per topic (see TOPIC policy below)
    docs/topics/index.html           — the topic directory (the search page links to /topics/)
    docs/sitemap.xml                 — every generated URL + the static pages
    docs/.generated-pages.json       — manifest of what this generator owns

Why this file changed (2026-09-12, handoff-2026-09-12 §5.3)
----------------------------------------------------------
The generator existed but **nothing ran it**: it had been executed once by hand,
so the site had 205 lesson pages for 378 lessons, 88 pages for titles that no
longer exist, and topic pages advertising counts frozen at generation time
(`docs/topics/contrib/` said "176 verified failure lessons" while the index held
330). Three defects made running it in a loop unsafe:

1. it never removed what it stopped generating (stale pages would accumulate
   forever), so it could not own its output;
2. it wrote ``N verified failure lessons`` into every ``<meta description>``,
   which docs/trust-semantics.md explicitly forbids ("indexed" is the word for
   scale claims; "verified" is reserved for fact-checked lessons);
3. the ``domain`` field falls back to the directory name, so translation dirs
   leak in as "domains" (``es``, ``pt-br``) and would each get a topic page.

It is now wired into the daily ``update-lessons.yml`` (after
``update_lessons_json.py``, which it reads) and owns exactly what its manifest
lists: generated pages are pruned when they stop being generated, and pruning
only touches directories that carry this generator's marker.

TOPIC policy
------------
A topic page is generated for:

* every non-locale ``domain`` value in the index (the raw domain is
  directory-based today, so ``contrib``/``core``/``ops`` are topics too), plus
* every entry of ``INTENT_TOPICS`` (curated keyword topics), plus
* ``LEGACY_TOPICS``: slugs that are live URLs today because an older version of
  this script generated them, kept alive and refreshed instead of being deleted
  behind the user's back. Each one is matched by its slug tokens, the same
  generic rule the generator would use for a domain page.

``TOP_DOMAINS`` is gone: it was config that ``main()`` never read.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from misakanet.evidence import describe  # noqa: E402

LESSONS_JSON = Path("data") / "lessons.json"
LESSONS_DIR = Path("docs") / "lessons"
TOPICS_DIR = Path("docs") / "topics"
TOPICS_INDEX = TOPICS_DIR / "index.html"
SITEMAP = Path("docs") / "sitemap.xml"
MANIFEST = Path("docs") / ".generated-pages.json"
SITE_URL = "https://misakanet.org"

# Prune guard: a directory is only deleted if its page carries this marker, so a
# hand-written page that happens to live under the generated tree is never lost.
GENERATOR_MARK = "Back to MisakaNet"

# Translation directories show up as `domain` values (the field falls back to the
# directory name) — they are not topics.
LOCALE_DIRS = frozenset({"en", "es", "hi", "id", "pt-br", "ru", "tr", "vi"})

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

# Live slugs from the previous generation that no current domain/intent entry
# covers. Matched by their slug tokens; a slug matching nothing is simply not
# regenerated (and its stale page is pruned).
LEGACY_TOPICS = {
    "agent-network": "Lessons about agents, nodes and the network",
    "database": "Lessons about databases and locked/unavailable data stores",
    "mcp-setup": "Lessons about setting up MCP servers",
    "scraping": "Lessons about scraping and crawlers",
    "windows-encoding": "Lessons about Windows, encodings and terminal output",
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
  .evidence {{ background: rgba(163,113,247,0.14); color: #a371f7; border-radius: 4px; padding: 2px 6px; font-size: 12px; cursor: help; }}
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

TOPICS_INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Browse failure lessons by topic — MisakaNet</title>
<meta name="description" content="Browse {total} indexed failure-recovery lessons by topic: {topics}.">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="Browse failure lessons by topic — MisakaNet">
<meta property="og:description" content="Browse {total} indexed failure-recovery lessons by topic.">
<meta property="og:url" content="{canonical}">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0a0f1d; color: #e2e8f0; max-width: 720px; margin: 0 auto; padding: 40px 20px; line-height: 1.6; }}
  a {{ color: #58a6ff; }}
  h1 {{ font-size: 24px; margin-bottom: 8px; }}
  .count {{ color: #8b949e; font-size: 14px; margin-bottom: 24px; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ padding: 8px 0; border-bottom: 1px solid rgba(88,166,255,0.1); display: flex; justify-content: space-between; gap: 12px; }}
  li .n {{ color: #8b949e; font-size: 13px; white-space: nowrap; }}
  .back {{ margin-top: 32px; font-size: 13px; }}
</style>
</head>
<body>
<h1>Browse by topic</h1>
<div class="count">{total} indexed failure-recovery lessons across {topic_count} topics</div>
<ul>
{items}
</ul>
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
        # "indexed", not "verified": docs/trust-semantics.md reserves "verified"
        # for lessons fact-checked against source material.
        description = f"Indexed failure lesson: {title}. From MisakaNet — Git-backed failure lesson network."

    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags[:6])

    # Evidence level (#786) — how well this lesson is backed, not how well written.
    evidence = describe(lesson.get("evidence_level"))
    evidence_html = (
        f'<span class="evidence" title="{evidence["how_to_achieve"]}">'
        f'Evidence {evidence["evidence_level"]} — {evidence["label"]}</span>'
    )

    body = f"""<h1>{title}</h1>
<div class="meta">Domain: <a href="/topics/{domain}/">{domain}</a> · {evidence_html}</div>
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
        # "indexed" (see build_lesson_page) — a scale claim, not a trust claim.
        description = f"{len(lessons)} indexed failure lessons about {domain}. From MisakaNet — Git-backed failure lesson network."
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


def build_topics_index(entries: list[tuple[str, str, int]], total: int) -> str:
    """The topic directory the search page's "browse by topic" link points at.

    ``entries`` is a list of (slug, title, lesson_count). Before this existed
    /topics/ was a 404 that the search page linked to on every empty result set.
    """
    items = "\n".join(
        f'  <li><a href="/topics/{slug}/">{title}</a><span class="n">{count} lessons</span></li>'
        for slug, title, count in sorted(entries, key=lambda e: (-e[2], e[0]))
    )
    topics = ", ".join(title for _, title, _ in entries[:6])
    return TOPICS_INDEX_TEMPLATE.format(
        total=total,
        topic_count=len(entries),
        items=items,
        topics=topics,
        canonical=f"{SITE_URL}/topics/",
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

    # Topic pages (including the /topics/ index itself)
    lines.append(f"  <url><loc>{SITE_URL}/topics/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")
    for domain in domains:
        lines.append(f"  <url><loc>{SITE_URL}/topics/{domain}/</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")

    # Lesson pages
    for slug in lesson_slugs:
        lines.append(f"  <url><loc>{SITE_URL}/lessons/{slug}/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>")

    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


def _haystack(lesson: dict) -> str:
    return (lesson.get("title", "") + " " + lesson.get("summary", "") + " "
            + " ".join(lesson.get("tags", []))).lower()


def topic_plan(lessons: list) -> dict[str, tuple[str, int]]:
    """Map topic slug -> (generated HTML, lesson count) for every topic page."""
    pages: dict[str, tuple[str, int]] = {}

    by_domain: dict[str, list] = {}
    for lesson in lessons:
        domain = lesson.get("domain", "general")
        if domain in LOCALE_DIRS:
            continue  # translation dir leaked in as a domain
        by_domain.setdefault(domain, []).append(lesson)
    for domain, group in by_domain.items():
        slug = domain.lower().replace(" ", "-").replace("/", "-")
        pages[slug] = (build_topic_page(domain, group), len(group))

    for topic_slug, config in INTENT_TOPICS.items():
        matched = [l for l in lessons if any(kw in _haystack(l) for kw in config["keywords"])]
        if matched:
            pages[topic_slug] = (
                build_topic_page(config["title"], matched, description=config["description"]),
                len(matched))

    for topic_slug, blurb in LEGACY_TOPICS.items():
        if topic_slug in pages:
            continue
        tokens = [w for w in topic_slug.split("-") if len(w) >= 4]
        matched = [l for l in lessons if any(w in _haystack(l) for w in tokens)]
        if matched:
            pages[topic_slug] = (
                build_topic_page(topic_slug.title(), matched, description=blurb), len(matched))

    return pages


def plan_with_slugs(lessons: list, known_slugs: dict[str, str] | None = None
                    ) -> tuple[dict[str, dict], dict[str, str]]:
    """Plan every page, and return the lesson-id -> slug map that produced it.

    Slugs are **sticky**: a lesson keeps the URL it already has and only a new
    lesson gets one derived from its title. Deriving the slug from the title on
    every run meant that editing a title silently orphaned a live URL (the first
    wired run pruned 88 pages for exactly that reason) and left Google pointing at
    a 404. Sticky slugs are what a CMS does; the page content follows the title.
    """
    known = dict(known_slugs or {})
    titles = {lesson.get("id", ""): lesson.get("title", "") for lesson in lessons}

    seen_slugs: dict[str, str] = {}
    assigned: dict[str, str] = {}
    for lesson in lessons:                      # pass 1: keep the existing URL
        lesson_id = lesson.get("id", "")
        title = lesson.get("title", "")
        if not title:
            continue
        keep = known.get(lesson_id)
        if keep and keep not in seen_slugs:
            seen_slugs[keep] = title
            assigned[lesson_id] = keep
    for lesson in lessons:                      # pass 2: fresh lessons
        lesson_id = lesson.get("id", "")
        title = lesson.get("title", "")
        if not title or lesson_id in assigned:
            continue
        assigned[lesson_id] = unique_slug(title, seen_slugs)

    lesson_pages: dict[str, str] = {}
    lesson_slugs: list[str] = []
    for lesson in lessons:
        lesson_id = lesson.get("id", "")
        slug = assigned.get(lesson_id)
        if not slug or not lesson.get("title"):
            continue
        lesson["_slug"] = slug
        lesson_slugs.append(slug)
        lesson_pages[slug] = build_lesson_page(lesson)

    topics = topic_plan(lessons)
    index_entries = []
    for slug, (_html, count) in topics.items():
        title = INTENT_TOPICS[slug]["title"] if slug in INTENT_TOPICS else slug.title()
        index_entries.append((slug, title, count))

    files: dict[str, str] = {}
    for slug, html in lesson_pages.items():
        files[f"docs/lessons/{slug}/index.html"] = html
    for slug, (html, _count) in topics.items():
        files[f"docs/topics/{slug}/index.html"] = html
    files["docs/topics/index.html"] = build_topics_index(index_entries, len(lessons))
    files[str(SITEMAP)] = generate_sitemap(lesson_slugs, list(topics))
    return files, assigned


def plan(lessons: list, known_slugs: dict[str, str] | None = None) -> dict[str, dict]:
    """Everything this generator would write, as {relative path: text}."""
    return plan_with_slugs(lessons, known_slugs)[0]


def load_slug_map(root: Path = REPO) -> dict[str, str]:
    """The lesson-id -> slug map recorded by the previous run (may be empty)."""
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    slugs = manifest.get("slugs")
    return slugs if isinstance(slugs, dict) else {}


def discover_generated(root: Path) -> set[str]:
    """Paths this generator owns today: manifest ∪ marker-bearing pages on disk."""
    owned: set[str] = set()
    manifest = root / MANIFEST
    try:
        owned |= set(json.loads(manifest.read_text(encoding="utf-8")).get("pages", []))
    except (OSError, ValueError):
        pass
    for base in (LESSONS_DIR, TOPICS_DIR):
        for page in sorted((root / base).glob("*/index.html")):
            try:
                if GENERATOR_MARK in page.read_text(encoding="utf-8"):
                    owned.add(str(page.relative_to(root).as_posix()))
            except OSError:
                continue
    return owned


def sync(files: dict[str, str], *, root: Path = REPO,
         slugs: dict[str, str] | None = None) -> dict[str, list[str]]:
    """Write planned pages, prune pages this generator no longer produces."""
    result = {"written": [], "pruned": [], "kept": []}
    for rel, text in files.items():
        path = root / rel
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            result["written"].append(rel)

    for rel in sorted(discover_generated(root) - set(files)):
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if GENERATOR_MARK not in text:
            result["kept"].append(rel)   # not ours — never delete
            continue
        path.unlink()
        result["pruned"].append(rel)
        try:
            path.parent.rmdir()          # only succeeds when empty
        except OSError:
            pass

    # The lesson-id -> slug map is what makes URLs sticky across title edits; keep
    # the previous map when the caller does not supply one.
    slug_map = slugs if slugs is not None else load_slug_map(root)
    (root / MANIFEST).write_text(
        json.dumps({"generator": "scripts/build_lesson_pages.py",
                    "pages": sorted(files),
                    "slugs": dict(sorted(slug_map.items()))},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return result


def check(files: dict[str, str], *, root: Path = REPO) -> list[str]:
    """Report drift between disk and what this generator would write."""
    problems = []
    for rel, text in files.items():
        path = root / rel
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            problems.append(f"{rel}: missing (would be created)")
            continue
        if current != text:
            problems.append(f"{rel}: out of date")
    for rel in sorted(discover_generated(root) - set(files)):
        problems.append(f"{rel}: no longer generated (would be pruned)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report drift without writing; exit 1 if stale")
    parser.add_argument("--quiet", action="store_true", help="silent on success")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    lessons = json.loads((args.root / LESSONS_JSON).read_text(encoding="utf-8"))
    known_slugs = load_slug_map(args.root)
    files, slug_map = plan_with_slugs(lessons, known_slugs)
    if not args.quiet:
        print(f"Loaded {len(lessons)} lessons")
        print(f"Planned {sum(1 for p in files if p.startswith('docs/lessons/'))} lesson pages "
              f"+ {sum(1 for p in files if p.startswith('docs/topics/'))} topic pages + sitemap")

    if args.check:
        problems = check(files, root=args.root)
        if problems:
            print(f"❌ generated pages are stale ({len(problems)} path(s)):", file=sys.stderr)
            for problem in problems[:20]:
                print(f"  - {problem}", file=sys.stderr)
            if len(problems) > 20:
                print(f"  … and {len(problems) - 20} more", file=sys.stderr)
            print("\nFix: python3 scripts/build_lesson_pages.py", file=sys.stderr)
            return 1
        if not args.quiet:
            print("✅ every generated page matches the index")
        return 0

    result = sync(files, root=args.root, slugs=slug_map)
    if not args.quiet:
        sticky = sum(1 for lesson_id, slug in slug_map.items()
                     if known_slugs.get(lesson_id) == slug)
        print(f"Wrote/updated {len(result['written'])} pages, pruned {len(result['pruned'])} stale pages "
              f"({sticky} URL(s) kept sticky)")
        for rel in result["pruned"][:10]:
            print(f"  pruned {rel}")
        if len(result["pruned"]) > 10:
            print(f"  … and {len(result['pruned']) - 10} more")
        if result["kept"]:
            print(f"Kept {len(result['kept'])} unmanaged page(s) (no generator marker): "
                  + ", ".join(result["kept"][:5]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
