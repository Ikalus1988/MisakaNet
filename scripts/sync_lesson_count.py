#!/usr/bin/env python3
"""Lesson-count SSOT: keep every public "N lessons" claim equal to data/lessons.json.

Why this exists (2026-09-12)
----------------------------
The previous mechanism (``update_lessons_json.refresh_lesson_count_markers``,
audit QW6) substituted the literal number for each ``{{LESSONS_COUNT}}``
placeholder. Substitution *consumes* the placeholder, so the second run found
nothing left to replace and every managed count froze at its first
materialization:

    ARCHITECTURE.md  "358+ .md files"        (placeholder gone since 2026-09-05)
    README.md        "310+ failure lessons"
    docs/index.html  "435 indexed failure-recovery lessons"  (<meta description>
                      + og:description — the copy that appears in search results
                      and social cards)
    docs/search/…    "249 indexed failure-recovery lessons"

An SSOT that silently stops refreshing is worse than no SSOT: the tooling
advertises "counts cannot silently drift" while they drift by +15%.

This module is idempotent **by construction**: every managed site is a regex
whose numeric ``n`` group is re-matched on every run, so the tenth run is as
correct as the first. Two properties are pinned by
``tests/test_lesson_count_ssot.py``:

1. re-running with a *different* count rewrites the site again (no write-once);
2. a site whose wording changed is a **hard error**, never a silent skip —
   drift can throttle loudly instead of hiding.

Managed surfaces also normalise the trust vocabulary: ``verified failure
lessons`` is rewritten to ``indexed failure lessons`` because
``docs/trust-semantics.md`` reserves "verified" for manually fact-checked
lessons (✅ "N indexed failure-recovery lessons" / ❌ "N verified failure
lessons").

Deliberately NOT managed
------------------------
Historical snapshots keep the number they were written with: ``docs/blog/**``,
``docs/releases/**``, ``docs/reviews/**``, ``docs/prd/**``,
``docs/maintainer/handoff-*.md``, course bodies (``lessons/**``) and dated audit
reports. So does *testimony* (``docs/community/voices.json`` quotes a user
saying "200+ lessons") and any metric that is not the lesson total
(``18 domains``, ``52+ registered nodes``, per-domain topic pages).

Usage
-----
    python3 scripts/sync_lesson_count.py            # rewrite every managed site
    python3 scripts/sync_lesson_count.py --check     # CI gate: exit 1 on drift
    python3 scripts/sync_lesson_count.py --quiet
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_JSON = Path("data") / "lessons.json"
COUNT_FILE = Path("docs") / "_lessons_count.txt"


@dataclass(frozen=True)
class Site:
    """One managed count occurrence (or one family of identical occurrences).

    ``pattern`` must contain a named group ``n`` holding the count currently
    written in the file; ``replace`` is the re.Stemplate that writes the
    canonical count (may use ``\\g<k>`` backreferences and ``{n}``).
    ``min_matches`` guards against a partial loss of the surface (a meta tag
    quietly deleted) — it is a minimum, so adding another occurrence is fine.
    """

    path: str
    pattern: str
    replace: str
    note: str
    min_matches: int = 1

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.MULTILINE)


_COUNT = r"(?P<n>\d{2,4})"
# meta / og / JSON-LD / issue-template scale claim: "435 indexed failure-recovery
# lessons" (index.html, search page), "310+ indexed …" (mcp-quickstart), "249
# indexed …" (issue templates). The optional "+" is normalised away: the number
# is exact, and "N+" made two files disagree about the same claim.
_META = rf"{_COUNT}\+? indexed failure-recovery lessons"
_META_REPL = "{n} indexed failure-recovery lessons"
# "205+ verified failure lessons": the `\+?`/`(?:…)?` groups make the pattern
# match its own output ("378 indexed failure lessons"), which is what keeps the
# refresh idempotent. `tests/test_lesson_count_ssot.py` asserts that property for
# every row, so a row that cannot match its replacement fails before it ships.
_SCALE_CLAIM = rf"{_COUNT}\+? (?:verified |indexed )?failure lessons"


def _build_sites() -> tuple[Site, ...]:
    sites: list[Site] = []

    def add(path: str, pattern: str, replace: str, note: str, min_matches: int = 1) -> None:
        sites.append(Site(path, pattern, replace, note, min_matches))

    # ── repo-facing prose ───────────────────────────────────────────────────
    add("README.md", rf"{_COUNT}\+ failure lessons", "{n}+ failure lessons",
        "README tagline — quoted by GitHub search and social cards")
    add("ARCHITECTURE.md", rf"Shared knowledge \({_COUNT}\+ indexed lessons\)",
        "Shared knowledge ({n}+ indexed lessons)",
        "architecture tree comment; reports the index metric, not raw .md count")

    # ── public website metadata (static: no JS can fix these) ───────────────
    add("docs/index.html", _META, _META_REPL,
        "<meta description> + og:description + JSON-LD (search/social copy)", 3)
    add("docs/search/index.html", _META, _META_REPL,
        "search page <meta description> + og:description", 2)
    add("docs/mcp-quickstart.md", _META, _META_REPL, "MCP quickstart first paragraph")

    # ── website body fallbacks (JS overwrites them once data/lessons.json loads,
    #    but crawlers and no-JS readers only ever see the static text) ────────
    add("docs/index.html", rf'(<span id="lesson-count-(?:hero|product)">){_COUNT}\+?(</span>)',
        r"\g<1>{n}\g<3>", "hero + product count spans", 2)
    add("docs/index.html", rf'(id="lesson-count-search"[^>]*>){_COUNT} indexed lessons',
        r"\g<1>{n} indexed lessons", "search-panel fallback line")
    add("docs/index.html", rf"(_allLessons\.length : ){_COUNT}",
        r"\g<1>{n}", "JS fallback count shown before the index finishes loading")

    # ── agent-facing entry points ───────────────────────────────────────────
    add("docs/llms.txt", _SCALE_CLAIM, "{n} indexed failure lessons",
        "llms.txt scale claim (trust vocabulary enforced: indexed, not verified)")
    add("docs/.well-known/llms.txt", _SCALE_CLAIM, "{n} indexed failure lessons",
        "served copy of llms.txt")
    # Agent-discovery documents: what crawlers and MCP clients read before they
    # ever see the site. They advertised "300+ verified debugging lessons" — a
    # stale count *and* the trust claim docs/trust-semantics.md forbids.
    for _path in ("docs/.well-known/mcp.json", "docs/.well-known/agent.json",
                  "docs/.well-known/agent-card.json"):
        add(_path, _SCALE_CLAIM, "{n} indexed failure lessons", "agent-discovery description")
    # The glama connector document uses its own phrasing. It was served live at
    # https://misakanet.org/.well-known/glama.json while claiming "320+ … lessons"
    # at 380+ lessons and a version three releases behind (found 2026-09-12) — so it
    # is registered here as well as in the version line.
    add("docs/.well-known/glama.json", rf"{_COUNT}\+ indexed failure-recovery lessons",
        "{n}+ indexed failure-recovery lessons", "glama connector description")
    add("docs/skill.md", rf"\*\*{_COUNT}\+ lessons\*\*", "**{n}+ lessons**",
        "skill manifest tagline")
    add("JOIN.md", rf"\*\*{_COUNT}\+ lessons\*\*", "**{n}+ lessons**",
        "contributor onboarding tagline")

    # ── integration guides ──────────────────────────────────────────────────
    for _path in ("docs/integrations/cursor.md", "docs/integrations/continue.md",
                  "docs/integrations/claude-code.md"):
        add(_path, _SCALE_CLAIM, "{n} indexed failure lessons",
            "integration landing line")
    add("docs/integrations/README.md",
        rf"(Search ){_COUNT}\+? (?:indexed )?failure-recovery lessons",
        r"\g<1>{n} indexed failure-recovery lessons", "integrations index intro")
    add("docs/install/index.html", rf"{_COUNT}\+ lessons across 18 domains",
        "{n}+ lessons across 18 domains", "install page feature list")

    # ── GitHub-facing automation ────────────────────────────────────────────
    add(".github/ISSUE_TEMPLATE/config.yml", _META, _META_REPL,
        "issue-template chooser description")
    add(".github/ISSUE_TEMPLATE/ai-bounty-template.md", _META, _META_REPL,
        "AI-bounty issue preamble")
    # NOT managed: .github/workflows/pr-thank-you.yml. It used to hardcode
    # "MisakaNet's 298+ lessons", but GITHUB_TOKEN is refused any push that touches
    # .github/workflows/** ("refusing to allow a GitHub App to create or update
    # workflow ... without `workflows` permission") — so managing it made the daily
    # update job fail at push time the first time a count actually changed (caught
    # 2026-09-12 by dispatching that job). It now reads docs/_lessons_count.txt at
    # runtime, which this script writes.

    # ── docs that quote tool output ─────────────────────────────────────────
    add("docs/worker-bm25-search.md", rf"Loaded {_COUNT} lessons", "Loaded {n} lessons",
        "sample `doctor` output in the BM25 doc")

    return tuple(sites)


SITES: tuple[Site, ...] = _build_sites()


def canonical_count(root: Path = REPO) -> int:
    """Lesson count from the single source of truth: data/lessons.json."""
    data = json.loads((root / LESSONS_JSON).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError("data/lessons.json root must be a list")
    return len(data)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


@dataclass
class _Scan:
    site: Site
    text: str
    hits: list[re.Match[str]]


def _scan(root: Path, sites: tuple[Site, ...]) -> tuple[list[_Scan], list[str]]:
    """Collect every match; report missing files and non-matching patterns."""
    scans: list[_Scan] = []
    errors: list[str] = []
    for site in sites:
        path = root / site.path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{site.path}: unreadable ({exc}) — {site.note}")
            continue
        hits = list(site.compiled().finditer(text))
        if len(hits) < site.min_matches:
            errors.append(
                f"{site.path}: pattern {site.pattern!r} matched {len(hits)}×, "
                f"expected ≥{site.min_matches} — {site.note}. "
                "The sentence was reworded: fix the file or update SITES."
            )
            continue
        scans.append(_Scan(site, text, hits))
    return scans, errors


def stale_entries(count: int, *, root: Path = REPO,
                  sites: tuple[Site, ...] = SITES) -> list[str]:
    """Every health problem with the count surface; empty list == healthy."""
    scans, errors = _scan(root, sites)
    for scan in scans:
        for hit in scan.hits:
            if hit.group("n") != str(count):
                found = " ".join(hit.group(0).split())
                if len(found) > 60:
                    found = f"…{found[-60:]}"
                errors.append(
                    f"{scan.site.path}:{_line_of(scan.text, hit.start())}: "
                    f"{found!r} should be {count} — {scan.site.note}"
                )
    count_file = root / COUNT_FILE
    try:
        disk = count_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        errors.append(f"{COUNT_FILE}: unreadable ({exc})")
    else:
        if disk != str(count):
            errors.append(f"{COUNT_FILE}: says {disk!r}, data/lessons.json says {count}")
    return errors


def sync_all(count: int, *, root: Path = REPO, sites: tuple[Site, ...] = SITES,
             dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Rewrite every managed site to ``count``. Returns (changes, errors).

    Rows are applied **per file, onto one accumulating text**: several rows can
    target the same file (docs/index.html has four), and writing each row from
    the text captured at scan time made every write clobber the previous row's
    (found the hard way — only the last row survived on disk).
    """
    scans, errors = _scan(root, sites)
    changes: list[str] = []
    by_path: dict[str, list[_Scan]] = {}
    for scan in scans:
        by_path.setdefault(scan.site.path, []).append(scan)

    for path, path_scans in by_path.items():
        original = path_scans[0].text
        text = original
        total = 0
        for scan in path_scans:
            text, replaced = scan.site.compiled().subn(
                scan.site.replace.format(n=count), text)
            total += replaced
        if total and text != original:
            if not dry_run:
                (root / path).write_text(text, encoding="utf-8")
            changes.append(f"{path}: {total} site(s) → {count}")

    count_file = root / COUNT_FILE
    try:
        current = count_file.read_text(encoding="utf-8").strip()
    except OSError:
        current = None
    if current != str(count):
        if not dry_run:
            count_file.parent.mkdir(parents=True, exist_ok=True)
            count_file.write_text(f"{count}\n", encoding="utf-8")
        changes.append(f"{COUNT_FILE}: {current or 'missing'} → {count}")
    return changes, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync public lesson counts with data/lessons.json (idempotent).")
    parser.add_argument("--check", action="store_true",
                        help="verify only; exit 1 on stale or unmatched counts")
    parser.add_argument("--quiet", action="store_true", help="silent on success")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    count = canonical_count(args.root)

    if args.check:
        problems = stale_entries(count, root=args.root)
        if problems:
            print(f"❌ lesson-count SSOT drift (canonical = {count}):", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            print("\nFix: python3 scripts/sync_lesson_count.py   "
                  "(or update SITES if a sentence was intentionally reworded)",
                  file=sys.stderr)
            return 1
        if not args.quiet:
            print(f"✅ every managed lesson count == {count}")
        return 0

    changes, errors = sync_all(count, root=args.root)
    if changes:
        print(f"✅ lesson counts synced to {count}:")
        for change in changes:
            print(f"  - {change}")
    elif not args.quiet:
        print(f"✅ already consistent: every managed lesson count == {count}")
    if errors:
        print("❌ some managed sites could not be refreshed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
