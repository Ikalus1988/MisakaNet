#!/usr/bin/env python3
"""Add provenance metadata to lessons (Issue #1219).

Scans lesson markdown files and adds provenance section to those missing it.

Usage:
    python3 scripts/add_provenance.py --dry-run
    python3 scripts/add_provenance.py --apply
    python3 scripts/add_provenance.py --domain ops --dry-run

Provenance format:
    provenance:
      source: "internal" | "external" | "community"
      contributor: "Node Name"
      merged_at: "YYYY-MM-DD"
      evidence: "post-publication" | "pr-merged" | "issue-resolved"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"


@dataclass
class LessonInfo:
    """Lesson metadata."""
    path: Path
    title: str
    domain: str
    has_provenance: bool
    frontmatter: dict


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML-like frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content

    # Find end of frontmatter
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content

    frontmatter_str = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

    # Simple key-value parser (not full YAML)
    frontmatter = {}
    current_key = None
    current_value = []

    for line in frontmatter_str.split("\n"):
        if line.startswith("  ") and current_key:
            # Continuation of previous value
            current_value.append(line.strip())
        elif ":" in line and not line.startswith(" "):
            # New key-value pair
            if current_key:
                frontmatter[current_key] = "\n".join(current_value).strip()
            key, _, value = line.partition(":")
            current_key = key.strip()
            current_value = [value.strip()] if value.strip() else []
        elif line.strip().startswith("- "):
            # List item
            if current_key:
                current_value.append(line.strip())

    if current_key:
        frontmatter[current_key] = "\n".join(current_value).strip()

    return frontmatter, body


def has_provenance_section(content: str) -> bool:
    """Check if content already has provenance section."""
    return "provenance:" in content or "provenance:" in content.lower()


def extract_domain_from_path(path: Path) -> str:
    """Extract domain from file path."""
    # lessons/contrib/file.md -> contrib
    # lessons/en/file.md -> en (language, skip)
    parts = path.relative_to(LESSONS_DIR).parts
    if len(parts) > 1:
        domain = parts[0]
        if domain in ("en", "hi", "id", "ru", "tr"):
            return "unknown"  # Language directories
        return domain
    return "unknown"


def guess_contributor(frontmatter: dict, path: Path) -> str:
    """Guess contributor from metadata."""
    # Check for explicit contributor
    if "contributor" in frontmatter:
        return frontmatter["contributor"]

    # Check title for node names
    title = frontmatter.get("title", "")
    node_patterns = [
        r"Misaka\d+",
        r"Node\d+",
        r"Agent\d+",
    ]
    for pattern in node_patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(0)

    # Default based on domain
    domain = extract_domain_from_path(path)
    if domain == "contrib":
        return "Community"
    elif domain == "core":
        return "MisakaNet Core"
    else:
        return "Unknown"


def guess_source(domain: str) -> str:
    """Guess source from domain."""
    if domain == "contrib":
        return "community"
    elif domain in ("core", "devops"):
        return "internal"
    else:
        return "external"


def add_provenance(content: str, contributor: str, source: str) -> str:
    """Add provenance section to content."""
    # Find insertion point (after frontmatter)
    if not content.startswith("---"):
        # No frontmatter, add at beginning
        provenance = f"""---
provenance:
  source: "{source}"
  contributor: "{contributor}"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
"""
        return provenance + content

    # Find end of frontmatter
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return content

    # Insert provenance before closing ---
    before = content[:end_idx]
    after = content[end_idx:]

    provenance = f"""provenance:
  source: "{source}"
  contributor: "{contributor}"
  merged_at: "2026-08-23"
  evidence: "post-publication"
"""

    return before + provenance + after


def scan_lessons(domain_filter: Optional[str] = None) -> list[LessonInfo]:
    """Scan for lessons without provenance."""
    lessons = []

    for md_file in LESSONS_DIR.rglob("*.md"):
        # Skip templates, archive, etc.
        if md_file.parent.name in ("_archive", "templates", "draft", "drafts"):
            continue
        if md_file.name in ("index.md", "TEMPLATE.md", "LESSON_QUALITY_SCORING.md"):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        frontmatter, body = parse_frontmatter(content)
        domain = extract_domain_from_path(md_file)

        # Apply domain filter
        if domain_filter and domain != domain_filter:
            continue

        lessons.append(LessonInfo(
            path=md_file,
            title=frontmatter.get("title", md_file.stem),
            domain=domain,
            has_provenance=has_provenance_section(content),
            frontmatter=frontmatter,
        ))

    return lessons


def main():
    parser = argparse.ArgumentParser(description="Add provenance to lessons")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed")
    parser.add_argument("--apply", action="store_true", help="Apply changes")
    parser.add_argument("--domain", "-d", help="Filter by domain")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("Specify --dry-run or --apply")

    # Scan lessons
    lessons = scan_lessons(args.domain)

    # Filter those without provenance
    missing = [l for l in lessons if not l.has_provenance]
    has_prov = [l for l in lessons if l.has_provenance]

    # Output summary
    if args.json:
        result = {
            "total_scanned": len(lessons),
            "has_provenance": len(has_prov),
            "missing_provenance": len(missing),
            "lessons": [
                {
                    "path": str(l.path.relative_to(REPO_ROOT)),
                    "title": l.title,
                    "domain": l.domain,
                }
                for l in missing
            ],
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"Scanned {len(lessons)} lessons")
        print(f"  Has provenance: {len(has_prov)}")
        print(f"  Missing provenance: {len(missing)}")

        if missing:
            print(f"\nLessons to update:")
            for l in missing[:20]:  # Show first 20
                print(f"  - {l.path.relative_to(REPO_ROOT)} ({l.domain})")
            if len(missing) > 20:
                print(f"  ... and {len(missing) - 20} more")

    # Apply changes
    if args.apply and missing:
        print(f"\nAdding provenance to {len(missing)} lessons...")
        updated = 0

        for lesson in missing:
            try:
                content = lesson.path.read_text(encoding="utf-8")
                contributor = guess_contributor(lesson.frontmatter, lesson.path)
                source = guess_source(lesson.domain)

                new_content = add_provenance(content, contributor, source)
                lesson.path.write_text(new_content, encoding="utf-8")
                updated += 1
            except Exception as e:
                print(f"  Error updating {lesson.path}: {e}", file=sys.stderr)

        print(f"Updated {updated} lessons")


if __name__ == "__main__":
    main()
