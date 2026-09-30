#!/usr/bin/env python3
"""Rebuild lessons/index.md from the lesson corpus (frontmatter SSOT).

Usage:
    python3 scripts/rebuild_lessons_index.py          # rebuild in-place
    python3 scripts/rebuild_lessons_index.py --check   # verify only; exit 1 on drift

The index was hand-maintained and drifted badly (#1661): 25 dangling paths,
136 title mismatches, 85 domain mismatches, 52 tag mismatches against the
corpus on 2026-09-13.  This script regenerates it deterministically from
frontmatter so it is always correct after the daily update-lessons.yml run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
INDEX_PATH = LESSONS_DIR / "index.md"

# Files to skip when scanning for lessons
_SKIP = frozenset({"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"})

# Subdirectories to scan (order determines sort precedence)
_SUBDIRS = ("core", "contrib", "en")

# -- Frontmatter parser -------------------------------------------------------
# Replicates lesson_gate.parse_frontmatter logic inline to avoid importing
# the full gate module (which has heavy side-effects and test-only fixtures).

import json
import re

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    """Extract frontmatter as a dict.  Supports JSON and YAML."""
    m = _FM_RE.match(text)
    if not m:
        return {}
    raw = m.group(1).strip()
    # Try JSON first (legacy)
    try:
        fm = json.JSONDecoder().raw_decode(raw)[0]
        if isinstance(fm, dict):
            return fm
    except json.JSONDecodeError:
        pass
    # Try YAML
    try:
        import yaml

        fm = yaml.safe_load(raw)
        if isinstance(fm, dict):
            return fm
    except Exception:
        pass
    return {}


# -- Index builder -------------------------------------------------------------

_HEADER = (
    "# MisakaNet Shared Lessons\n"
    "\n"
    "每条 lesson 包含踩坑记录、修复方法和验证方式，跨节点自动同步。\n"
    "\n"
    "## 目录\n"
    "\n"
    "| Lesson | Domain | Tags | Source |\n"
    "|--------|--------|------|--------|\n"
)


def _scan_lessons() -> list[dict]:
    """Scan corpus and return sorted list of lesson metadata dicts."""
    entries: list[dict] = []
    for subdir in _SUBDIRS:
        d = LESSONS_DIR / subdir
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            if md.name in _SKIP:
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = _parse_frontmatter(text)
            title = fm.get("title", md.stem)
            domain = fm.get("domain", "")
            tags = fm.get("tags", [])
            source = fm.get("source", "")
            # Normalize tags to list of strings
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            rel = md.relative_to(LESSONS_DIR)
            entries.append(
                {
                    "path": str(rel),
                    "title": str(title),
                    "domain": str(domain),
                    "tags": [str(t) for t in tags],
                    "source": str(source),
                }
            )
    # Sort by path for deterministic output
    entries.sort(key=lambda e: e["path"])
    return entries


def _format_line(e: dict) -> str:
    """Format one index line matching existing convention."""
    tags_str = ", ".join(f'"{t}"' for t in e["tags"])
    source = e["source"]
    # Match existing format: - [Title](path) | domain | "tag1", "tag2" | source
    parts = [
        f'- [{e["title"]}]({e["path"]})',
        e["domain"],
        tags_str,
        source,
    ]
    return " | ".join(parts) + "\n"


def build_index() -> str:
    """Build the full index.md content string."""
    entries = _scan_lessons()
    lines = [_HEADER]
    for e in entries:
        lines.append(_format_line(e))
    return "".join(lines)


# -- Diff checker --------------------------------------------------------------

def _parse_existing(path: Path) -> list[dict]:
    """Parse existing index.md into a list of {path, title, domain, tags, source}."""
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- ["):
            continue
        # Format: - [Title](path) | domain | "tag1", "tag2" | source
        m = re.match(r"^- \[(.+?)\]\((.+?)\)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*)$", line)
        if not m:
            continue
        title, path_str, domain, tags_raw, source = m.groups()
        # Parse tags
        tags = re.findall(r'"([^"]*)"', tags_raw)
        entries.append(
            {
                "path": path_str.strip(),
                "title": title.strip(),
                "domain": domain.strip(),
                "tags": tags,
                "source": source.strip(),
            }
        )
    return entries


def _diff_entries(old: list[dict], new: list[dict]) -> list[str]:
    """Return human-readable diff lines between old and new index entries."""
    diffs: list[str] = []
    old_by_path = {e["path"]: e for e in old}
    new_by_path = {e["path"]: e for e in new}

    # Removed
    for p in sorted(set(old_by_path) - set(new_by_path)):
        diffs.append(f"REMOVED  {p}: {old_by_path[p]['title']}")

    # Added
    for p in sorted(set(new_by_path) - set(old_by_path)):
        diffs.append(f"ADDED    {p}: {new_by_path[p]['title']}")

    # Changed
    for p in sorted(set(old_by_path) & set(new_by_path)):
        o, n = old_by_path[p], new_by_path[p]
        for field in ("title", "domain", "source"):
            if o[field] != n[field]:
                diffs.append(f"CHANGED  {p} {field}: {o[field]!r} -> {n[field]!r}")
        if o["tags"] != n["tags"]:
            diffs.append(f"CHANGED  {p} tags: {o['tags']} -> {n['tags']}")

    return diffs


# -- CLI -----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild lessons/index.md from corpus frontmatter.")
    parser.add_argument("--check", action="store_true",
                        help="verify only; exit 1 on drift")
    parser.add_argument("--quiet", action="store_true", help="silent on success")
    args = parser.parse_args(argv)

    new_content = build_index()

    if args.check:
        old_entries = _parse_existing(INDEX_PATH)
        new_entries = _scan_lessons()
        diffs = _diff_entries(old_entries, new_entries)
        if diffs:
            print(f"❌ lessons/index.md is out of sync ({len(diffs)} differences):", file=sys.stderr)
            for d in diffs[:20]:
                print(f"  {d}", file=sys.stderr)
            if len(diffs) > 20:
                print(f"  ... and {len(diffs) - 20} more", file=sys.stderr)
            print("\nFix: python3 scripts/rebuild_lessons_index.py", file=sys.stderr)
            return 1
        if not args.quiet:
            print("✅ lessons/index.md is up to date")
        return 0

    # Rebuild mode
    INDEX_PATH.write_text(new_content, encoding="utf-8")
    entry_count = len(_scan_lessons())
    print(f"✅ Rebuilt lessons/index.md ({entry_count} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())