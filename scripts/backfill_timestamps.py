#!/usr/bin/env python3
"""Backfill missing timestamps and source fields in core lessons from git history.

For each core lesson (not in contrib/), extracts created/updated dates from
git log and injects them into the JSON frontmatter.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"
DRY_RUN = "--dry-run" in sys.argv

def git_log_dates(path: Path) -> tuple[str | None, str | None]:
    """Get created and last-updated dates from git history."""
    rel = path.relative_to(REPO_ROOT)
    # First commit (creation date)
    try:
        created = subprocess.run(
            ["git", "log", "--follow", "--reverse", "--format=%ai", "--", str(rel)],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30
        )
        first_date = created.stdout.strip().split("\n")[0] if created.stdout.strip() else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        first_date = None

    # Last commit (update date)
    try:
        updated = subprocess.run(
            ["git", "log", "--follow", "--format=%ai", "--", str(rel)],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30
        )
        last_date = updated.stdout.strip().split("\n")[0] if updated.stdout.strip() else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        last_date = None

    return first_date, last_date


def fix_lesson(path: Path) -> bool:
    """Fix frontmatter of a single lesson. Returns True if modified."""
    content = path.read_text(encoding="utf-8")

    # Extract frontmatter block
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return False

    raw = m.group(1)
    try:
        fm = json.loads(raw)
    except json.JSONDecodeError:
        return False

    modified = False

    # Backfill source
    if not fm.get("source"):
        fm["source"] = "git"
        modified = True

    # Backfill timestamps from git if missing
    needs_created = not fm.get("created")
    needs_updated = not fm.get("updated")

    if needs_created or needs_updated:
        created_dt, updated_dt = git_log_dates(path)
        if needs_created and created_dt:
            # Convert "2026-06-13 12:00:00 +0800" → "2026-06-13 00:00:00 UTC"
            date_part = created_dt.split()[0]
            fm["created"] = f"{date_part} 00:00:00 UTC"
            modified = True
        if needs_updated and updated_dt:
            date_part = updated_dt.split()[0]
            fm["updated"] = f"{date_part} 00:00:00 UTC"
            modified = True

    if not modified:
        return False

    # Write back
    new_raw = json.dumps(fm, ensure_ascii=False)
    new_content = content.replace(raw, new_raw, 1)
    if DRY_RUN:
        print(f"  Would fix: {path.name} — created={fm.get('created','?')} updated={fm.get('updated','?')} source={fm.get('source','?')}")
    else:
        path.write_text(new_content, encoding="utf-8")
        print(f"  Fixed: {path.name} — created={fm.get('created','?')[:10]} updated={fm.get('updated','?')[:10]}")

    return True


def main():
    paths = sorted(LESSONS_DIR.rglob("*.md"))
    fixed = 0
    skipped = 0

    print(f"{'Dry-run' if DRY_RUN else 'Fixing'} core lessons...\n")

    for path in paths:
        if path.name in ("index.md", "README.md"):
            continue
        if "_archive" in str(path):
            continue
        if "contrib" in str(path):
            continue  # Skip contrib — those are from external contributors

        if fix_lesson(path):
            fixed += 1
        else:
            skipped += 1

    print(f"\n{'='*40}")
    print(f"Fixed:  {fixed}")
    print(f"Skipped (already had metadata): {skipped}")


if __name__ == "__main__":
    main()
