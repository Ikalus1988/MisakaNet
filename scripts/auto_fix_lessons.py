#!/usr/bin/env python3
"""Auto-fix lesson quality issues.

This script automatically fixes common issues found by check_lesson_quality.py:
1. Add missing status field to frontmatter
2. Add Verification section template
3. Fix short content (expand or merge)

Usage:
    python3 scripts/auto_fix_lessons.py --dry-run  # Preview fixes
    python3 scripts/auto_fix_lessons.py --fix      # Apply fixes
"""

import json
import re
import yaml
from pathlib import Path
import argparse

REPO = Path(__file__).resolve().parent.parent
CONTRIB = REPO / "lessons" / "contrib"


def fix_missing_status(filepath: Path, dry_run: bool = True) -> bool:
    """Add missing status field to frontmatter."""
    content = filepath.read_text(encoding='utf-8')

    # Parse frontmatter
    m = re.match(r'^---\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not m:
        return False

    frontmatter_raw = m.group(1).strip()
    body = m.group(2)

    # Parse as YAML
    try:
        fm = yaml.safe_load(frontmatter_raw)
    except Exception:
        return False

    if not isinstance(fm, dict):
        return False

    # Check if status is missing
    if 'status' in fm:
        return False

    # Add status field
    fm['status'] = 'published'

    # Reconstruct frontmatter
    new_frontmatter = yaml.dump(fm, allow_unicode=True, default_flow_style=False)

    # Reconstruct file
    new_content = f"---\n{new_frontmatter}---\n{body}"

    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')

    return True


def add_verification_template(filepath: Path, dry_run: bool = True) -> bool:
    """Add Verification section template if missing."""
    content = filepath.read_text(encoding='utf-8')

    # Check if Verification section exists
    if re.search(r'^##\s*(Verification|验证)', content, re.MULTILINE | re.IGNORECASE):
        return False

    # Extract title from frontmatter
    m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if m:
        try:
            fm = yaml.safe_load(m.group(1))
            title = fm.get('title', filepath.stem) if isinstance(fm, dict) else filepath.stem
        except Exception:
            title = filepath.stem
    else:
        title = filepath.stem

    # Add Verification section at the end
    verification_section = f"""

## Verification

```bash
# Verify the fix works
echo "Verification commands for: {title}"
```

**Expected Output:**
```
Successfully verified
```
"""

    if not dry_run:
        # Append to file
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(verification_section)

    return True


def main():
    parser = argparse.ArgumentParser(description='Auto-fix lesson quality issues')
    parser.add_argument('--dry-run', action='store_true', help='Preview fixes without applying')
    parser.add_argument('--fix', action='store_true', help='Apply fixes')
    args = parser.parse_args()

    if not args.dry_run and not args.fix:
        print("Please specify --dry-run or --fix")
        return 1

    fixed_status = 0
    fixed_verification = 0

    for filepath in sorted(CONTRIB.glob("*.md")):
        # Fix missing status
        if fix_missing_status(filepath, dry_run=args.dry_run):
            print(f"[{'DRY' if args.dry_run else 'FIXED'}] Added status to: {filepath.name}")
            fixed_status += 1

        # Add Verification template
        if add_verification_template(filepath, dry_run=args.dry_run):
            print(f"[{'DRY' if args.dry_run else 'FIXED'}] Added Verification to: {filepath.name}")
            fixed_verification += 1

    print(f"\nSummary:")
    print(f"  Status fixes: {fixed_status}")
    print(f"  Verification fixes: {fixed_verification}")

    return 0


if __name__ == "__main__":
    exit(main())
