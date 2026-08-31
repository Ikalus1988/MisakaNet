#!/usr/bin/env python3
"""Deduplicate lesson files by fuzzy title + content hash.

Run: python scripts/dedup_lessons.py [--fix] [--dry-run]
"""

import hashlib
import os
import re
import sys
from pathlib import Path

LESSONS_DIR = Path(__file__).resolve().parent.parent / "lessons"


def extract_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text."""
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def content_hash(text: str) -> str:
    """SHA-256 of normalized body (strip frontmatter + whitespace)."""
    body = re.sub(r"^---\n.*?\n---\n?", "", text, flags=re.DOTALL)
    body = re.sub(r"\s+", "", body)
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def load_lessons() -> list[dict]:
    """Load all lesson files."""
    lessons = []
    for f in sorted(LESSONS_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        meta = extract_frontmatter(text)
        lessons.append({
            "file": f.name,
            "path": f,
            "title": meta.get("title", ""),
            "norm_title": normalize_title(meta.get("title", "")),
            "hash": content_hash(text),
            "quality": meta.get("quality", ""),
            "text": text,
        })
    return lessons


def find_duplicates(lessons: list[dict]) -> list[dict]:
    """Find duplicates by exact title match or content hash."""
    groups: dict[str, list[dict]] = {}

    for lesson in lessons:
        key = lesson["norm_title"] or lesson["hash"]
        groups.setdefault(key, []).append(lesson)

    # Also group by content hash for different titles with same body
    hash_groups: dict[str, list[dict]] = {}
    for lesson in lessons:
        hash_groups.setdefault(lesson["hash"], []).append(lesson)

    # Merge groups
    for h, members in hash_groups.items():
        if len(members) > 1:
            titles = [m["norm_title"] for m in members]
            for t in titles:
                if t in groups:
                    existing_files = {m["file"] for m in groups[t]}
                    for m in members:
                        if m["file"] not in existing_files:
                            groups[t].append(m)
                    break
            else:
                groups[h] = members

    # Filter to groups with >1 member
    return [
        {"key": k, "members": v}
        for k, v in groups.items()
        if len(v) > 1
    ]


def pick_winner(group: list[dict]) -> dict:
    """Pick the best lesson from a duplicate group."""
    def score(m: dict) -> tuple:
        q = m["quality"]
        q_score = {"A": 4, "B": 3, "C": 2, "legacy": 1}.get(q, 0)
        return (q_score, len(m["text"]), m["file"])

    return max(group, key=score)


def main():
    fix = "--fix" in sys.argv
    dry_run = "--dry-run" in sys.argv

    if not LESSONS_DIR.is_dir():
        print(f"Lessons directory not found: {LESSONS_DIR}")
        sys.exit(1)

    lessons = load_lessons()
    print(f"Loaded {len(lessons)} lessons")

    duplicates = find_duplicates(lessons)

    if not duplicates:
        print("No duplicates found.")
        return

    print(f"\nFound {len(duplicates)} duplicate groups:\n")

    removed = []
    for group in duplicates:
        winner = pick_winner(group["members"])
        losers = [m for m in group["members"] if m["file"] != winner["file"]]

        print(f"  [{group['key']}]")
        print(f"    KEEP: {winner['file']} (quality={winner['quality']}, {len(winner['text'])} chars)")
        for loser in losers:
            print(f"    DROP: {loser['file']} (quality={loser['quality']}, {len(loser['text'])} chars)")
            if fix and not dry_run:
                loser["path"].unlink()
                removed.append(loser["file"])

    if fix and not dry_run:
        print(f"\nRemoved {len(removed)} duplicates.")
    elif dry_run:
        print("\n[dry-run] No files modified.")
    else:
        print("\nRun with --fix to remove duplicates (keeps highest quality).")


if __name__ == "__main__":
    main()
