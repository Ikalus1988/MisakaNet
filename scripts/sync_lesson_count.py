#!/usr/bin/env python3
"""
Sync lesson count across all project files using data/lessons.json as the single source of truth.

Usage:
    python3 scripts/sync_lesson_count.py              # sync all files
    python3 scripts/sync_lesson_count.py --check      # check only, exit 1 if mismatch
    python3 scripts/sync_lesson_count.py --quiet      # sync silently
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_JSON = REPO / "data" / "lessons.json"
STATUS_MD = REPO / "STATUS.md"
README_MD = REPO / "README.md"
FRONTEND_HTML = REPO / "docs" / "index.html"


def get_lesson_count() -> int:
    """Read lesson count from the single source of truth: data/lessons.json."""
    with open(LESSONS_JSON, "r", encoding="utf-8") as f:
        lessons = json.load(f)
    return len(lessons)


def sync_status_md(count: int, dry_run: bool = False) -> list[str]:
    """Sync lesson count in STATUS.md."""
    changes = []
    text = STATUS_MD.read_text(encoding="utf-8")
    # Pattern: | 📚 Lessons | XXX 篇 |
    pattern = r"(\| 📚 Lessons \|\s*)\d+(\s*篇\s*\|)"
    replacement = rf"\g<1>{count}\2"
    if re.search(pattern, text):
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            changes.append(f"STATUS.md: lesson count updated to {count}")
            if not dry_run:
                STATUS_MD.write_text(new_text, encoding="utf-8")
    return changes


def sync_readme_md(count: int, dry_run: bool = False) -> list[str]:
    """Sync lesson count in README.md (badges, descriptions, tables)."""
    changes = []
    text = README_MD.read_text(encoding="utf-8")
    old_text = text

    # Replace standalone digit counts followed by + or space or end-of-word
    # Match patterns like "205+", "205 ", "205 lessons"
    replacements = [
        (r"\b\d{2,3}\+", f"{count}+"),
        (r"(\|\s*\*\*Data\*\*\s*\|\s*)\d{2,3}\s+lessons", rf"\g<1>{count} lessons"),
        (r"(Give Cursor / Claude access to )\d{2,3}\+ verified", rf"\g<1>{count}+ verified"),
    ]

    for pattern, replacement in replacements:
        new_text = re.sub(pattern, replacement, text)
        if new_text != text:
            changes.append(f"README.md: matched pattern '{pattern}'")
            text = new_text

    if text != old_text:
        if not dry_run:
            README_MD.write_text(text, encoding="utf-8")
    return changes


def sync_frontend_html(count: int, dry_run: bool = False) -> list[str]:
    """Sync hardcoded lesson count fallbacks in docs/index.html.

    Note: The JS dynamically fetches from /data/lessons.json at runtime,
    so runtime values are always correct. This syncs the static HTML fallbacks
    for when JS is disabled or hasn't loaded yet.
    """
    changes = []
    text = FRONTEND_HTML.read_text(encoding="utf-8")
    old_text = text

    # Search panel fallback: "198 curated lessons"
    text = re.sub(
        r'(\b\d{2,3}\s+curated lessons)',
        f'{count} curated lessons',
        text,
    )

    # Hero section span: "<span id="lesson-count-hero">200+</span>"
    text = re.sub(
        r'(<span id="lesson-count-hero">)\d{2,3}\+(</span>)',
        rf'\g<1>{count}+\g<2>',
        text,
    )

    # Product section span: "<span id="lesson-count-product">200+</span>"
    text = re.sub(
        r'(<span id="lesson-count-product">)\d{2,3}\+(</span>)',
        rf'\g<1>{count}+\g<2>',
        text,
    )

    # Meta description: "205+ curated lessons"
    text = re.sub(
        r'(\b\d{2,3}\+\s+curated lessons)',
        f'{count}+ curated lessons',
        text,
    )

    if text != old_text:
        changes.append(f"docs/index.html: hardcoded fallbacks updated to {count}")
        if not dry_run:
            FRONTEND_HTML.write_text(text, encoding="utf-8")
    return changes


def check_count_in_files(count: int) -> tuple[list[str], bool]:
    """Check all files for stale lesson counts. Returns (issues, is_clean)."""
    issues = []

    # STATUS.md
    text = STATUS_MD.read_text(encoding="utf-8")
    if re.search(r'\|\s*📚\s*Lessons\s*\|\s*\d+\s*篇\s*\|', text):
        m = re.search(r'\|\s*📚\s*Lessons\s*\|\s*(\d+)\s*篇\s*\|', text)
        if m and int(m.group(1)) != count:
            issues.append(f"STATUS.md has lesson count {m.group(1)}, expected {count}")

    # README.md — look for lesson-count-specific patterns, not PR numbers
    text = README_MD.read_text(encoding="utf-8")
    # Match patterns like "205+", "200+", "205 lessons" — but ignore "#NNN" (PR refs)
    lesson_ref_patterns = [
        r"\b\d{2,3}\+\s*(?:verified)?\s*lessons?",
        r"\b\d{2,3}\+\s*curated",
        r"\|\s*\*\*Data\*\*\s*\|\s*\d{2,3}\s+lessons",
        r"\|\s*Shared Lessons\s*\|\s*\d{2,3}\+",
    ]
    for pattern in lesson_ref_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            digits = re.findall(r"\d+", m.group())
            for d in digits:
                if int(d) < count:
                    issues.append(f"README.md has stale lesson count reference: '{m.group()}'")

    # Frontend HTML
    text = FRONTEND_HTML.read_text(encoding="utf-8")
    m = re.search(r'(\d{2,3})\s+curated lessons', text)
    if m and int(m.group(1)) != count:
        issues.append(f"docs/index.html search panel has {m.group(1)}, expected {count}")

    return issues, len(issues) == 0


def main():
    parser = argparse.ArgumentParser(description="Sync lesson count across project files")
    parser.add_argument("--check", action="store_true", help="Check only, exit 1 if mismatch")
    parser.add_argument("--quiet", action="store_true", help="Silent mode (no output on success)")
    args = parser.parse_args()

    count = get_lesson_count()
    all_changes = []

    if args.check:
        issues, is_clean = check_count_in_files(count)
        if is_clean:
            if not args.quiet:
                print(f"✅ All files consistent: lesson count = {count}")
            sys.exit(0)
        else:
            print(f"❌ Mismatch detected (expected {count}):", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            sys.exit(1)

    all_changes += sync_status_md(count)
    all_changes += sync_readme_md(count)
    all_changes += sync_frontend_html(count)

    if all_changes:
        print(f"✅ Synced lesson count to {count}:")
        for change in all_changes:
            print(f"  - {change}")
    elif not args.quiet:
        print(f"✅ Already consistent: lesson count = {count}")


if __name__ == "__main__":
    main()
