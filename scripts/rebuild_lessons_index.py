#!/usr/bin/env python3
"""Rebuild lessons/index.md from lesson file frontmatter.

Usage:
    python3 scripts/rebuild_lessons_index.py          # rebuild lessons/index.md
    python3 scripts/rebuild_lessons_index.py --check   # CI gate: exit 1 on drift

The index is a markdown table of all lessons with title, domain, tags, and source
from their YAML frontmatter. Output is deterministic (sorted by path).
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(1)

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
INDEX_FILE = LESSONS_DIR / "index.md"

SCAN_DIRS = ["core", "contrib", "en"]
EXCLUDE_FILES = {"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"}

HEADER = """\
# MisakaNet Shared Lessons

> Auto-generated from lesson frontmatter. Do not edit manually.
> Run `python3 scripts/rebuild_lessons_index.py` to regenerate.

每条 lesson 包含踩坑记录、修复方法和验证方式，跨节点自动同步。
---

## 目录

| Lesson | Domain | Tags | Source |
|--------|--------|------|--------|
"""


def parse_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    try:
        return yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None


def collect_lessons() -> list[dict]:
    """Scan lesson directories and collect metadata."""
    lessons = []
    for scan_dir in SCAN_DIRS:
        d = LESSONS_DIR / scan_dir
        if not d.is_dir():
            continue
        for md in sorted(d.rglob("*.md")):
            if md.name in EXCLUDE_FILES:
                continue
            rel = md.relative_to(LESSONS_DIR)
            fm = parse_frontmatter(md)
            if not fm:
                continue
            title = fm.get("title", md.stem)
            domain = fm.get("domain", "")
            tags = fm.get("tags", [])
            source = fm.get("source", "")
            # Normalize tags: ensure all are strings
            if isinstance(tags, list):
                tags = [str(t) for t in tags]
            else:
                tags = []
            lessons.append({
                "path": str(rel),
                "title": title,
                "domain": domain,
                "tags": tags,
                "source": source,
            })
    # Sort by path for deterministic output
    lessons.sort(key=lambda x: x["path"])
    return lessons


def format_line(lesson: dict) -> str:
    """Format a single lesson line matching existing index format."""
    tags_str = ", ".join(f'"{t}"' for t in lesson["tags"])
    source = lesson["source"]
    # Truncate long sources for readability
    if len(source) > 80:
        source = source[:77] + "..."
    return f'- [{lesson["title"]}]({lesson["path"]}) | {lesson["domain"]} | {tags_str} | {source}'


def build_index(lessons: list[dict]) -> str:
    """Build the full index.md content."""
    lines = [HEADER.rstrip()]
    for lesson in lessons:
        lines.append(format_line(lesson))
    return "\n".join(lines) + "\n"


def check_mode(lessons: list[dict]) -> int:
    """Compare generated index with existing. Exit 1 on drift."""
    if not INDEX_FILE.exists():
        print(f"ERROR: {INDEX_FILE} does not exist. Run without --check first.", file=sys.stderr)
        return 1

    expected = build_index(lessons)
    actual = INDEX_FILE.read_text(encoding="utf-8")

    if expected == actual:
        return 0

    # Print diff (max 20 lines)
    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    diff = list(difflib.unified_diff(actual_lines, expected_lines,
                                      fromfile="lessons/index.md (current)",
                                      tofile="lessons/index.md (expected)"))
    print(f"DRIFT DETECTED: lessons/index.md differs from generated ({len(diff)} diff lines)")
    for line in diff[:20]:
        print(line, end="")
    if len(diff) > 20:
        print(f"... ({len(diff) - 20} more lines)")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Rebuild lessons/index.md")
    parser.add_argument("--check", action="store_true",
                        help="Check mode: exit 1 if index differs from generated")
    args = parser.parse_args()

    lessons = collect_lessons()
    print(f"Found {len(lessons)} lessons across {len(SCAN_DIRS)} directories")

    if args.check:
        return check_mode(lessons)

    # Rebuild mode
    content = build_index(lessons)
    INDEX_FILE.write_text(content, encoding="utf-8")
    print(f"Wrote {INDEX_FILE} ({len(lessons)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
