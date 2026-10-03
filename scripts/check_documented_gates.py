#!/usr/bin/env python3
"""Does the gate table in `docs/ci-gates.md` still match the ruleset that actually enforces?

`main` is protected by ruleset 23826057, *"main: the deterministic gates"*. `docs/ci-gates.md`
documents that set as a table, and the same file carries the `curl` that reads the ruleset back.
**The command was documented; nothing ever ran it.** So the one fact the whole document is built
on could change silently, and a reader would carry a stale list of the checks that block a merge.

The failure mode is not hypothetical. This repository spent a session removing the hand-written
counts of "the required checks" out of its prose, and the surviving one sat in the very file it
had nominated as the single statement of the set — twenty-two such lines, across seventeen files. A grep for numbers in prose does
not fix that: it is a heuristic over every file, it goes on finding new shapes to miss, and it
makes two thousand documents into a place CI can fail. This script instead checks the one thing
that is actually true or false — *the live set, against the documented set* — and lets the
document carry no count at all. The count is then a property of the table, not a sentence
somewhere that has to be remembered.

Run it directly, or let `.github/workflows/check-documented-gates.yml` run it weekly. The
schedule follows `gate-mutation-audit.yml`: this is a question about the ruleset, and the
ruleset changes on a timescale of months, not commits, so paying for it on every PR would
re-answer yesterday's answer slowly.

**Streams and exit codes are a contract, not an implementation detail.** stdout carries a verdict
and its first line is always `OK:` or `FAIL:`; stderr carries every reason the comparison could not
be made. Exit `1` is the *only* way to say "the document has drifted" — an expired token, a 404 and
a crash of this script all exit non-1, because a ratchet that reports "your document is wrong" when
it never got to read the ruleset is worse than one that stays silent.
"""
from __future__ import annotations

import argparse
import json
import os
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

# The first line of stdout always states the verdict, and the workflow keys its whole branch
# structure off it. Anything that is not one of these two prefixes means the comparison never
# produced a verdict — a crash, a bad interpreter, a missing file — and must be treated as *unknown*
# rather than as drift, or the ratchet opens an issue telling a maintainer to fix a correct document.
OK_PREFIX = "OK:"
FAIL_PREFIX = "FAIL:"

# Exit codes, and the contract the workflow relies on:
#   0 — the two sets agree
#   1 — they differ; the diff is on stdout
#   2 — the comparison could not be made (no token, no network, an unreadable ruleset)
#   3 — this script itself broke
# Only `report()` may return 1. Everything else means "no verdict", which is a different thing and is
# the case that used to be reported as a confident, wrong issue.
EXIT_AGREE = 0
EXIT_DIVERGED = 1
EXIT_CANNOT_CHECK = 2
EXIT_BROKEN = 3


class GateDocumentUnreadable(Exception):
    """The document does not contain the section this script reads. Not a verdict.

    Raised rather than returned, and deliberately **not** a `SystemExit`. `SystemExit("message")`
    exits **1** in CPython — 1 being this script's own "the document has drifted" — so the first
    version of this function reported a renamed heading as drift with an empty diff on stdout, and
    the workflow opened an issue about a document that was fine. An ordinary exception cannot be
    mistaken for a verdict, and `main` turns it into `EXIT_CANNOT_CHECK`.
    """


def parse_documented(path: Path) -> list[str]:
    """The contexts `docs/ci-gates.md` claims block a merge, in document order.

    Returns them with the table's decoration removed, so a cell written `**gate**` and a cell
    written `` `gate` `` compare equal. Only rows in the Hard Gates section are read.

    The heading is matched as a **whole line**, and it must appear exactly once. A substring
    search finds the first occurrence anywhere in the file, and the most natural edit to a
    document whose subject is now "this table is parsed by a ratchet" is to add a fenced example
    of the table format to the preamble — which the substring search would read as the section,
    parse the example's placeholder cells as contexts, and then open an issue claiming all four
    gates are missing when all four are present. Requiring exactly one occurrence turns that, a
    duplicated heading, and a rename into `EXIT_CANNOT_CHECK` instead: loud, and never a verdict
    about the ruleset.
    """
    text = path.read_text(encoding="utf-8")
    starts = [index for index, line in enumerate(text.splitlines()) if line.rstrip() == SECTION]
    if not starts:
        raise GateDocumentUnreadable(f"{SECTION!r} is not a heading line in {path}")
    if len(starts) > 1:
        raise GateDocumentUnreadable(
            f"{SECTION!r} appears as a heading {len(starts)} times in {path} "
            f"(lines {[n + 1 for n in starts]}); which table is authoritative?"
        )
    # Scan *after* the heading line. The loop below stops at the next `## `, which — left
    # unskipped — is the line it just started on.
    body = text.splitlines()[starts[0] + 1:]
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
        context = undecorate(cells[0])
        if context:
            contexts.append(context)
    return contexts


def undecorate(cell: str) -> str:
    """Strip a table cell's decoration, on both sides of the comparison.

    Applied to the document *and* to the ruleset context. Doing it only on the document side meant
    a live context ending in `_` — markdown's emphasis marker — could never be written down, so
    the comparison failed permanently and unfixably. Neither side is allowed to carry decoration
    into the comparison.
    """
    return cell.strip().strip("*`_ ").strip()


def contexts_from_ruleset(payload: dict) -> list[str]:
    """The contexts the ruleset requires, from a decoded API response.

    Note this returns `[]` for a response that names no required checks — and that is **not** the
    same as "the ruleset requires nothing". A 404 body, a token without the scope, or a ruleset whose
    `required_status_checks` key is absent all decode successfully and all land here, so the caller
    has to treat an empty result as *unreadable*, not as an answer. Getting that backwards is what
    made a ratchet tell a maintainer to delete four correct rows because a token had expired.
    """
    found: list[str] = []
    for rule in payload.get("rules", []):
        if rule.get("type") != "required_status_checks":
            continue
        for entry in rule.get("parameters", {}).get("required_status_checks", []):
            context = entry.get("context")
            if context:
                found.append(undecorate(context))
    return found


def ruleset_is_enforcing(payload: dict) -> list[str]:
    """What is wrong with a ruleset that is readable but not *enforcing*.

    A set comparison only asks *which* checks the ruleset names. It cannot tell the difference
    between a ruleset that blocks a merge and one that is decorative — and this document is titled
    *Hard Gates (must pass)*. A disabled ruleset, one aimed at something other than branches, or
    one that exempts actors all pass a set comparison and mean something completely different, so
    they are read here and said out loud rather than reported as a silent match.

    `docs/ci-gates.md` states all three values, so all three are worth checking; the bypass list is
    included because "nobody can bypass this, including the owner" is a claim a reader relies on.
    """
    problems: list[str] = []
    if payload.get("enforcement") != "active":
        problems.append(f"enforcement is {payload.get('enforcement')!r}, not 'active'")
    if payload.get("target") not in (None, "branch"):
        problems.append(f"target is {payload.get('target')!r}, not 'branch'")
    bypass = payload.get("bypass_actors") or []
    if bypass:
        listed = ", ".join(str(actor.get("actor_id") or actor) for actor in bypass)
        problems.append(f"bypass_actors is not empty ({listed}) — some actors skip these gates")
    return problems


def cannot_check(reason: str) -> int:
    """Report that the comparison did not happen, on stderr, and return its exit code.

    stderr, always — the workflow reads **stdout** to decide whether the document has drifted, and a
    line that reached the wrong stream would be a verdict this run never made.
    """
    print(f"fail: {reason}", file=sys.stderr)
    return EXIT_CANNOT_CHECK


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
    """Print what diverged. Returns `EXIT_AGREE` or `EXIT_DIVERGED` — the only two verdicts."""
    missing = [context for context in live if context not in documented]
    invented = [context for context in documented if context not in live]

    if not missing and not invented:
        if not quiet:
            print(f"{OK_PREFIX} the documented gates match ruleset {RULESET_ID} ({len(live)} contexts)")
        return EXIT_AGREE

    print(f"{FAIL_PREFIX} the gate table in docs/ci-gates.md no longer matches ruleset {RULESET_ID}.",
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
    return EXIT_DIVERGED


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

    try:
        documented = parse_documented(args.doc)
    except GateDocumentUnreadable as error:
        # The adjacent case, `if not documented`, already routed to `cannot_check`; this one did
        # not, and it exited 1 — the drift code — with an empty stdout. Two halves of one mistake.
        return cannot_check(
            f"{error}. That is not a statement about the ruleset: the document's gate table "
            "cannot be read, so nothing can be compared. Check the heading and the table before "
            "concluding that the gates moved."
        )
    except OSError as error:
        return cannot_check(f"could not read {args.doc}: {error}")

    if args.from_file:
        try:
            payload = json.loads(args.from_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            return cannot_check(f"could not read the saved ruleset {args.from_file}: {error}")
    else:
        token = token_from_environment()
        if not token:
            return cannot_check(
                "no token. Set SHELDON_PAT, or pass --from-file with a saved ruleset response."
            )
        try:
            payload = fetch_live(token)
        except urllib.error.HTTPError as error:
            # 404 and 401 both arrive here, and both mean the *read* failed rather than that the
            # document is wrong: a token without the rulesets scope gets a 404, not a 403, so this
            # used to look exactly like "the ruleset requires nothing" and read as a divergence.
            detail = f"HTTP {error.code}"
            if error.code in (401, 403):
                detail += " — the token is not accepted, or lacks the rulesets scope"
            elif error.code == 404:
                detail += " — no such ruleset for this token, or the token cannot see it"
            return cannot_check(f"could not read ruleset {RULESET_ID}: {detail}")
        except urllib.error.URLError as error:
            return cannot_check(f"could not read ruleset {RULESET_ID}: {error.reason}")

    if not documented:
        return cannot_check("the Hard Gates table in the document yielded no rows.")

    live = contexts_from_ruleset(payload)
    if not live:
        return cannot_check(
            f"ruleset {RULESET_ID} returned no required status checks. That is not a statement "
            "about the document — either the ruleset is gone, or this token cannot read it. "
            "Check the ruleset by hand before changing docs/ci-gates.md."
        )

    not_enforcing = ruleset_is_enforcing(payload)
    if not_enforcing:
        return cannot_check(
            f"ruleset {RULESET_ID} names the same checks but is not enforcing them: "
            + "; ".join(not_enforcing)
            + ". The table in docs/ci-gates.md is accurate — what is not accurate is the word "
            "'must pass' in its own heading, and that is not a diff this script can render."
        )

    return report(documented, live, sys.stdout, quiet=args.quiet)


def run_cli(argv: list[str] | None = None) -> int:
    """`main()` plus the guard that keeps a crash from being read as a verdict.

    Two ways out of `main` used to land on the drift code by accident, and both are closed here
    rather than at the call site, so a future edit cannot reopen them:

    * an uncaught exception — a traceback exits 1, and 1 is this script's own "the document has
      drifted". A one-character typo would have opened a recurring, authoritative-looking issue
      about a document that was correct;
    * a `SystemExit` whose code is a **string** — CPython exits 1 for it. `argparse` raises
      `SystemExit(2)` for a bad argument and `SystemExit(0)` for `--help`, and those pass through
      untouched; anything non-integer is not a verdict and is not 1.

    The check is `isinstance(code, int)`, not `code == 0`, because `True` is an `int` and nobody
    should have to think about that.
    """
    try:
        return main(argv)
    except SystemExit as exit_request:
        code = exit_request.code
        # Only argparse's two codes pass through: 0 for `--help`, 2 for a bad argument. Everything
        # else — including a bare `1` — is a status this script never means to produce, and 1 is
        # its own "the document has drifted". Letting an integer 1 through re-created the exact
        # failure this guard exists to stop, one level down.
        if code in (0, 2) and isinstance(code, int) and not isinstance(code, bool):
            raise
        print(f"fail: the ratchet exited with an unexpected status: {code!r}", file=sys.stderr)
        return EXIT_BROKEN
    except BaseException as error:  # noqa: BLE001 - the point is to catch *everything*
        print(f"fail: the ratchet itself broke: {error!r}", file=sys.stderr)
        return EXIT_BROKEN


if __name__ == "__main__":
    sys.exit(run_cli())
