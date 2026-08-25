#!/usr/bin/env python3
"""
Lesson deduplication script.

Detects duplicate lessons by title similarity (fuzzy match) and content hash.
Outputs potential duplicates with suggested merge targets.
"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple
import yaml


@dataclass
class Lesson:
    path: str
    title: str
    content_hash: str
    content: str
    frontmatter: dict


def load_lessons(lessons_dir: Path) -> List[Lesson]:
    """Load all lesson files from the lessons directory."""
    lessons = []
    for lesson_file in lessons_dir.rglob("*.md"):
        try:
            content = lesson_file.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(content)
            title = frontmatter.get("title", lesson_file.stem)
            # Hash the body content (normalized whitespace)
            normalized_body = " ".join(body.split())
            content_hash = hashlib.sha256(normalized_body.encode()).hexdigest()[:16]
            lessons.append(Lesson(
                path=str(lesson_file.relative_to(lessons_dir)),
                title=title,
                content_hash=content_hash,
                content=body,
                frontmatter=frontmatter
            ))
        except Exception as e:
            print(f"Warning: Failed to parse {lesson_file}: {e}", file=sys.stderr)
    return lessons


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return frontmatter, body
            except yaml.YAMLError:
                pass
    return {}, content


def title_similarity(title1: str, title2: str) -> float:
    """Compute similarity ratio between two titles (0.0 to 1.0)."""
    return SequenceMatcher(None, title1.lower(), title2.lower()).ratio()


def find_duplicates(
    lessons: List[Lesson],
    title_threshold: float = 0.85,
    content_threshold: float = 0.95
) -> List[dict]:
    """Find potential duplicate lessons."""
    duplicates = []
    
    # Group by content hash first (exact/near-exact content matches)
    hash_groups = {}
    for lesson in lessons:
        hash_groups.setdefault(lesson.content_hash, []).append(lesson)
    
    for hash_val, group in hash_groups.items():
        if len(group) > 1:
            # Sort by path length (shorter = likely original) then alphabetically
            group.sort(key=lambda l: (len(l.path), l.path))
            primary = group[0]
            for dup in group[1:]:
                duplicates.append({
                    "type": "content_hash",
                    "primary": primary.path,
                    "duplicate": dup.path,
                    "primary_title": primary.title,
                    "duplicate_title": dup.title,
                    "similarity": 1.0,
                    "reason": f"Identical content hash ({hash_val})"
                })
    
    # Fuzzy title matching for remaining lessons
    # Skip lessons already flagged as content duplicates
    flagged_paths = {d["duplicate"] for d in duplicates}
    flagged_paths.update({d["primary"] for d in duplicates})
    unflagged = [l for l in lessons if l.path not in flagged_paths]
    
    for i, lesson1 in enumerate(unflagged):
        for lesson2 in unflagged[i+1:]:
            sim = title_similarity(lesson1.title, lesson2.title)
            if sim >= title_threshold:
                # Determine primary (shorter path, then alphabetical)
                if (len(lesson1.path), lesson1.path) <= (len(lesson2.path), lesson2.path):
                    primary, duplicate = lesson1, lesson2
                else:
                    primary, duplicate = lesson2, lesson1
                
                duplicates.append({
                    "type": "title_fuzzy",
                    "primary": primary.path,
                    "duplicate": duplicate.path,
                    "primary_title": primary.title,
                    "duplicate_title": duplicate.title,
                    "similarity": round(sim, 3),
                    "reason": f"Title similarity {sim:.1%}"
                })
    
    return duplicates


def main():
    parser = argparse.ArgumentParser(description="Detect duplicate lessons")
    parser.add_argument(
        "--lessons-dir",
        type=Path,
        default=Path("lessons"),
        help="Directory containing lesson markdown files"
    )
    parser.add_argument(
        "--title-threshold",
        type=float,
        default=0.85,
        help="Title similarity threshold (0.0-1.0)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file for duplicates"
    )
    parser.add_argument(
        "--fail-on-duplicates",
        action="store_true",
        help="Exit with non-zero code if duplicates found"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only output JSON, no human-readable summary"
    )
    
    args = parser.parse_args()
    
    if not args.lessons_dir.exists():
        print(f"Error: Lessons directory not found: {args.lessons_dir}", file=sys.stderr)
        sys.exit(1)
    
    lessons = load_lessons(args.lessons_dir)
    if not lessons:
        print("No lessons found.")
        sys.exit(0)
    
    duplicates = find_duplicates(lessons, title_threshold=args.title_threshold)
    
    if args.output:
        args.output.write_text(json.dumps(duplicates, indent=2))
    
    if not args.quiet:
        if duplicates:
            print(f"\nFound {len(duplicates)} potential duplicate(s):\n")
            for dup in duplicates:
                print(f"  [{dup['type']}] {dup['duplicate']}")
                print(f"    -> Suggested merge target: {dup['primary']}")
                print(f"    -> Reason: {dup['reason']}")
                print(f"    -> Titles: '{dup['primary_title']}' vs '{dup['duplicate_title']}'")
                print()
        else:
            print("No duplicates found.")
    
    if args.fail_on_duplicates and duplicates:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
