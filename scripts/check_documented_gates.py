#!/usr/bin/env python3
"""Does the gate table in `docs/ci-gates.md` still match the ruleset that actually enforces?

`main` is protected by ruleset 23826057, *"main: the deterministic gates"*. `docs/ci-gates.md`
documents that set as a table, and the same file carries the `curl` that reads the ruleset back.
**The command was documented; nothing ever ran it.** So the one fact the whole document is built
on could change silently, and a reader would carry a stale list of the checks that block a merge.

The failure mode is not hypothetical. This repository spent a session removing twenty-three
hand-written counts of "the required checks" out of its prose, and the surviving one sat in the
very file it had nominated as the single statement of the set. A grep for numbers in prose does
not fix that: it is a heuristic over every file, it goes on finding new shapes to miss, and it
makes two thousand documents into a place CI can fail. This script instead checks the one thing
that is actually true or false — *the live set, against the documented set* — and lets the
document carry no count at all. The count is then a property of the table, not a sentence
somewhere that has to be remembered.

Run it directly, or let `.github/workflows/check-documented-gates.yml` run it weekly. The
schedule follows `gate-mutation-audit.yml`: this is a question about the ruleset, and the
ruleset changes on a timescale of months, not commits, so paying for it on every PR would
re-answer yesterday's answer slowly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "ci-gates.md"
RULESET_ID = "23826057"
RULESET_API = f"https://api.github.com/repos/Ikalus1988/MisakaNet/rulesets/{RULESET_ID}"

# The heading the documented set lives under. Everything before it is scope; the advisory tables
# further down name checks that deliberately do **not** block a merge, and counting those would
# invert the document's own point.
SECTION = "## Hard Gates (must pass)"

# A table body row in that section: `| **gate** | `lesson-gate.yml` | ... |`
ROW = re.compile(r"^\|\s*(?P<context>[^|]+?)\s*\|")


def parse_documented(path: Path) -> list[str]:
    """The contexts `docs/ci-gates.md` claims block a merge, in document order.

    Returns them with the table's decoration removed, so a cell written `**gate**` and a cell
    written `` `gate` `` compare equal. Only rows in the Hard Gates section are read.
    """
    text = path.read_text(encoding="utf-8")
    start = text.find(SECTION)
    if start < 0:
        raise SystemExit(f"fail: {SECTION!r} is not in {path}")
    # Scan *after* the heading line. Slicing from `start` includes the heading itself, and the
    # loop below stops at the next `## ` — which, left unskipped, is the line it just started on.
    body = text[start:].splitlines()[1:]
    contexts: list[str] = []
    for line in body:
        if line.startswith("## "):
            break  # the next section is a different set
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("Check", "Check (context as GitHub reports it)"):
            continue
        if set(cells[0]) <= {"-", ":"}:  # the |---|---| separator
            continue
        context = cells[0].strip("*`_ ")
        if context:
            contexts.append(context)
    return contexts


def contexts_from_ruleset(payload: dict) -> list[str]:
    """The contexts the ruleset requires, from a decoded API response."""
    found: list[str] = []
    for rule in payload.get("rules", []):
        if rule.get("type") != "required_status_checks":
            continue
        for entry in rule.get("parameters", {}).get("required_status_checks", []):
            context = entry.get("context")
            if context:
                found.append(context)
    return found


def fetch_live(token: str, timeout: int = 30) -> dict:
    """Read the ruleset. The only place this script touches the network."""
    request = urllib.request.Request(
        RULESET_API,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "misakanet-gate-ratchet",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def token_from_environment() -> str:
    """The workflow's PAT, or nothing — this script never reads a file of credentials itself."""
    for name in ("SHELDON_PAT", "GITHUB_TOKEN"):
        value = os.environ.get(name)
        if value:
            return value
    return ""


def report(documented: list[str], live: list[str], stream, quiet: bool = False) -> int:
    """Print what diverged. Returns the process exit code."""
    missing = [context for context in live if context not in documented]
    invented = [context for context in documented if context not in live]

    if not missing and not invented:
        if not quiet:
            print(f"OK: the documented gates match ruleset {RULESET_ID} ({len(live)} contexts)")
        return 0

    print(f"FAIL: the gate table in docs/ci-gates.md no longer matches ruleset {RULESET_ID}.",
          file=stream)
    if missing:
        print("\n  the ruleset requires these, the document does not list them:", file=stream)
        for context in missing:
            print(f"    + {context}", file=stream)
    if invented:
        print("\n  the document lists these, the ruleset does not require them:", file=stream)
        for context in invented:
            print(f"    - {context}", file=stream)
    print(
        "\n  Read the ruleset back with the command in docs/ci-gates.md, update the table, and\n"
        "  keep the count out of the prose — the table's length is the count.",
        file=stream,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--from-file",
        type=Path,
        help="read a saved ruleset JSON response instead of calling GitHub (for tests/offline runs)",
    )
    parser.add_argument("--doc", type=Path, default=DOC, help="the document holding the table")
    parser.add_argument("--quiet", action="store_true", help="print only on divergence")
    args = parser.parse_args(argv)

    documented = parse_documented(args.doc)
    if args.from_file:
        payload = json.loads(args.from_file.read_text(encoding="utf-8"))
    else:
        token = token_from_environment()
        if not token:
            print(
                "fail: no token. Set SHELDON_PAT, or pass --from-file with a saved ruleset response.",
                file=sys.stderr,
            )
            return 2
        try:
            payload = fetch_live(token)
        except urllib.error.URLError as error:
            print(f"fail: could not read ruleset {RULESET_ID}: {error}", file=sys.stderr)
            return 2

    if not documented:
        print("fail: the Hard Gates table in the document yielded no rows.", file=sys.stderr)
        return 2

    stream = sys.stderr if args.quiet else sys.stdout
    return report(documented, contexts_from_ruleset(payload), stream, quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
