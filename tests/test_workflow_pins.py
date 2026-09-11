#!/usr/bin/env python3
"""Every `uses:` in .github/workflows must be pinned — 2026-09-12.

CodeQL's GITHUB_ACTION_UNPINNED was the single largest alert class in this repo
(120 of 166 open alerts). A mutable ref (`@v7`, `@release/v1`, `@main`) can be
re-pointed at any commit by the action's owner, so every workflow here was
running whatever that tag happened to point at — a supply-chain risk that no test
covered.

The pins are cheap to keep fresh: `.github/dependabot.yml` already tracks the
`github-actions` ecosystem weekly, and it was configured for exactly this
("We keep SHA pinning + manual review (never auto-merge)").

Allowed forms:

* ``owner/repo[/path]@<40-hex sha>``  — the pinned form, optionally with a ``# vX``
  comment so a human can see which release the SHA is;
* ``./path``                          — a local action in this repository;
* ``docker://image:tag``              — pinned by tag/digest semantics of the registry;
* an expression (``${{ … }}``)        — resolved at run time.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)")
PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
ALLOWED_PREFIXES = ("./", "docker://")


def test_every_action_reference_is_pinned():
    offenders = []
    for workflow in WORKFLOWS:
        for lineno, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            match = USES.match(line)
            if not match:
                continue
            target = match.group(1)
            if target.startswith(ALLOWED_PREFIXES) or PINNED.match(target):
                continue
            if "${{" in target:
                continue
            offenders.append(f"{workflow.name}:{lineno}: {target}")
    assert offenders == [], (
        "these action references can be re-pointed by their owner (pin the commit SHA, "
        "with a `# vX` comment for humans):\n  - " + "\n  - ".join(offenders)
    )


def test_workflows_directory_is_not_empty():
    """Guard the guard: a bad glob would make the test above vacuously pass."""
    assert len(WORKFLOWS) > 20, f"only found {len(WORKFLOWS)} workflow files"
