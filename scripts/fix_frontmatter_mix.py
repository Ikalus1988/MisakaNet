#!/usr/bin/env python3
"""Fix frontmatter JSON+YAML mix issues in lessons.

This script moves provenance blocks from frontmatter to body,
ensuring frontmatter is pure JSON.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTRIB = REPO / "lessons" / "contrib"


def fix_frontmatter_mix(filepath: Path) -> bool:
    """Fix frontmatter JSON+YAML mix issue in a single file."""
    content = filepath.read_text(encoding='utf-8')

    # Parse frontmatter
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not m:
        return False

    frontmatter_raw = m.group(1).strip()
    body = m.group(2)

    # Check if it's JSON
    if not frontmatter_raw.startswith('{'):
        return False

    # Try to parse JSON
    try:
        fm = json.loads(frontmatter_raw)
        return False  # Already valid JSON
    except json.JSONDecodeError as e:
        if 'Extra data' not in str(e):
            return False

    # Extract valid JSON part and YAML part
    # Find the last closing brace before "provenance:"
    lines = frontmatter_raw.split('\n')
    json_lines = []
    yaml_lines = []
    in_json = True
    brace_count = 0

    for line in lines:
        if in_json:
            json_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0 and line.strip() == '}':
                in_json = False
        else:
            yaml_lines.append(line)

    # Parse JSON part
    json_str = '\n'.join(json_lines)
    try:
        fm = json.loads(json_str)
    except json.JSONDecodeError:
        return False

    # Convert YAML part to comment in body
    yaml_block = '\n'.join(yaml_lines).strip()
    if yaml_block:
        # Add YAML block as comment in body
        body = f"<!-- provenance:\n{yaml_block}\n-->\n\n{body}"

    # Reconstruct file
    new_content = f"---\n{json.dumps(fm, ensure_ascii=False, indent=2)}\n---\n{body}"

    # Write back
    filepath.write_text(new_content, encoding='utf-8')
    return True


def main():
    fixed = 0
    for filepath in sorted(CONTRIB.glob("*.md")):
        if fix_frontmatter_mix(filepath):
            print(f"Fixed: {filepath.name}")
            fixed += 1

    print(f"\nTotal fixed: {fixed}")


if __name__ == "__main__":
    main()
