#!/usr/bin/env python3
"""
Preview what a fatal-guard tombstone would look like as a MisakaNet lesson.

This is the opt-in report path: preview locally before deciding to submit.
No data is uploaded or sent anywhere.

Usage:
    # Preview from tombstone file
    python3 scripts/report_preview.py tombstone.json

    # Preview from stdin
    fatal-guard -- node app.js 2>&1 | python3 scripts/report_preview.py --stdin

    # Generate draft lesson (local only)
    python3 scripts/report_preview.py tombstone.json --draft
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_tombstone(path: str | None, use_stdin: bool) -> dict:
    """Load tombstone JSON from file or stdin."""
    if use_stdin:
        raw = sys.stdin.read()
    elif path:
        raw = Path(path).read_text(encoding="utf-8")
    else:
        raise ValueError("Provide tombstone file path or --stdin")

    # Try to extract JSON from mixed output
    json_match = re.search(r'\{[^{}]*"reason"[^{}]*\}', raw, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return json.loads(raw)


def redact(text: str) -> str:
    """Redact sensitive information."""
    # Tokens / secrets
    text = re.sub(r'ghp_[a-zA-Z0-9]{36}', 'ghp_[REDACTED]', text)
    text = re.sub(r'gho_[a-zA-Z0-9]{36}', 'gho_[REDACTED]', text)
    text = re.sub(r'sk-[a-zA-Z0-9]{48}', 'sk-[REDACTED]', text)
    text = re.sub(r'Bearer [a-zA-Z0-9._-]{20,}', 'Bearer [REDACTED]', text)
    # Email
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL_REDACTED]', text)
    # Absolute paths
    text = re.sub(r'/home/[a-zA-Z0-9_-]+/', '/home/[USER]/', text)
    text = re.sub(r'/Users/[a-zA-Z0-9_-]+/', '/Users/[USER]/', text)
    text = re.sub(r'C:\\Users\\[a-zA-Z0-9_-]+\\', r'C:\\Users\\[USER]\\', text)
    return text


def generate_preview(tombstone: dict) -> str:
    """Generate a human-readable preview of the tombstone."""
    reason = tombstone.get("reason", "unknown")
    timestamp = tombstone.get("timestamp", datetime.now(timezone.utc).isoformat())
    pid = tombstone.get("pid", "?")
    exit_code = tombstone.get("exit_code", "?")
    snippet = tombstone.get("snippet", "")
    command = tombstone.get("command", "")

    snippet = redact(snippet)
    command = redact(command)

    preview = f"""
╔══════════════════════════════════════════════════════════════╗
║  MisakaNet — Fatal Guard Report Preview                     ║
║  This is a LOCAL preview. Nothing is uploaded.              ║
╚══════════════════════════════════════════════════════════════╝

Timestamp:  {timestamp}
PID:        {pid}
Exit Code:  {exit_code}
Command:    {command[:80]}

Reason:
{redact(reason)[:500]}

Snippet (redacted):
{snippet[:500]}

──────────────────────────────────────────────────────────────
To generate a draft lesson (local only):
  python3 scripts/report_preview.py <tombstone.json> --draft

To submit as a GitHub issue (requires auth):
  python3 scripts/tombstone_to_draft.py --from-file <tombstone.json> --submit
"""
    return preview


def generate_draft(tombstone: dict) -> str:
    """Generate a draft lesson markdown."""
    reason = tombstone.get("reason", "unknown error")
    snippet = redact(tombstone.get("snippet", ""))
    command = redact(tombstone.get("command", ""))
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Generate slug from reason
    slug = re.sub(r'[^\w\s-]', '', reason.lower())
    slug = re.sub(r'[\s]+', '-', slug)[:60].strip('-')

    title = reason[:80]

    return f"""---
title: "{title}"
domain: "devops"
source: "fatal-guard automated capture"
status: "draft"
confidence: 0.7
created: {timestamp}
updated: {timestamp}
tags: ["fatal-guard", "crash", "auto-generated"]
---

## Problem

Process crashed with: {reason[:200]}

Command: `{command[:200]}`

## Root Cause

(TODO: analyze the crash trace)

## Fix

(TODO: document the fix)

## Verification

(TODO: verify the fix works)

## Raw Snippet

```
{snippet[:1000]}
```
"""


def main():
    parser = argparse.ArgumentParser(description="Preview fatal-guard tombstone report")
    parser.add_argument("file", nargs="?", help="Tombstone JSON file")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    parser.add_argument("--draft", action="store_true", help="Generate draft lesson file (local only)")
    parser.add_argument("--output", "-o", help="Output directory for draft (default: lessons/drafts/)")
    args = parser.parse_args()

    if not args.file and not args.stdin:
        parser.print_help()
        sys.exit(1)

    tombstone = load_tombstone(args.file, args.stdin)

    if args.draft:
        draft = generate_draft(tombstone)
        out_dir = Path(args.output) if args.output else REPO / "lessons" / "drafts"
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r'[^\w-]', '-', tombstone.get("reason", "unknown")[:40].lower()).strip('-')
        out_path = out_dir / f"{slug}.md"
        out_path.write_text(draft, encoding="utf-8")
        print(f"Draft written to: {out_path}")
    else:
        print(generate_preview(tombstone))


if __name__ == "__main__":
    main()
