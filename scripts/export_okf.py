#!/usr/bin/env python3
"""Export MisakaNet lessons to OKF (Open Knowledge Format) JSONL.

OKF required fields: type, title, description, tags, timestamp
Output: data/okf/lessons.jsonl (one lesson per line)

Usage:
    python3 scripts/export_okf.py [--output data/okf/] [--validate]
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"
REQUIRED_OKF_FIELDS = {"type", "title", "description", "tags", "timestamp"}


def parse_frontmatter(content: str) -> dict:
    """Extract JSON or YAML frontmatter from markdown."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    fm_text = content[3:end].strip()
    # Try JSON first
    try:
        return json.loads(fm_text)
    except json.JSONDecodeError:
        pass
    # Fallback: simple YAML key: value
    result = {}
    for line in fm_text.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            result[key.strip()] = val.strip().strip("\"\'")
    return result


def extract_title(content: str, fallback: str) -> str:
    """Get title from first heading or frontmatter."""
    for line in content.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def extract_description(content: str) -> str:
    """Get first meaningful paragraph as description."""
    in_frontmatter = content.startswith("---")
    lines = content.split("\n")
    if in_frontmatter:
        end = content.find("---", 3)
        if end != -1:
            lines = content[end + 3:].split("\n")

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            return stripped[:300]
    return ""


def lesson_to_okf(path: Path) -> dict | None:
    """Convert a lesson markdown file to OKF format."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    fm = parse_frontmatter(content)
    rel_path = str(path.relative_to(REPO_ROOT))
    stem = path.stem

    okf = {
        "type": "lesson",
        "id": stem,
        "title": fm.get("title", extract_title(content, stem.replace("-", " ").title())),
        "description": fm.get("description", "") or extract_description(content),
        "tags": fm.get("tags", []),
        "timestamp": fm.get("created", fm.get("updated", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))),
        "domain": fm.get("domain", ""),
        "source_path": rel_path,
        "confidence": fm.get("confidence", ""),
        "status": fm.get("status", "published"),
    }

    # Fallback description from title if empty
    if not okf["description"]:
        okf["description"] = f"Lesson: {okf['title']}"

    # Ensure tags is a list; generate fallback from domain/title if empty
    if isinstance(okf["tags"], str):
        okf["tags"] = [t.strip() for t in okf["tags"].split(",") if t.strip()]
    if not okf["tags"]:
        # Fallback: use domain + first 2 title words as tags
        fallback_tags = []
        if okf["domain"]:
            fallback_tags.append(okf["domain"])
        title_words = okf["title"].lower().split()[:2]
        fallback_tags.extend(w for w in title_words if w not in fallback_tags)
        okf["tags"] = fallback_tags or ["general"]

    return okf


def validate_okf(record: dict) -> list[str]:
    """Validate OKF required fields. Returns list of errors."""
    errors = []
    for field in REQUIRED_OKF_FIELDS:
        if field not in record or not record[field]:
            errors.append(f"Missing or empty required field: {field}")
    if not isinstance(record.get("tags"), list):
        errors.append("tags must be a list")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Export MisakaNet lessons to OKF format")
    parser.add_argument("--output", "-o", default="data/okf/", help="Output directory")
    parser.add_argument("--validate", action="store_true", help="Validate OKF fields and report errors")
    args = parser.parse_args()

    output_dir = REPO_ROOT / args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "lessons.jsonl"

    if not LESSONS_DIR.exists():
        print(f"Error: lessons directory not found: {LESSONS_DIR}", file=sys.stderr)
        sys.exit(1)

    lessons = sorted(LESSONS_DIR.rglob("*.md"))
    # Skip archived lessons
    lessons = [l for l in lessons if "_archive" not in str(l)]

    records = []
    validation_errors = []

    for path in lessons:
        okf = lesson_to_okf(path)
        if okf is None:
            continue
        records.append(okf)

        if args.validate:
            errors = validate_okf(okf)
            if errors:
                validation_errors.append((str(path.relative_to(REPO_ROOT)), errors))

    # Write JSONL
    with open(output_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Exported {len(records)} lessons to {output_file}")

    if args.validate:
        if validation_errors:
            print(f"\nValidation errors ({len(validation_errors)} files):", file=sys.stderr)
            for path, errors in validation_errors[:10]:
                print(f"  {path}: {'; '.join(errors)}", file=sys.stderr)
            sys.exit(1)
        else:
            print("Validation passed: all records have required OKF fields")


if __name__ == "__main__":
    main()
