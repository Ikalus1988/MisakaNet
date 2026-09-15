#!/usr/bin/env python3
"""Normalize lesson `domain` values onto the canonical vocabulary (issue #1687).

Why this exists
---------------
The domain vocabulary had drifted into 56 values containing obvious duplicates —
``devops``/``ops``, ``network``/``networking``, ``agent``/``agents``/``ai-agents``,
``data``/``data-engineering``/``data-pipeline``, ``ruby/performance``,
``memory_management`` — plus 39 lessons whose ``domain`` was ``contrib``, the
*directory* they live in rather than a topic. ``lesson_gate.py`` accepted every value
that some lesson already used, so the vocabulary was self-perpetuating: any value,
once written, became legal forever and nobody could review it.

``data/domains.json`` is now the single source of truth (canonical values, aliases,
retired values, and the per-lesson replacement for the directory-shaped ones), and
this script applies it to the corpus. The two are checked against each other:
``--check`` fails when a lesson carries a value that is neither canonical nor an
alias, so a new lesson cannot quietly widen the vocabulary.

Usage:
  python3 scripts/normalize_domains.py --check     # gate: report drift (exit 1)
  python3 scripts/normalize_domains.py --write     # rewrite frontmatter in place
  python3 scripts/normalize_domains.py --list      # show what would change
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VOCAB_PATH = REPO / "data" / "domains.json"
LESSONS = REPO / "lessons"
COUNTED_DIRS = ("core", "contrib", "en")
EXCLUDED = {"README.md", "TEMPLATE.md", "index.md", "CONTRIBUTING.md"}

DOMAIN_LINE_RE = re.compile(r'^(domain:[ \t]*)(["\']?)([^"\'\n]*?)(\2)([ \t]*)$', re.M)


def load_vocab() -> dict:
    return json.loads(VOCAB_PATH.read_text(encoding="utf-8"))


def frontmatter_bounds(text: str) -> tuple[int, int] | None:
    """(start, end) of the frontmatter *content*, or None when there is none."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return 4, end


def read_domain(text: str) -> str | None:
    bounds = frontmatter_bounds(text)
    if not bounds:
        return None
    raw = text[bounds[0]:bounds[1]].strip()
    if raw.startswith("{"):
        try:
            value = json.JSONDecoder().raw_decode(raw)[0].get("domain")
        except Exception:
            return None
    else:
        match = DOMAIN_LINE_RE.search(text[bounds[0]:bounds[1]])
        if not match:
            return None
        value = match.group(3)
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value).strip().strip('"').lower() if value is not None else None


def lesson_files() -> list[Path]:
    out = []
    for path in sorted(LESSONS.rglob("*.md")):
        if path.name in EXCLUDED or path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if text.startswith("---"):
            out.append(path)
    return out


def target_domain(path: Path, current: str, vocab: dict) -> str | None:
    """The canonical value this lesson should carry, or None when it already does."""
    replacement = (vocab.get("contrib_replacement") or {}).get(path.relative_to(REPO).as_posix())
    if replacement:
        return replacement if replacement != current else None
    alias = (vocab.get("aliases") or {}).get(current)
    if alias:
        return alias
    return None


def rewrite_domain(text: str, target: str) -> str:
    """Rewrite the `domain:` value, handling YAML and JSON frontmatter.

    Both forms are edited *in place* rather than re-serialized: some lessons append a
    YAML-ish ``provenance:`` tail after the JSON object inside the same frontmatter
    block, and re-dumping the parsed object would silently drop it.
    """
    bounds = frontmatter_bounds(text)
    assert bounds, "rewrite called on a file without frontmatter"
    head, block, tail = text[:bounds[0]], text[bounds[0]:bounds[1]], text[bounds[1]:]

    if block.strip().startswith("{"):
        new_block, n = re.subn(r'("domain"\s*:\s*")([^"]*)(")', lambda m: m.group(1) + target + m.group(3),
                               block, count=1)
        assert n == 1, "no `\"domain\":` entry to rewrite"
        return head + new_block + tail

    def sub(match: re.Match) -> str:
        return f"{match.group(1)}{match.group(2) or ''}{target}{match.group(2) or ''}{match.group(5)}"

    new_block, n = DOMAIN_LINE_RE.subn(sub, block, count=1)
    assert n == 1, "no `domain:` line to rewrite"
    return head + new_block + tail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift and exit 1 (gate mode)")
    ap.add_argument("--write", action="store_true", help="apply the vocabulary in place")
    ap.add_argument("--list", action="store_true", help="print the planned changes")
    args = ap.parse_args()

    vocab = load_vocab()
    canonical = set(vocab["canonical"])
    aliases = vocab.get("aliases") or {}
    retired = vocab.get("retired") or {}

    changes: list[tuple[Path, str, str]] = []
    unknown: list[tuple[Path, str]] = []
    for path in lesson_files():
        current = read_domain(path.read_text(encoding="utf-8", errors="replace"))
        if not current:
            continue
        # Decide by "is a change needed", then classify: a lesson that was just
        # rewritten to its canonical target is neither drift nor unknown (it is still
        # listed in contrib_replacement, which is what made an earlier version of this
        # loop report the files it had just fixed).
        target = target_domain(path, current, vocab)
        if target is not None:
            changes.append((path, current, target))
        elif current in canonical:
            continue
        else:
            reason = retired.get(current)
            unknown.append((path, f"{current!r}{f' ({reason})' if reason else ''}"))

    if args.list or args.check:
        for path, current, target in changes:
            print(f"{path.relative_to(REPO)}: {current} → {target}")
    for path, value in unknown:
        print(f"UNKNOWN {path.relative_to(REPO)}: domain {value} is not in data/domains.json", file=sys.stderr)

    if args.write:
        for path, _current, target in changes:
            path.write_text(rewrite_domain(path.read_text(encoding="utf-8"), target), encoding="utf-8")
        print(f"normalized {len(changes)} lesson(s)", file=sys.stderr)

    if args.check:
        if unknown:
            print(f"\n{len(unknown)} lesson(s) carry a domain outside the vocabulary.", file=sys.stderr)
            print("Add it to data/domains.json (canonical) or map it (aliases) — "
                  "the vocabulary is the review surface for domains, not the corpus.", file=sys.stderr)
            return 1
        if changes:
            print(f"\n{len(changes)} lesson(s) still carry a non-canonical domain "
                  f"(alias or directory-shaped). Run: python3 scripts/normalize_domains.py --write",
                  file=sys.stderr)
            return 1
        print(f"✅ every lesson domain is canonical ({len(canonical)} values in data/domains.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
