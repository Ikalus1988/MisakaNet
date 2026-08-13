#!/usr/bin/env python3
"""Fix missing H1 titles in lesson files."""

import re
import sys
from pathlib import Path


def extract_title_from_frontmatter(content: str) -> str | None:
    """Extract title from YAML or JSON frontmatter."""
    # Try --- delimited frontmatter
    match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if match:
        frontmatter = match.group(1).strip()

        # Try JSON frontmatter (could be inside --- markers)
        if frontmatter.startswith('{'):
            try:
                import json
                data = json.loads(frontmatter)
                return data.get('title')
            except json.JSONDecodeError:
                pass

        # Try YAML frontmatter
        title_match = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()

        # Try name field in YAML frontmatter
        name_match = re.search(r'^name:\s*["\']?(.*?)["\']?\s*$', frontmatter, re.MULTILINE)
        if name_match:
            return name_match.group(1).strip().replace('-', ' ').title()

    # Try raw JSON at start of file (no --- delimiters)
    if content.strip().startswith('{'):
        try:
            import json
            # Find the closing brace
            brace_count = 0
            end_idx = 0
            for i, char in enumerate(content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx > 0:
                data = json.loads(content[:end_idx])
                return data.get('title')
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def has_h1_in_first_lines(content: str, n: int = 10) -> bool:
    """Check if content has H1 title in first n lines after frontmatter."""
    # Skip --- delimited frontmatter
    match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
    if match:
        body = content[match.end():]
    elif content.strip().startswith('{'):
        # Skip raw JSON frontmatter
        brace_count = 0
        end_idx = 0
        for i, char in enumerate(content):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        if end_idx > 0:
            body = content[end_idx:]
        else:
            body = content
    else:
        body = content

    lines = body.split('\n')[:n]
    in_code_block = False
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue
        if not in_code_block and line.startswith('# '):
            return True
    return False


def fix_file(filepath: Path) -> bool:
    """Add H1 title to a lesson file if missing."""
    content = filepath.read_text(encoding='utf-8')

    if has_h1_in_first_lines(content):
        return False

    title = extract_title_from_frontmatter(content)
    if not title:
        print(f"  SKIP (no title in frontmatter): {filepath}", file=sys.stderr)
        return False

    # Find end of frontmatter
    match = re.search(r'^---\s*\n.*?\n---\s*\n', content, re.DOTALL)
    if match:
        frontmatter_end = match.end()
        before = content[:frontmatter_end]
        after = content[frontmatter_end:]
    elif content.strip().startswith('{'):
        # Raw JSON frontmatter
        brace_count = 0
        end_idx = 0
        for i, char in enumerate(content):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        if end_idx > 0:
            # Find the next newline after closing brace
            newline_idx = content.find('\n', end_idx)
            if newline_idx > 0:
                frontmatter_end = newline_idx + 1
            else:
                frontmatter_end = end_idx
            before = content[:frontmatter_end]
            after = content[frontmatter_end:]
        else:
            return False
    else:
        return False

    # Add H1 title
    new_content = before + f"# {title}\n\n" + after
    filepath.write_text(new_content, encoding='utf-8')
    return True


def main():
    lessons_dir = Path('lessons')
    fixed = 0
    skipped = 0

    for md_file in lessons_dir.rglob('*.md'):
        if md_file.name == 'README.md':
            continue
        try:
            if fix_file(md_file):
                fixed += 1
                print(f"  FIXED: {md_file}")
            else:
                skipped += 1
        except Exception as e:
            print(f"  ERROR: {md_file}: {e}", file=sys.stderr)

    print(f"\nFixed: {fixed}, Skipped: {skipped}")


if __name__ == '__main__':
    main()
