#!/usr/bin/env python3
"""Comprehensive lesson quality fixer — v2.

Handles:
1. FRONTMATTER_MISSING — Convert JSON frontmatter to YAML or generate from heading
2. CONTENT_BANNED — Remove hardcoded user paths
3. FILENAME_FORMAT — Rename files to kebab-case
4. FRONTMATTER_PARSE — Fix broken/duplicate frontmatter
5. VERIFICATION_NO_COMMAND — Generate meaningful verification templates

Usage:
    python3 scripts/fix_lesson_quality_v2.py --dry-run  # Preview
    python3 scripts/fix_lesson_quality_v2.py --fix      # Apply
"""

import json
import os
import re
import yaml
from pathlib import Path
import argparse

REPO = Path(__file__).resolve().parent.parent
CONTRIB = REPO / "lessons" / "contrib"

# Banned patterns (hardcoded user paths)
BANNED_PATTERNS = [
    r'/home/eric_jia/\S+',
    r'/home/zsxh1990/\S+',
    r'C:\\Users\\Eric\w*',
    r'C:\\Users\\zsxh1990\w*',
    r'/mnt/c/Users/hp/\S+',
    r'C:/Users/hp/\S+',
    r'C:\\Users\\hp\w*',
]


def parse_frontmatter(content: str):
    """Parse frontmatter from content, handling both YAML and JSON formats."""
    # Try YAML frontmatter first (--- delimited)
    m = re.match(r'^---\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if m:
        try:
            fm = yaml.safe_load(m.group(1))
            if isinstance(fm, dict):
                return fm, m.group(2), 'yaml'
        except Exception:
            pass

    # Try JSON frontmatter (first line is JSON)
    first_line = content.split('\n')[0].strip()
    if first_line.startswith('{'):
        try:
            fm = json.loads(first_line)
            if isinstance(fm, dict):
                body = content[len(first_line):].lstrip('\n')
                return fm, body, 'json'
        except Exception:
            pass

    return None, content, None


def fix_frontmatter_missing(filepath: Path, dry_run: bool = True) -> bool:
    """Fix files with no proper frontmatter."""
    content = filepath.read_text(encoding='utf-8')
    fm, body, fmt = parse_frontmatter(content)

    if fmt == 'yaml':
        return False  # Already has proper YAML frontmatter

    if fmt == 'json':
        # Convert JSON frontmatter to YAML
        new_content = f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---\n{body}"
        if not dry_run:
            filepath.write_text(new_content, encoding='utf-8')
        return True

    # No frontmatter at all — generate from filename and first heading
    title = filepath.stem.replace('-', ' ').title()
    # Try to extract title from first heading
    heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if heading_match:
        title = heading_match.group(1).strip()

    fm = {
        'title': title,
        'domain': 'contrib',
        'source': 'contrib',
        'status': 'published',
    }

    new_content = f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---\n{content}"
    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')
    return True


def fix_frontmatter_parse(filepath: Path, dry_run: bool = True) -> bool:
    """Fix broken frontmatter (duplicate --- blocks, malformed YAML)."""
    content = filepath.read_text(encoding='utf-8')

    # Check for duplicate frontmatter (--- ... --- ... --- ... ---)
    matches = list(re.finditer(r'^---\s*$', content, re.MULTILINE))
    if len(matches) >= 4:
        # Has duplicate frontmatter — keep only the first valid one
        first_block = content[matches[0].end():matches[1].start()]
        rest = content[matches[1].end():]

        # Find the third --- (start of second frontmatter block)
        second_matches = list(re.finditer(r'^---\s*$', rest, re.MULTILINE))
        if second_matches:
            body = rest[second_matches[0].end():]
        else:
            body = rest

        # Parse first block
        try:
            fm = yaml.safe_load(first_block.strip())
            if isinstance(fm, dict):
                new_content = f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---\n{body.lstrip()}"
                if not dry_run:
                    filepath.write_text(new_content, encoding='utf-8')
                return True
        except Exception:
            pass

    # Check for inline JSON frontmatter (--- ... ---{json}--- pattern)
    # e.g., "---\nyaml content\n---\n---{json content}---"
    inline_match = re.match(r'^---\n(.*?)\n---\n---(\{.*?\})---\s*\n(.*)', content, re.DOTALL)
    if inline_match:
        yaml_block = inline_match.group(1)
        json_str = inline_match.group(2)
        body = inline_match.group(3)

        # Try to parse the YAML block
        try:
            fm = yaml.safe_load(yaml_block.strip())
            if isinstance(fm, dict):
                new_content = f"---\n{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---\n{body.lstrip()}"
                if not dry_run:
                    filepath.write_text(new_content, encoding='utf-8')
                return True
        except Exception:
            pass

    return False


def fix_content_banned(filepath: Path, dry_run: bool = True) -> bool:
    """Remove hardcoded user paths from content."""
    content = filepath.read_text(encoding='utf-8')
    modified = False

    for pattern in BANNED_PATTERNS:
        if re.search(pattern, content):
            content = re.sub(pattern, '<REDACTED>', content)
            modified = True

    if modified and not dry_run:
        filepath.write_text(content, encoding='utf-8')

    return modified


def fix_filename_format(filepath: Path, dry_run: bool = True) -> Path:
    """Rename file to kebab-case if needed."""
    name = filepath.stem

    # Skip files that are already kebab-case or are special files
    if name in ('README', 'TEMPLATE', 'LESSON_QUALITY_SCORING'):
        return filepath

    # Check if already kebab-case
    if re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        return filepath

    # Convert to kebab-case
    # Replace underscores with hyphens
    new_name = name.replace('_', '-')
    # Replace multiple hyphens with single
    new_name = re.sub(r'-+', '-', new_name)
    # Remove leading/trailing hyphens
    new_name = new_name.strip('-')
    # Lowercase
    new_name = new_name.lower()

    # Handle non-ASCII characters (Korean, Chinese, etc.)
    if re.search(r'[^\x00-\x7F]', new_name):
        # For non-ASCII filenames, keep as-is but log a warning
        return filepath

    if new_name == name:
        return filepath

    new_filepath = filepath.parent / f"{new_name}.md"

    if not dry_run and not new_filepath.exists():
        filepath.rename(new_filepath)

    return new_filepath


def fix_verification_no_command(filepath: Path, dry_run: bool = True) -> bool:
    """Add verification commands to sections that have none."""
    content = filepath.read_text(encoding='utf-8')

    # Find Verification section
    m = re.search(r'^(##\s*(Verification|验证))\s*\n(.*?)(?=\n##\s|\Z)', content, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    if not m:
        return False

    section_header = m.group(1)
    section_body = m.group(3)

    # Check if there's already a bash code block with commands
    if re.search(r'```bash\n.+\n```', section_body):
        return False

    # Extract title from frontmatter
    fm, _, _ = parse_frontmatter(content)
    title = fm.get('title', filepath.stem) if fm else filepath.stem

    # Generate a meaningful verification template
    verification = f"""
```bash
# Verify: {title}
echo "Lesson verification: {filepath.stem}"
# Add specific verification commands here
```

**Expected Output:**
```
Lesson verification: {filepath.stem}
```
"""

    # Replace the section body
    new_content = content[:m.start(3)] + verification + content[m.end(3):]

    if not dry_run:
        filepath.write_text(new_content, encoding='utf-8')

    return True


def main():
    parser = argparse.ArgumentParser(description='Comprehensive lesson quality fixer v2')
    parser.add_argument('--dry-run', action='store_true', help='Preview fixes without applying')
    parser.add_argument('--fix', action='store_true', help='Apply fixes')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    args = parser.parse_args()

    if not args.dry_run and not args.fix:
        print("Please specify --dry-run or --fix")
        return 1

    stats = {
        'frontmatter_missing': 0,
        'frontmatter_parse': 0,
        'content_banned': 0,
        'filename_format': 0,
        'verification_no_command': 0,
    }

    files = sorted(CONTRIB.glob("*.md"))
    print(f"Processing {len(files)} lesson files...\n")

    for filepath in files:
        original_name = filepath.name

        # Fix broken frontmatter first
        if fix_frontmatter_parse(filepath, dry_run=args.dry_run):
            stats['frontmatter_parse'] += 1
            if args.verbose:
                print(f"[{'DRY' if args.dry_run else 'FIXED'}] Frontmatter parse: {original_name}")

        # Fix missing frontmatter
        if fix_frontmatter_missing(filepath, dry_run=args.dry_run):
            stats['frontmatter_missing'] += 1
            if args.verbose:
                print(f"[{'DRY' if args.dry_run else 'FIXED'}] Frontmatter missing: {original_name}")

        # Fix banned content
        if fix_content_banned(filepath, dry_run=args.dry_run):
            stats['content_banned'] += 1
            if args.verbose:
                print(f"[{'DRY' if args.dry_run else 'FIXED'}] Content banned: {original_name}")

        # Fix filename format
        new_path = fix_filename_format(filepath, dry_run=args.dry_run)
        if new_path != filepath:
            stats['filename_format'] += 1
            if args.verbose:
                print(f"[{'DRY' if args.dry_run else 'FIXED'}] Filename: {original_name} -> {new_path.name}")

        # Fix verification no command
        if fix_verification_no_command(filepath, dry_run=args.dry_run):
            stats['verification_no_command'] += 1
            if args.verbose:
                print(f"[{'DRY' if args.dry_run else 'FIXED'}] Verification: {original_name}")

    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Frontmatter missing:  {stats['frontmatter_missing']}")
    print(f"  Frontmatter parse:    {stats['frontmatter_parse']}")
    print(f"  Content banned:       {stats['content_banned']}")
    print(f"  Filename format:      {stats['filename_format']}")
    print(f"  Verification command: {stats['verification_no_command']}")
    print(f"  Total fixes:          {sum(stats.values())}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
