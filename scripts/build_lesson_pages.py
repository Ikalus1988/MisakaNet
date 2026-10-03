#!/usr/bin/env python3
"""Generate static lesson and topic pages from lessons.json for SEO.

Usage:
    python3 scripts/build_lesson_pages.py            # write/refresh every page
    python3 scripts/build_lesson_pages.py --check    # report drift, write nothing (exit 1 if stale)

Two gates the plan cannot see (2026-09-30)
------------------------------------------
`check()` compares this generator's plan against the pages this generator wrote, and both
sides are derived from `data/lessons.json` — so it can only ever report drift *inside* the
plan. Two defects lived in that blind spot and are now separate, named failures:

* **An unpageable lesson.** Both slug passes used to `continue` when a lesson had no
  `title`, and the page loop skipped it a third time, so the lesson got no page and nothing
  said so. `unpageable_lessons()` names every lesson that can never get a page (no title, a
  non-string title, or a title that slugifies to nothing) and `main()` refuses to run.
* **A corpus lesson with no page.** `corpus_page_problems()` walks the corpus itself and
  resolves each lesson against the slug map recorded by the previous run in
  `docs/.generated-pages.json` (or the `/lessons/<id>/` alias page), which is what makes it
  able to notice a lesson that was never planned at all.

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
REDIRECTS = Path("docs") / "_redirects"
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

    # Non-published lessons are served and indexed (the MCP side already decided that in #2423,
    # which makes `status` visible on every hit so a caller can filter). The page template was the
    # half that never got the same treatment: a draft lesson renders with an identical <title> and
    # <h1> to a published one, so a reader — or a crawler building a snippet — cannot tell it is
    # unfinished. Measured 2026-10-04 against production: `/lessons/fanuc-alarm-code-reference/`
    # (a draft) contained zero occurrences of "draft" or "unpublished", while the MCP response for
    # the same lesson carried `status: "draft"`.
    #
    # This does not change whether drafts are published or indexed — that is a product decision and
    # out of scope here. It makes the state visible to whoever lands on the page, which is the same
    # rule the API already follows.
    status = (lesson.get("status") or "published").strip().lower()
    is_published = status == "published"

    description = f"{summary[:150]}..." if len(summary) > 150 else summary
    if not description:
        # "indexed", not "verified": docs/trust-semantics.md reserves "verified"
        # for lessons fact-checked against source material.
        description = f"Indexed failure lesson: {title}. From MisakaNet — Git-backed failure lesson network."
    if not is_published:
        # A search snippet built from the description is exactly where an unfinished lesson is most
        # likely to be mistaken for a settled one, so the state has to survive into the meta tag too.
        description = f"Draft (not published): {description}"

    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags[:6])

    banner_html = "" if is_published else (
        # Styled inline rather than via the shared <style> block on purpose. A rule in the template
        # would regenerate all 464 lesson pages for a change that only concerns 30 of them, and a
        # 464-file diff makes a one-line feature unreviewable. Inline keeps the diff to exactly the
        # pages that changed meaning.
        '<div class="draft-banner" role="note" style="border:1px solid rgba(210,153,34,0.5);'
        "background:rgba(210,153,34,0.12);color:#e3b341;border-radius:6px;padding:10px 14px;"
        'margin-bottom:20px;font-size:13px;line-height:1.5;">'
        f"<strong>Draft — not published.</strong> "
        f"This lesson is <code style=\"background:rgba(210,153,34,0.15);padding:1px 5px;"
        f'border-radius:3px;">{status}</code> and may be incomplete or wrong. '
        f'The MCP API returns it with <code>status: "{status}"</code> so callers can filter it.</div>'
    )

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

    if banner_html:
        # Prepended rather than interpolated into the f-string below: an empty `{banner_html}` still
        # emits its newline, which put a blank line after <body> on all 434 published pages.
        body = banner_html + "\n" + body

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

    # Static pages.
    # The path shape has to match how each one is actually served, and the two differ in this repo:
    # `/search/` is a directory (`docs/search/index.html`), while `docs/troubleshooting.md` is a
    # markdown file served verbatim at `/troubleshooting.md` — the same as `docs/agents/repo-operations.md`.
    # Advertising the directory form of the `.md` page gave a 404 that no check caught: measured
    # 2026-10-04, `https://misakanet.org/troubleshooting/` → 404 while `/troubleshooting.md` → 200.
    # `tests/test_sitemap_urls_resolve.py` now asserts each entry maps to a real file.
    static = [
        ("https://misakanet.org/", "weekly", "1.0"),
        ("https://misakanet.org/search/", "weekly", "0.9"),
        ("https://misakanet.org/troubleshooting.md", "weekly", "0.8"),
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


def build_id_alias_page(lesson_id: str, slug: str) -> str:
    """A tiny redirect page at `/lessons/<id>/` for a lesson whose page slug differs from its id.

    Why this exists (2026-09-29): `misakanet_search` returns the frontmatter `id`, `docs/llms.txt` tells
    readers that static pages live at `https://misakanet.org/lessons/<slug>/`, and the page slug is
    **title-derived** (`slugify(title)`, sticky across renames only through the manifest). Measured on the
    live site: **73 of 426 lessons** have an id that is not their slug, so `curl /lessons/<id>/` answered
    **404** for 17% of the corpus while the page existed under another name — the documented mapping
    between a search hit and its page simply did not hold.

    Two ways to close that: publish a canonical URL in the API (needs the slug in D1, i.e. a second
    implementation of `slugify` in JavaScript — the drift this repository keeps paying for), or make the id
    resolve. This is the second one: static, generated from the *same* slug map the pages use, no runtime
    cost, no API contract change, and it makes the documented pattern true under either reading of
    "slug". `rel="canonical"` keeps search engines pointed at the real page, which is also why the alias is
    deliberately absent from the sitemap.
    """
    target = f"/lessons/{slug}/"
    # The canonical is **site-relative** on purpose (2026-09-29). `rel="canonical"` resolves a relative URL
    # against the page, so the origin is not needed here, and a generated file whose only content is a
    # redirect should not carry one.
    #
    # **Correction (2026-09-30).** The original comment claimed the absolute URL was what tripped GitHub's
    # secret-scanning heuristic on two alias pages (`HARDCODED_SECRET`, plugin-scanner 2.2.0). That was
    # wrong: after this file switched to a relative canonical the same two pages were flagged again at the
    # same line, so the match is the **slug text** — "Idempotent task claim **keys** for snipers", "Disk full
    # from agent tmp dirs — **GC pattern**" — which is a public URL built from a lesson title, not a
    # credential. `scripts/check_published_secrets.py` is green over all 739 published prose files and
    # neither lesson source contains credential-shaped material, so those alerts are false positives and are
    # disposed of as such. Removing the HTML entirely (one `docs/_redirects` table instead of 73 redirect
    # pages) is the structural alternative — see `build_redirects_file`, which now emits that table.
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        f'<title>Moved — {lesson_id}</title>\n'
        f'<link rel="canonical" href="{target}">\n'
        f'<meta http-equiv="refresh" content="0; url={target}">\n'
        '</head>\n<body>\n'
        f'<p>{GENERATOR_MARK} — this lesson lives at <a href="{target}">{target}</a>.</p>\n'
        '</body>\n</html>\n'
    )


def build_redirects_file(rules: list[tuple[str, str]]) -> str:
    """`docs/_redirects` — the id -> slug table as a platform redirect table instead of 111 stub pages.

    Platform support (2026-10-04, verified before the stub pages were retired): the site is a Cloudflare
    **Workers Static Assets** Worker, not Pages — `wrangler.jsonc` (`misakanet-web`) names `docs/` as
    `assets.directory` and no `main`, so no Worker code runs on these paths. That matters because the
    documented rule is that `_redirects` is *not* applied to requests served by Worker code; with no
    script there is nothing to be skipped. Confirmed from the inside rather than assumed: `docs/_headers`
    sits in the same directory through the same parser, and all five of its rules are present verbatim in
    the live response for `/` and `/lessons/<slug>/` (measured 2026-10-04). The documented limits are 2,000
    static redirects and a 1,000-character line; 111 rules is 5% of the first and the longest line here is
    far under the second.

    **301, not the 302 default.** A slug is sticky — `plan_with_slugs` keeps a lesson on the URL it already
    has — so `/lessons/<id>/` is a permanent address and 301 is the truthful status. It is also the one the
    old stub could not express: a `<meta http-equiv="refresh">` is invisible to every client that is not a
    browser. `curl`, an MCP agent resolving a `misakanet_search` hit, a feed reader and a link checker all
    saw a 200 with a small HTML body, which is why the GitHub Pages side of this repository could read the
    alias as "a real page exists here" and why the secret-scanner alerts (recorded above) kept firing on the
    slug text inside those bodies.

    The source keeps its trailing slash because that is the URL the stub served: static assets default to
    `html_handling: auto-trailing-slash`, and `/lessons/<id>` (no slash) is a different request from
    `/lessons/<id>/`. Rules are sorted so the file is byte-stable across runs — an unsorted table would make
    every corpus reshuffle a spurious diff.

    **Targets are written as literal UTF-8, never percent-encoded, and that is deliberate.** Three rules
    redirect to a Chinese slug (`fanuc-ls-程序解析段标记必须行首锚定否则注释会截断程序体` and two others,
    all three verified 200 on the live site 2026-10-04). A `Location` header must be an ASCII URI per
    RFC 7231, so pre-encoding looks tidy — but the file is a UTF-8 *text* file that the platform parses,
    so a pre-encoded `%E7%A8%8B...` may be taken as already-encoded and emitted as `%25E7%25A8%25...`,
    which is a broken link that still looks well-formed in review. Emitting the character and letting the
    platform encode is the direction that cannot double-encode. It is the one behaviour here measured
    against production rather than assumed: the 301s ship first with the stub pages still in place, so a
    wrong `Location` shows up as a live probe before anything is deleted.
    """
    lines = [
        "# Generated by scripts/build_lesson_pages.py — do not edit by hand.",
        "# `/lessons/<id>/` -> `/lessons/<slug>/` for every lesson whose id is not its page slug.",
        f"# {len(rules)} rules. Cloudflare Workers Static Assets `_redirects`; see build_redirects_file().",
    ]
    lines += [f"/lessons/{lesson_id}/ /lessons/{slug}/ 301" for lesson_id, slug in sorted(rules)]
    return "\n".join(lines) + "\n"


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
    # Every id resolves too, so `/lessons/<id>/` (what a search hit hands a consumer) is not a 404 for the
    # 73 lessons whose slug is title-derived. A real page always wins: if an id happens to equal another
    # lesson's slug, the alias is dropped rather than overwriting it.
    #
    # 2026-10-04: the alias is now published twice on purpose — as a `docs/_redirects` rule *and* as the
    # stub page — because a redirect is "always followed, regardless of whether or not an asset matches",
    # so the rule shadows the file it duplicates. That makes this step safe to land on its own: if the
    # platform honours the table the stub is simply never reached, and if it does not, the stub is still
    # on disk and still answers. Neither branch can 404. Retiring the stubs is a second, separately
    # revertible change made only after the 301s are observed on the live site.
    aliases = 0
    alias_rules: list[tuple[str, str]] = []
    for lesson in lessons:
        lesson_id = str(lesson.get("id") or "")
        slug = assigned.get(lesson_id)
        if not lesson_id or not slug or lesson_id == slug:
            continue
        path = f"docs/lessons/{lesson_id}/index.html"
        if path in files:
            continue
        files[path] = build_id_alias_page(lesson_id, slug)
        alias_rules.append((lesson_id, slug))
        aliases += 1
    # Unconditional on purpose. The prune guard only deletes a file that carries GENERATOR_MARK, and a
    # `_redirects` table has no reason to carry it, so a table that stopped being emitted would sit on
    # disk forever, stale and still live, rather than being cleaned up with the rest of the output.
    # Always emitting it keeps the path in `files` (and so in the manifest) on every run. A comments-only
    # table is valid — Cloudflare ignores `#` lines — so the zero-alias case costs nothing but a header.
    files[REDIRECTS.as_posix()] = build_redirects_file(alias_rules)
    for slug, (html, _count) in topics.items():
        files[f"docs/topics/{slug}/index.html"] = html
    files["docs/topics/index.html"] = build_topics_index(index_entries, len(lessons))
    # .as_posix(), never `str(SITEMAP)`: every key of `files` is a repo-relative POSIX path
    # (that is the form `docs/.generated-pages.json` is committed in and the form
    # discover_generated() reports), and `str(Path)` on Windows would make this one key
    # `docs\sitemap.xml` — which the committed manifest then reads back as a page this run
    # no longer generates, so `check()` demands a prune of the live sitemap.
    files[SITEMAP.as_posix()] = generate_sitemap(lesson_slugs, list(topics))
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


def unpageable_lessons(lessons: list) -> list[str]:
    """Lessons that can never get a page, each named by id with the reason why.

    Why this exists (2026-09-30): both passes of `plan_with_slugs` had `if not title: continue`
    and the page loop skipped a lesson with no title a third time, so an untitled lesson got no
    page and **no gate fired**. `--check` cannot see it either — it compares this generator's
    plan against the pages this generator wrote, and both come from the same index, so a lesson
    that was never planned cannot show up as drift. `scripts/lesson_gate.py` requires a title on
    the PR path, but nothing checked the *index*: a `title:` key with an empty value, or a title
    that `slugify()` empties out (e.g. one made only of emoji), reached the generator unopposed.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for index, lesson in enumerate(lessons):
        lesson_id = lesson.get("id") or f"<entry #{index} with no id>"
        if lesson_id in seen:
            continue
        seen.add(lesson_id)
        title = lesson.get("title")
        if not isinstance(title, str) or not title.strip():
            problems.append(
                f"{lesson_id}: no usable `title` (got {title!r}) — no slug can be derived, so no "
                f"page is generated and nothing the lesson owns is reachable")
        elif not slugify(title):
            problems.append(
                f"{lesson_id}: title {title!r} slugifies to an empty string — no page URL can be "
                f"derived from it")
    return problems


def corpus_page_problems(lessons: list, *, root: Path = REPO) -> list[str]:
    """Every lesson in the corpus must have a page on disk — derived WITHOUT the plan.

    The page URL is not re-derived from the title while a slug is on record: the slug map the
    previous run wrote to `docs/.generated-pages.json` is the authority, because slugs are sticky
    and re-deriving on every run is what orphaned 88 live URLs once. `docs/lessons/<id>/index.html`
    is accepted as well, since the generator also writes an id alias page for a lesson whose id
    differs from its slug (2026-09-29). Accepting the alias cannot hide a missing live page: the
    alias is a redirect *to* `/lessons/<slug>/`, and the plan-versus-disk comparison in the same
    `--check` run still carries the slug page, so the missing URL is reported on its own (pinned in
    tests/test_lesson_page_generator.py). Only a lesson **absent from the slug map** is probed at its
    title-derived URL, and that is reported as its own defect rather than counted as healthy: the
    recorded slug is what keeps a live URL sticky.

    This reads the corpus and the manifest, never `plan_with_slugs()`, so it can notice a lesson the
    plan left out — the class `check()` is structurally blind to.
    """
    if not lessons:
        return []
    slugs = load_slug_map(root)
    if not slugs:
        # One named problem, not one per lesson: with no slug map every URL is unknown, and
        # "no page on disk" would be said about the 70+ lessons whose slug differs from their id.
        return [f"{MANIFEST.as_posix()} carries no lesson-id -> slug map, so no lesson's page URL "
                f"is knowable — run `python3 scripts/build_lesson_pages.py` to record it"]

    problems: list[str] = []
    for lesson in lessons:
        lesson_id = lesson.get("id") or ""
        if not lesson_id:
            problems.append("a corpus entry has no `id` — nothing can map it to a page")
            continue
        # `or None` is load-bearing: `plan_with_slugs` writes `""` into the slug map for a title that
        # slugifies to nothing, and `""` would otherwise index `docs/lessons/index.html` — the lessons
        # *directory* index — as if it were this lesson's page. Found 2026-09-30 by removing the
        # unpageable gate and watching this check accept the directory index as a page.
        slug = slugs.get(lesson_id) or None
        alias_page = LESSONS_DIR / lesson_id / "index.html"
        if slug is not None:
            candidates = [LESSONS_DIR / slug / "index.html", alias_page]
            # Deliberately NOT the title-derived URL: when a slug is on record, a page at another
            # URL does not make the live one reachable.
            if any((root / candidate).is_file() for candidate in candidates):
                continue
            problems.append(
                f"lesson {lesson_id!r}: no page on disk — looked for "
                + " and ".join(candidate.as_posix() for candidate in candidates))
            continue
        # No recorded slug: the manifest is behind the corpus (a lesson new to the index, or a
        # hand-trimmed manifest). Say which of the two it is; both are failures, for the reason
        # `plan_with_slugs` gives — an unrecorded slug is a URL that can be re-derived and orphaned.
        derived = slugify(lesson.get("title") or "") if isinstance(lesson.get("title"), str) else ""
        derived_page = LESSONS_DIR / derived / "index.html" if derived else None
        found = next((page for page in (derived_page, alias_page)
                      if page is not None and (root / page).is_file()), None)
        if found is None:
            problems.append(
                f"lesson {lesson_id!r}: no page on disk and no slug recorded for its id in "
                f"{MANIFEST.as_posix()} — the page generator has never planned it")
        else:
            problems.append(
                f"lesson {lesson_id!r}: {MANIFEST.as_posix()} records no slug for its id, though the "
                f"page {found.as_posix()} is on disk — the recorded slug is what keeps a live URL "
                f"sticky, so the next run can re-derive it and orphan this page")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report drift without writing; exit 1 if stale")
    parser.add_argument("--quiet", action="store_true", help="silent on success")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    lessons = json.loads((args.root / LESSONS_JSON).read_text(encoding="utf-8"))

    # A lesson that can never get a page is a hard error in BOTH modes, and it is reported before
    # anything is written: planning around it is what used to leave it silently page-less
    # (2026-09-30). Refusing rather than writing a half-synced tree is the same call
    # `update_lessons_json.py` makes when the count SSOT cannot be refreshed.
    unpageable = unpageable_lessons(lessons)
    if unpageable:
        print(f"❌ {len(unpageable)} lesson(s) in {LESSONS_JSON.as_posix()} can never get a page:",
              file=sys.stderr)
        for item in unpageable[:20]:
            print(f"  - {item}", file=sys.stderr)
        if len(unpageable) > 20:
            print(f"  … and {len(unpageable) - 20} more", file=sys.stderr)
        print("\nFix: give each one a real `title` in its frontmatter (lesson_gate.py requires one). "
              "Until then no page is generated for it and the site has nothing behind a search hit.",
              file=sys.stderr)
        return 1

    known_slugs = load_slug_map(args.root)
    files, slug_map = plan_with_slugs(lessons, known_slugs)
    if not args.quiet:
        print(f"Loaded {len(lessons)} lessons")
        print(f"Planned {sum(1 for p in files if p.startswith('docs/lessons/'))} lesson pages "
              f"+ {sum(1 for p in files if p.startswith('docs/topics/'))} topic pages + sitemap")

    if args.check:
        # Two independent gates. `check()` is the plan-versus-disk comparison; the corpus walk is
        # the relation the plan cannot express, so the two are reported separately (2026-09-30).
        problems = check(files, root=args.root)
        corpus_problems = corpus_page_problems(lessons, root=args.root)
        if problems or corpus_problems:
            if problems:
                print(f"❌ generated pages are stale ({len(problems)} path(s)):", file=sys.stderr)
                for problem in problems[:20]:
                    print(f"  - {problem}", file=sys.stderr)
                if len(problems) > 20:
                    print(f"  … and {len(problems) - 20} more", file=sys.stderr)
            if corpus_problems:
                print(f"❌ the corpus and the pages on disk disagree "
                      f"({len(corpus_problems)} problem(s)):", file=sys.stderr)
                for problem in corpus_problems[:20]:
                    print(f"  - {problem}", file=sys.stderr)
                if len(corpus_problems) > 20:
                    print(f"  … and {len(corpus_problems) - 20} more", file=sys.stderr)
            print("\nFix: python3 scripts/build_lesson_pages.py", file=sys.stderr)
            return 1
        if not args.quiet:
            print("✅ every generated page matches the index")
            print(f"✅ every one of the {len(lessons)} lessons in {LESSONS_JSON.as_posix()} has a page")
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
