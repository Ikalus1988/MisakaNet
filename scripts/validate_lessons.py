#!/usr/bin/env python3
"""Validate all MisakaNet lessons against the lesson schema.
Usage:
    python3 scripts/validate_lessons.py          # validate all lessons
    python3 scripts/validate_lessons.py <file>    # validate a single file
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "lesson.json"
LESSONS_DIR = REPO_ROOT / "lessons"

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)


def load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def extract_frontmatter(path: Path) -> tuple[dict | None, str | None]:
    """Extract JSON frontmatter from a lesson markdown file."""
    content = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None, "No frontmatter block found (must start with ---)"
    raw = m.group(1).strip()
    # Try JSON first, fall back to YAML-like
    try:
        fm = json.loads(raw)
        return fm, None
    except json.JSONDecodeError:
        pass
    # Simple YAML-like parser for common patterns
    try:
        fm = {}
        current_key = None
        current_list = None

        for line in raw.split("\n"):
            # Check if this is a list item
            if line.strip().startswith("- "):
                if current_key and current_list is not None:
                    item = line.strip()[2:].strip().strip('"').strip("'")
                    current_list.append(item)
                continue

            line = line.strip()
            if not line:
                continue

            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()

                # Save previous list if exists
                if current_key and current_list is not None:
                    fm[current_key] = current_list
                    current_list = None

                if val == "":
                    # Start a new list
                    current_key = key
                    current_list = []
                elif val.startswith("[") and val.endswith("]"):
                    val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
                    fm[key] = val
                    current_key = None
                elif val.lower() == "true":
                    fm[key] = True
                    current_key = None
                elif val.lower() == "false":
                    fm[key] = False
                    current_key = None
                elif val.startswith('"') and val.endswith('"'):
                    fm[key] = val[1:-1]
                    current_key = None
                elif val.startswith("'") and val.endswith("'"):
                    fm[key] = val[1:-1]
                    current_key = None
                else:
                    fm[key] = val
                    current_key = None

        # Save last list if exists
        if current_key and current_list is not None:
            fm[current_key] = current_list

        if fm:
            return fm, None
    except Exception:
        pass
    return None, "Frontmatter must be valid JSON"


def validate_body(path: Path) -> list[str]:
    """Check lesson body has required sections."""
    content = path.read_text(encoding="utf-8")
    # Strip frontmatter
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)
    errors = []

    # Must have at least 3 sections
    sections = re.findall(r"^##\s+(.+)", body, re.MULTILINE)
    if len(sections) < 3:
        errors.append(f"Body has only {len(sections)} sections (minimum 3 required: Background/Solution/Verify)")

    # Check minimum content length
    text_only = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    if len(text_only) < 100:
        errors.append(f"Body text too short ({len(text_only)} chars, minimum 100)")

    # No placeholders
    placeholders = ["TODO", "FIXME", "coming soon", "to be written"]
    for ph in placeholders:
        if ph.lower() in body.lower():
            errors.append(f"Contains placeholder '{ph}'")

    return errors


def validate_lesson(path: Path, schema: dict) -> tuple[int, list[str]]:
    """Validate a single lesson. Returns (exit_code, [errors])."""
    errors = []

    # 1. Frontmatter extraction
    fm, fm_err = extract_frontmatter(path)
    if fm_err:
        errors.append(fm_err)
        return 1, errors

    # 2. JSON Schema validation
    try:
        jsonschema.validate(fm, schema)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema violation: {e.message}")
        if e.path:
            errors.append(f"  Path: {' -> '.join(str(p) for p in e.path)}")
        return 1, errors

    # 3. Body structure validation
    body_errs = validate_body(path)
    errors.extend(body_errs)

    return 0 if not errors else 1, errors


def main():
    schema = load_schema()
    if len(sys.argv) > 1:
        # Resolve relative paths to absolute so relative_to(REPO_ROOT) works
        paths = [Path(sys.argv[1]).resolve()]
    else:
        paths = sorted(LESSONS_DIR.glob("**/*.md"))

    exit_code = 0
    total = 0
    passed = 0
    failed = 0

    for path in paths:
        if path.name in ("index.md", "README.md", "TEMPLATE.md"):
            continue
        if "_archive" in str(path):
            continue

        total += 1
        is_core = "contrib" not in path.parts
        code, errs = validate_lesson(path, schema)
        if code == 0:
            passed += 1
        else:
            failed += 1
            rel = path.relative_to(REPO_ROOT)
            if is_core:
                print(f"❌ {rel}")
                exit_code = 1
            else:
                print(f"⚠️  {rel} (contrib — legacy, not blocking)")
            for e in errs:
                print(f"   - {e}")

    print(f"\n{'='*40}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
