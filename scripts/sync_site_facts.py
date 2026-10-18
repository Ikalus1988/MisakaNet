#!/usr/bin/env python3
"""Site-facts SSOT: the homepage Quickstart command strings and its tool count (#1895).

Why this file exists
--------------------
``scripts/sync_lesson_count.py`` already owns the corpus *counts* (lessons, domains). The same
"one fact, many faces, one writer" defect also lives in the homepage Quickstart's **command
strings** and its **tool count**, and nothing compared them:

    docs/index.html  "npx @misaka-net/misakanet-setup"   (Track A step 1)
    README.md        "npx @misaka-net/misakanet-setup"   (the installer row of "How to use it")

and the same for the ``--verify`` invocation and the MCP ``curl`` search call. Each surface
hand-writes its own copy. A one-character drift (a renamed npm package, a dropped flag) was
invisible to every gate — the site would teach a command the README does not, and both would
keep passing CI.

The tool count was worse than invisible: it was wrong. ``docs/index.html``'s self-check line
said "claude mcp list shows misakanet with 7 tools" while ``canonical_mcp_tools()`` — the
documented set in ``AGENTS.md`` §3.2 against what ``workers/register-proxy-sw.js`` registers —
has been 8 since ``misakanet_me_inbox`` landed. ``tests/test_mcp_tool_count_ssot.py`` pins the
count on the READMEs, the skill and ``docs/quickstart.md``; the homepage sentence was never on
that list, so nothing noticed it sitting at 7.

The route, and why not ``sync_lesson_count.py``
-----------------------------------------------
Issue #1895 preferred extending ``scripts/sync_lesson_count.py``'s ``SITES``. That registry is
deliberately count-shaped (a named group ``n`` rewritten to a canonical number) and its own
doctrine is "the registry may shrink, never grow" — a correct row over a surface that should
not carry the number is still the wrong shape. Command strings are not counts: there is no
number to rewrite to, the invariant is *verbatim parity* between two surfaces, and the error a
reader needs names **both** files. Stuffing that into the lesson-count module would make its
name and docstring lie about what it gates. This sibling module is the other half of the same
SSOT idea, and the tool count reuses the existing ``Site`` machinery (imported) rather than
reimplementing it.

What is managed (three command facts + one count)
-------------------------------------------------
Each command fact names a *source* surface (README.md — the repo-facing prose) and one or more
*mirrors* (docs/index.html — the bytes a crawler or a no-JS reader sees). The captured command
text must be **verbatim identical** after edge-whitespace normalisation (a code fence and a
``<div>`` delimit differently; internal whitespace of a multi-line ``curl`` is significant and
is compared). ``--check`` fails on any disagreement and names every surface with its file and
line; the default mode rewrites the mirrors from the source, so the source is the only writer.

The tool count is a count, so it goes through ``Site``/``stale_entries``/``sync_all`` with
``canonical_mcp_tools()`` as the source of truth: the homepage phrase is re-matched every run
(idempotent by construction) and a reworded phrase is a hard error, never a silent skip.

Deliberately NOT managed
------------------------
``npx @misaka-net/misakanet-setup@latest`` (a different invocation), the ``register`` curl on
the homepage (it has no README counterpart to pair with), ``docs/install/index.html`` and
``docs/quickstart.md`` (the issue's acceptance pairs the homepage against the README), and
``docs/locales/*.json`` — the i18n dictionaries are issue #1894's surface. The dictionaries
still carry the old "7 tools" in ``qsAVerify``/``qsB``; that is reported in the PR rather than
edited here, because touching them would collide with the i18n work.

Root ``llms.txt`` needs nothing from this module: it is already a pointer at ``docs/llms.txt``
and ``tests/test_lesson_count_ssot.py`` keeps it one (issue #1895's fourth bullet, closed by
that earlier work).

Usage
-----
    python3 scripts/sync_site_facts.py            # rewrite mirrors from their sources
    python3 scripts/sync_site_facts.py --check    # CI gate: exit 1 on drift
    python3 scripts/sync_site_facts.py --quiet
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sync_lesson_count import (  # noqa: E402
    Site,
    canonical_mcp_tools,
    stale_entries,
    sync_all,
)

REPO = Path(__file__).resolve().parent.parent

# The homepage's Quickstart self-check sentence. The count is *retyped* in the static bytes
# (crawlers and no-JS readers cannot run the JS that fetches data/lessons.json), which is exactly
# why it needs a writer rather than a human with good intentions.
TOOL_SITES: tuple[Site, ...] = (
    Site(
        "docs/index.html",
        r"misakanet with (?P<n>\d+) tools",
        "misakanet with {n} tools",
        "Quickstart Track A self-check ('claude mcp list shows misakanet with N tools')",
    ),
)


@dataclass(frozen=True)
class Surface:
    """One file's capture of one command.

    ``pattern`` must contain a named group ``cmd`` holding the command text as written in this
    file. It is anchored on the surrounding sentence, *not* on the command itself, so a
    one-character corruption still captures (and then fails the comparison naming both sides)
    instead of turning into a silent "pattern not found".
    """

    path: str
    pattern: str

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class CommandFact:
    """One command string stated on more than one surface.

    ``source`` is the surface the default mode copies from; ``mirrors`` are rewritten to match
    it. ``--check`` requires every capture (source included) to be verbatim equal.
    """

    name: str
    note: str
    source: Surface
    mirrors: tuple[Surface, ...]

    def surfaces(self) -> tuple[Surface, ...]:
        return (self.source, *self.mirrors)


# ── the three command facts ──────────────────────────────────────────────────────────────────────
# Each pair is "the same command" in the issue's sense: the homepage Quickstart step and the
# README sentence a reader meets first. Patterns are anchored on the surrounding prose so that
# a corrupted command is still captured and compared, not missed.
COMMAND_FACTS: tuple[CommandFact, ...] = (
    CommandFact(
        name="install-command",
        note="the Quickstart install command must be the README installer row's command",
        source=Surface(
            "README.md",
            r"my assistant to search the lessons\s*\|\s*`(?P<cmd>[^`]+)`",
        ),
        mirrors=(
            Surface(
                "docs/index.html",
                r"Install the endpoint into every assistant[^<]*</div>\s*"
                r'<div class="qs-cmd">(?P<cmd>[^<]+)</div>',
            ),
        ),
    ),
    CommandFact(
        name="install-verify-command",
        note="the Quickstart verify command must be the README verify sentence's command",
        source=Surface(
            "README.md",
            r"Verify an install with `(?P<cmd>[^`]+)`",
        ),
        mirrors=(
            Surface(
                "docs/index.html",
                r"Close and reopen your assistant[^<]*</div>\s*"
                r'<div class="qs-cmd">(?P<cmd>[^<]+)</div>',
            ),
        ),
    ),
    CommandFact(
        name="search-curl-command",
        note="the Quickstart MCP search curl must be the README first-five-minutes curl",
        source=Surface(
            "README.md",
            r"```bash\n(?P<cmd>curl -sS https://misakanet\.org/mcp.*?misakanet_search.*?)\n?```",
        ),
        mirrors=(
            Surface(
                "docs/index.html",
                r'<div class="qs-cmd">(?P<cmd>curl -sS https://misakanet\.org/mcp.*?'
                r"misakanet_search.*?)</div>",
            ),
        ),
    ),
)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


@dataclass
class _Capture:
    surface: Surface
    text: str
    match: re.Match[str]

    @property
    def command(self) -> str:
        return self.match.group("cmd")

    @property
    def line(self) -> int:
        return _line_of(self.text, self.match.start("cmd"))

    def normalised(self) -> str:
        """Edge whitespace is not part of the command: a code fence and a <div> delimit differently.

        Internal whitespace is — the multi-line ``curl``'s line breaks and indentation are the
        command a reader copies.
        """
        return self.command.strip()


def _capture(root: Path, surface: Surface) -> _Capture | str:
    """One surface's capture of a command, or the error explaining why there is none."""
    path = root / surface.path
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"{surface.path}: unreadable ({exc})"
    match = surface.compiled().search(text)
    if not match:
        return (
            f"{surface.path}: pattern {surface.pattern!r} matched 0× — the sentence was "
            f"reworded: fix the file or update COMMAND_FACTS"
        )
    return _Capture(surface, text, match)


def stale_command_entries(*, root: Path = REPO,
                          facts: tuple[CommandFact, ...] = COMMAND_FACTS) -> list[str]:
    """Every command-string disagreement; empty list == healthy.

    A disagreement names **both** (all) files with their lines and their captured text — the
    reader needs to see the two spellings side by side, not only which one "won".
    """
    errors: list[str] = []
    for fact in facts:
        captures: list[_Capture] = []
        for surface in fact.surfaces():
            got = _capture(root, surface)
            if isinstance(got, str):
                errors.append(f"{fact.name}: {got} — {fact.note}")
            else:
                captures.append(got)
        if len(captures) < 2:
            continue
        spellings: dict[str, list[_Capture]] = {}
        for capture in captures:
            spellings.setdefault(capture.normalised(), []).append(capture)
        if len(spellings) == 1:
            continue
        lines = [
            f"  - {c.surface.path}:{c.line}: {c.command!r}"
            for c in captures
        ]
        errors.append(
            f"{fact.name}: the same command is spelled {len(spellings)} different ways — "
            f"{fact.note}:\n" + "\n".join(lines)
            + "\n  (compared verbatim after edge-whitespace stripping)"
        )
    return errors


def sync_command_facts(*, root: Path = REPO,
                       facts: tuple[CommandFact, ...] = COMMAND_FACTS,
                       dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Rewrite every mirror from its source. Returns (changes, errors).

    The source is never rewritten: one writer means the README is the origin and the homepage
    is a copy this script makes, not a second place a human retypes the command.
    """
    changes: list[str] = []
    errors: list[str] = []
    for fact in facts:
        source = _capture(root, fact.source)
        if isinstance(source, str):
            errors.append(f"{fact.name}: {source} — cannot rewrite mirrors without a source")
            continue
        canonical = source.command
        for surface in fact.mirrors:
            mirror = _capture(root, surface)
            if isinstance(mirror, str):
                errors.append(f"{fact.name}: {mirror} — {fact.note}")
                continue
            if mirror.normalised() == canonical.strip():
                continue

            def repl(match: re.Match[str], _new: str = canonical) -> str:
                return (
                    match.group(0)[: match.start("cmd") - match.start()]
                    + _new
                    + match.group(0)[match.end("cmd") - match.start():]
                )

            updated = surface.compiled().sub(repl, mirror.text)
            if not dry_run:
                (root / surface.path).write_text(updated, encoding="utf-8")
            changes.append(
                f"{surface.path}:{mirror.line}: {mirror.command!r} → {canonical!r}"
            )
    return changes, errors


def stale_tool_count_entries(*, root: Path = REPO) -> list[str]:
    """The homepage's tool count against `canonical_mcp_tools()`, through the count machinery."""
    try:
        count = canonical_mcp_tools(root)
    except ValueError as exc:
        return [f"tool count unavailable: {exc}"]
    return stale_entries(count, root=root, sites=TOOL_SITES, check_count_file=False)


def sync_tool_count(*, root: Path = REPO, dry_run: bool = False) -> tuple[list[str], list[str]]:
    count = canonical_mcp_tools(root)
    return sync_all(count, root=root, sites=TOOL_SITES, dry_run=dry_run, write_count_file=False)


def stale_entries_all(*, root: Path = REPO) -> list[str]:
    return stale_command_entries(root=root) + stale_tool_count_entries(root=root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync homepage Quickstart command strings and the tool count with their "
                    "sources of truth (idempotent).")
    parser.add_argument("--check", action="store_true",
                        help="verify only; exit 1 on drift")
    parser.add_argument("--quiet", action="store_true", help="silent on success")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.check:
        problems = stale_entries_all(root=args.root)
        if problems:
            print("❌ site-fact SSOT drift:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            print("\nFix: python3 scripts/sync_site_facts.py   "
                  "(or update COMMAND_FACTS/TOOL_SITES if a sentence was intentionally "
                  "reworded)", file=sys.stderr)
            return 1
        if not args.quiet:
            print("✅ every managed homepage command and the tool count match their sources")
        return 0

    changes: list[str] = []
    errors: list[str] = []
    cmd_changes, cmd_errors = sync_command_facts(root=args.root)
    tool_changes, tool_errors = sync_tool_count(root=args.root)
    changes.extend(cmd_changes)
    changes.extend(tool_changes)
    errors.extend(cmd_errors)
    errors.extend(tool_errors)
    if changes:
        print("✅ site facts synced:")
        for change in changes:
            print(f"  - {change}")
    elif not args.quiet:
        print("✅ already consistent: every managed homepage command and the tool count "
              "match their sources")
    if errors:
        print("❌ some managed site facts could not be refreshed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
