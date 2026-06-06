#!/usr/bin/env python3
"""
Lesson Metadata Linter — validates frontmatter against lessons/schema.yaml.

Usage:
    python -m lessons.lint_lessons [directory]  # default: lessons/
    python -m lessons.lint_lessons lessons/contrib

Checks:
    - lang field is one of supported_langs (if present)
    - tags are non-empty and UTF-8 valid
    - required fields present
    - status values valid
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"

SUPPORTED_LANGS = {"zh-CN", "en", "ja", "ko"}
REQUIRED_FIELDS = {"title"}
VALID_STATUSES = {"draft", "published", "active"}


def _parse_yaml_frontmatter(text: str) -> dict:
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split('\n'):
        line = line.strip()
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith('[') and val.endswith(']'):
            try:
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',') if v.strip()]
            except Exception:
                pass
        elif val.lower() in ('true', 'yes'):
            val = True
        elif val.lower() in ('false', 'no'):
            val = False
        else:
            try:
                val = float(val)
            except ValueError:
                pass
        meta[key] = val
    return meta


def _parse_json_frontmatter(text: str) -> dict | None:
    m = re.match(r'^---\s*\n?(\{.*?\})\n?---', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def lint_file(filepath: Path) -> list[str]:
    """Validate a single lesson file. Returns list of error strings."""
    errors = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"READ ERROR: {e}"]

    if not content.strip():
        return []  # empty files are OK (README, etc.)

    meta = _parse_json_frontmatter(content) or _parse_yaml_frontmatter(content)
    if not meta:
        errors.append("No frontmatter found")
        return errors

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in meta:
            errors.append(f"Missing required field: {field}")

    # Validate lang
    lang = meta.get("lang")
    if lang is not None:
        if lang not in SUPPORTED_LANGS:
            errors.append(f"Invalid lang: '{lang}' (supported: {', '.join(sorted(SUPPORTED_LANGS))})")

    # Validate tags
    tags = meta.get("tags", [])
    if isinstance(tags, list) and tags:
        for tag in tags:
            if not isinstance(tag, str):
                errors.append(f"Non-string tag: {tag}")
            elif len(tag.strip()) == 0:
                errors.append("Empty tag found")

    # Validate status
    status = meta.get("status")
    if status is not None and isinstance(status, str):
        if status not in VALID_STATUSES:
            errors.append(f"Invalid status: '{status}' (valid: {', '.join(sorted(VALID_STATUSES))})")

    return errors


def lint_directory(dirpath: Path, recursive: bool = True) -> dict[str, list[str]]:
    """Lint all .md files in a directory. Returns {filepath: [errors]}."""
    results = {}
    pattern = "**/*.md" if recursive else "*.md"
    for f in sorted(dirpath.glob(pattern)):
        if f.name.startswith('.') or f.name == 'README.md':
            continue
        errors = lint_file(f)
        if errors:
            results[str(f.relative_to(REPO))] = errors
    return results


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else LESSONS
    if not target.exists():
        print(f"❌ Directory not found: {target}")
        sys.exit(1)

    results = lint_directory(target)
    if not results:
        print("✅ All lessons pass validation!")
        sys.exit(0)

    print(f"⚠️  {len(results)} files with issues:\n")
    for filepath, errors in results.items():
        print(f"📄 {filepath}")
        for err in errors:
            print(f"   ❌ {err}")
        print()
    sys.exit(1)


if __name__ == "__main__":
    main()
