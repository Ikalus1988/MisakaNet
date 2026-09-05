#!/usr/bin/env python3
"""Sync data/intake-kind-hints.json into workers/lib/utils.js.

Embeds the patterns as JS ``RegExp`` arrays so the single-file Cloudflare
worker stays self-contained.  Run after editing the JSON, or use ``--check``
to verify the JS file is up to date (CI guard).

Usage:
    python3 scripts/sync_intake_hints.py           # patch utils.js
    python3 scripts/sync_intake_hints.py --check   # verify only (exit 1 if stale)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "intake-kind-hints.json"
JS_PATH = ROOT / "workers" / "lib" / "utils.js"

_START = "// -- intake-kind-hints:start (auto-generated, do not edit) --"
_END = "// -- intake-kind-hints:end --"

_OLD_Q_START = "const QUESTION_HINTS = ["
_OLD_F_START = "const FAILURE_HINTS = ["


def _to_js_regex(pattern: str) -> str:
    """Convert a Python regex pattern string to a JS regex literal.

    Python string: ``\\bhow`` (two chars: backslash, b, h, o, w)
    → JS regex literal source: ``/\\bhow/`` (regex engine sees ``\\b`` = ``\\b``)

    The key insight: Python's ``\\`` (one backslash) in the output becomes
    ``\\`` in JS source (two chars), which the regex engine interprets as
    ``\\b`` (one backslash + b) = word boundary.  So we just need to escape
    forward slashes for the JS regex literal syntax — no backslash doubling.
    """
    return pattern.replace("/", "\\/")


def _build_js_block(hints: dict) -> str:
    """Return the JS block that replaces the old arrays."""
    lines = [_START]
    lines.append("const QUESTION_HINTS = [")
    for p in hints["question_hints"]:
        lines.append(f"  /{_to_js_regex(p)}/i,")
    lines.append("];")
    lines.append("")
    lines.append("const FAILURE_HINTS = [")
    for p in hints["failure_hints"]:
        lines.append(f"  /{_to_js_regex(p)}/i,")
    lines.append("];")
    lines.append(_END)
    return "\n".join(lines)


def _find_old_block(js: str) -> tuple[int, int]:
    """Find the range of old QUESTION_HINTS through FAILURE_HINTS arrays."""
    # Prefer markers (idempotent — second run finds these)
    s = js.find(_START)
    if s >= 0:
        e = js.find(_END, s)
        if e >= 0:
            return s, e + len(_END)
    # First run: find the raw arrays
    q_start = js.find(_OLD_Q_START)
    if q_start < 0:
        return -1, -1
    f_start = js.find(_OLD_F_START, q_start)
    if f_start < 0:
        return -1, -1
    end_marker = js.find("];", f_start)
    if end_marker < 0:
        return -1, -1
    return q_start, end_marker + 2


def sync(check_only: bool = False) -> bool:
    hints = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    js = JS_PATH.read_text(encoding="utf-8")
    new_block = _build_js_block(hints)

    start, end = _find_old_block(js)
    if start < 0:
        print("ERROR: could not locate QUESTION_HINTS/FAILURE_HINTS in utils.js", file=sys.stderr)
        return False

    patched = js[:start] + new_block + js[end:]

    if check_only:
        if patched == js:
            print("OK: utils.js is in sync with intake-kind-hints.json")
            return True
        print("STALE: utils.js differs from intake-kind-hints.json — run `python3 scripts/sync_intake_hints.py`", file=sys.stderr)
        return False

    JS_PATH.write_text(patched, encoding="utf-8")
    print(f"Patched {JS_PATH.relative_to(ROOT)}")
    return True


def main() -> int:
    check = "--check" in sys.argv
    return 0 if sync(check_only=check) else 1


if __name__ == "__main__":
    sys.exit(main())
