#!/usr/bin/env python3
"""Clean empty verification templates and irrelevant commands."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTRIB = REPO / "lessons" / "contrib"


def clean_verification(filepath: Path) -> bool:
    """Remove empty verification templates and irrelevant commands."""
    content = filepath.read_text(encoding='utf-8')
    original = content

    # Remove echo verification commands
    content = re.sub(
        r'```bash\n\s*echo\s+.*?Verification\s+commands\s+for:.*?\n```',
        '',
        content,
        flags=re.DOTALL
    )

    # Remove irrelevant curl commands
    content = re.sub(
        r'```bash\n\s*curl\s+.*?localhost:8080/health.*?\n```',
        '',
        content,
        flags=re.DOTALL
    )

    # Remove irrelevant python commands
    content = re.sub(
        r'```bash\n\s*python3\s+.*?Python\s+check\s+passed.*?\n```',
        '',
        content,
        flags=re.DOTALL
    )

    # Remove git status commands
    content = re.sub(
        r'```bash\n\s*git\s+status\s*\n```',
        '',
        content,
        flags=re.DOTALL
    )

    # Remove docker ps commands
    content = re.sub(
        r'```bash\n\s*docker\s+ps\s*\n```',
        '',
        content,
        flags=re.DOTALL
    )

    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    count = 0
    for filepath in sorted(CONTRIB.glob("*.md")):
        if clean_verification(filepath):
            try:
                print(f"Cleaned: {filepath.name}")
            except UnicodeEncodeError:
                print(f"Cleaned: {filepath.stem}")
            count += 1

    print(f"\nTotal cleaned: {count}")


if __name__ == "__main__":
    main()
