#!/usr/bin/env python3
"""Audit all contrib lessons: frontmatter format + content quality.
Fixes YAML→JSON frontmatter where possible.
Truly empty files → delete.
"""
import json, re, sys, os
from pathlib import Path

REPO = Path("/mnt/c/Users/hp/MisakaNet")
CONTRIB = REPO / "lessons" / "contrib"
DRY_RUN = "--dry-run" in sys.argv

def yaml_to_json(text: str) -> str | None:
    """Convert simple YAML frontmatter to JSON."""
    lines = text.strip().split("\n")
    result = {}
    for line in lines:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        # Handle arrays: "tags: [a, b, c]"
        if val.startswith("[") and val.endswith("]"):
            val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
        elif val.lower() == "true":
            val = True
        elif val.lower() == "false":
            val = False
        elif val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        result[key] = val
    if not result:
        return None
    return json.dumps(result, ensure_ascii=False)

total = 0
converted = 0
deleted = 0
kept = 0

for path in sorted(CONTRIB.rglob("*.md")):
    if path.name == "README.md":
        continue
    total += 1

    content = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)

    # Check if the lesson has substance
    text_only = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    char_count = len(text_only)
    has_heading = bool(re.search(r"^##\s", content, re.MULTILINE))

    # DELETE if: no headings, < 50 chars of real content
    if not has_heading and char_count < 100:
        if DRY_RUN:
            print(f"  WOULD DELETE: {path.name} ({char_count} chars, no sections)")
        else:
            path.unlink()
            print(f"  DELETED: {path.name} ({char_count} chars)")
        deleted += 1
        continue

    # CONVERT YAML → JSON frontmatter
    if m and not m.group(1).strip().startswith("{"):
        yaml_text = m.group(1)
        json_text = yaml_to_json(yaml_text)
        if json_text:
            new_content = content.replace(yaml_text, json_text, 1)
            if DRY_RUN:
                print(f"  WOULD CONVERT: {path.name} (YAML→JSON)")
            else:
                path.write_text(new_content, encoding="utf-8")
                print(f"  CONVERTED: {path.name} (YAML→JSON)")
            converted += 1
        else:
            if DRY_RUN:
                print(f"  WOULD SKIP (unparseable YAML): {path.name}")
            kept += 1
    elif m and m.group(1).strip().startswith("{"):
        kept += 1  # already JSON, fine
    else:
        if DRY_RUN:
            print(f"  WOULD KEEP (no frontmatter, has content): {path.name} ({char_count} chars)")
        kept += 1

print(f"\n{'='*40}")
print(f"Total:   {total}")
print(f"Converted YAML→JSON: {converted}")
print(f"Deleted (empty):     {deleted}")
print(f"Kept (already OK):   {kept}")
