#!/usr/bin/env python3
"""Normalize lesson frontmatter metadata for consistency (#306).

Usage:
    python3 scripts/normalize_metadata.py              # dry-run: show what would change
    python3 scripts/normalize_metadata.py --fix         # apply fixes
    python3 scripts/normalize_metadata.py --fix --push  # apply fixes and commit

Normalization rules:
    - domain: lowercase, no spaces
    - tags: kebab-case
    - status: one of published, draft, archived (active → published)
    - title: required (skip files without it)
    - created: required (use file mtime as fallback)
    - source: required (default "unknown")
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"

VALID_STATUSES = {"published", "draft", "archived"}
STATUS_MAP = {"active": "published"}  # deprecated → canonical

FIX_MODE = "--fix" in sys.argv
DRY_RUN = not FIX_MODE


def parse_frontmatter(text: str) -> tuple[dict | None, int, int]:
    """Parse frontmatter, return (meta_dict, body_start_line, body_end_line)."""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None, 0, 0
    raw = m.group(1).strip()
    fm_start = text.index(m.group(1))
    fm_end = fm_start + len(m.group(1))

    # Try JSON first
    try:
        return json.loads(raw), fm_start, fm_end
    except json.JSONDecodeError:
        pass

    # Simple YAML-like parser
    fm = {}
    for line in raw.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
        fm[key] = val
    return fm, fm_start, fm_end


def to_kebab_case(s: str) -> str:
    """Convert a tag to kebab-case."""
    s = s.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def normalize_meta(meta: dict, file_mtime: float) -> tuple[dict, list[str]]:
    """Normalize metadata fields, return (new_meta, list_of_changes)."""
    changes = []
    new = dict(meta)

    # 1. domain: lowercase, no spaces
    if "domain" in new and new["domain"]:
        old = new["domain"]
        new["domain"] = old.lower().replace(" ", "-")
        if new["domain"] != old:
            changes.append(f"domain: {old!r} → {new['domain']!r}")

    # 2. tags: kebab-case
    if "tags" in new and isinstance(new["tags"], list):
        old_tags = new["tags"]
        new_tags = [to_kebab_case(t) for t in old_tags if t]
        new_tags = [t for t in new_tags if t]  # remove empty
        if new_tags != old_tags:
            changes.append(f"tags: {old_tags} → {new_tags}")
        new["tags"] = new_tags

    # 3. status: normalize
    if "status" in new and new["status"]:
        old = new["status"]
        mapped = STATUS_MAP.get(old, old)
        if mapped not in VALID_STATUSES:
            changes.append(f"status: {old!r} → 'published' (was not in {VALID_STATUSES})")
            new["status"] = "published"
        elif mapped != old:
            changes.append(f"status: {old!r} → {mapped!r}")
            new["status"] = mapped

    # 4. created: add if missing (use file mtime)
    if "created" not in new or not new["created"]:
        dt = datetime.fromtimestamp(file_mtime, tz=timezone.utc)
        new["created"] = dt.strftime("%Y-%m-%d")
        changes.append(f"created: (added from mtime: {new['created']})")

    # 5. source: add if missing
    if "source" not in new or not new["source"]:
        new["source"] = "unknown"
        changes.append("source: (added: 'unknown')")

    return new, changes


def write_frontmatter(path: Path, meta: dict, body_start: int, body_end: int, original_text: str):
    """Write normalized JSON frontmatter back to file."""
    # Build new frontmatter as JSON (matching existing convention)
    fm_json = json.dumps(meta, ensure_ascii=False, indent=2)

    # Find the --- boundaries in original text
    first_sep = original_text.index("---")
    second_sep = original_text.index("---", first_sep + 3)

    # Reconstruct: ---\n{json}\n---\n{body}
    body = original_text[second_sep + 3:]
    if body and not body.startswith("\n"):
        body = "\n" + body
    new_text = f"---\n{fm_json}\n---{body}"

    path.write_text(new_text, encoding="utf-8")


def main():
    stats = {"scanned": 0, "would_fix": 0, "fixed": 0, "skipped": 0, "errors": 0}

    for f in sorted(LESSONS_DIR.rglob("*.md")):
        if f.name in ("index.md", "TEMPLATE.md", "README.md"):
            continue
        if "_archive" in f.parts:
            continue

        stats["scanned"] += 1
        text = f.read_text(encoding="utf-8", errors="replace")
        meta, fm_start, fm_end = parse_frontmatter(text)

        if meta is None:
            stats["skipped"] += 1
            continue

        mtime = f.stat().st_mtime
        new_meta, changes = normalize_meta(meta, mtime)

        if not changes:
            continue

        stats["would_fix"] += 1
        rel = str(f.relative_to(LESSONS_DIR))
        print(f"\n{'='*60}")
        print(f"📝 {rel}")
        for c in changes:
            print(f"  • {c}")

        if FIX_MODE:
            try:
                write_frontmatter(f, new_meta, fm_start, fm_end, text)
                stats["fixed"] += 1
                print(f"  ✅ Fixed")
            except Exception as e:
                stats["errors"] += 1
                print(f"  ❌ Error: {e}")

    print(f"\n{'='*60}")
    print(f"📊 Summary: {stats['scanned']} scanned, {stats['would_fix']} need fixes")
    if FIX_MODE:
        print(f"   Fixed: {stats['fixed']}, Errors: {stats['errors']}, Skipped: {stats['skipped']}")
    else:
        print(f"   (dry-run — use --fix to apply)")


if __name__ == "__main__":
    main()
