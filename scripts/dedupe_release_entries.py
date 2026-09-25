#!/usr/bin/env python3
"""Remove the duplicate entries `release-please` puts in the newest release section.

`release-please` builds a release's notes from the conventional commits between two tags. When a PR reaches
`main` through a **merge commit whose message also carries the PR title** (GitHub fills the body with it by
default), the branch commit and the merge commit both look conventional — so the change is listed twice.
Measured 2026-09-25 on the 2.35.0 release PR:

    137 bullet lines, 104 distinct entries, 33 of them listed twice

`tests/test_changelog_shape.py` refuses to release in that state, and it is right to: the release notes are
the one page a user reads to decide whether to upgrade, and an entry that appears twice reads as two changes.
The *cause* is fixed (every merge path squashes now — pinned by `test_every_merge_path_squashes`), but the
damage from the merges that already happened is in the commit range until the release that carries it is
tagged, and `release-please` regenerates the section on every push to `main`. So the repair has to happen
where the section is generated, on every run, or it is undone by the next push — which is why
`release-please.yml` calls this script after the action instead of a human editing the release PR by hand.

Which copy is kept: the one carrying the **most reference groups**, because that is the copy with the PR
link (`([#2121](…))`) rather than only the bare commit link. Ties keep the first occurrence. Order is the
generator's; this script only removes lines.

    python3 scripts/dedupe_release_entries.py --check   # exit 1 if the newest section has duplicates
    python3 scripts/dedupe_release_entries.py           # rewrite in place, print what it removed
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The same peeling rule the changelog gate uses: the trailing reference groups are what differ between two
# copies of one change, so they are stripped before comparing.
_TRAILING_GROUP = re.compile(r"\s*\((?:[^()]|\([^()]*\))*\)\s*$")
_BULLET = re.compile(r"^\s*\*\s+")


def normalise(entry: str) -> str:
    """The entry without its trailing `([#N](…)) ([sha](…))` groups."""
    text = entry.strip()
    while True:
        peeled = _TRAILING_GROUP.sub("", text)
        if peeled == text:
            return text
        text = peeled


def reference_count(entry: str) -> int:
    """How many trailing reference groups the entry carries — the PR link makes a copy worth keeping."""
    text, count = entry.strip(), 0
    while True:
        peeled = _TRAILING_GROUP.sub("", text)
        if peeled == text:
            return count
        count += 1
        text = peeled


def newest_section_bounds(lines: list[str]) -> tuple[int, int]:
    """(start, end) line indexes of the most recent release block."""
    start = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    if start is None:
        return 0, 0
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return start, end


def dedupe(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (new text, [(kept, dropped), …]) — only the newest section is touched."""
    lines = text.splitlines(keepends=True)
    start, end = newest_section_bounds(lines)
    if start == end:
        return text, []

    section = lines[start:end]
    best: dict[str, tuple[int, str]] = {}   # normalised entry -> (first line index, the copy to keep)
    order: list[str] = []
    dropped: list[tuple[str, str]] = []
    for index, line in enumerate(section):
        if not _BULLET.match(line):
            continue
        key = normalise(line)
        if key not in best:
            best[key] = (index, line)
            order.append(key)
            continue
        first_index, kept_line = best[key]
        if reference_count(line) > reference_count(kept_line):
            # The later copy carries the PR link; keep it, at the position of the first occurrence.
            best[key] = (first_index, line)
            dropped.append((line.rstrip("\n"), kept_line.rstrip("\n")))
        else:
            dropped.append((kept_line.rstrip("\n"), line.rstrip("\n")))

    if not dropped:
        return text, []

    emitted: set[str] = set()
    out: list[str] = []
    for line in section:
        if not _BULLET.match(line):
            out.append(line)
            continue
        key = normalise(line)
        if key in emitted:
            continue
        emitted.add(key)
        out.append(best[key][1])
    return "".join(lines[:start] + out + lines[end:]), dropped


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove duplicate entries from the newest release section")
    parser.add_argument("path", nargs="?", default=str(REPO / "CHANGELOG.md"))
    parser.add_argument("--check", action="store_true", help="exit 1 if there is anything to remove")
    args = parser.parse_args()

    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    new_text, dropped = dedupe(text)

    if not dropped:
        print(f"{path.name}: no duplicate entries in the newest release section")
        return 0

    print(f"{path.name}: {len(dropped)} duplicate entr{'y' if len(dropped) == 1 else 'ies'} in the newest section")
    for kept, gone in dropped:
        print(f"  dropped {gone[:110]}")
        print(f"   kept   {kept[:110]}")

    if args.check:
        print("refusing to rewrite: --check was asked for")
        return 1

    path.write_text(new_text, encoding="utf-8")
    print(f"rewrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
