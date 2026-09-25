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


# ── the `# vN` comment is the half a human reads, so it has to be true ───────────────────────────
#
# The pin exists so a re-pointed tag cannot silently change what runs; the comment exists so a person can
# see which release is actually pinned without looking the SHA up. Measured 2026-09-26 while adding a
# workflow: one SHA (`actions/upload-artifact@043fb46d…`, which upstream tags `v7.0.1`) was written as
# `# v4` in the new file and `# v7` in the four older ones — a one-word difference that tells a reviewer
# an older major is in use. Nothing checked the comment, because the test above stops at the SHA.
PIN_WITH_COMMENT = re.compile(r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([0-9a-f]{40})\s*#\s*v?(\d+)", re.M)


def pin_comment_conflicts(workflows: dict[str, str]) -> list[str]:
    """Every use of the same `owner/repo@sha` must name the same major version in its comment."""
    seen: dict[tuple[str, str], dict[str, list[str]]] = {}
    for name, text in workflows.items():
        for target, sha, major in PIN_WITH_COMMENT.findall(text):
            seen.setdefault((target, sha), {}).setdefault(f"v{major}", []).append(name)
    problems = []
    for (target, sha), majors in sorted(seen.items()):
        if len(majors) > 1:
            detail = "; ".join(f"{m} in {', '.join(sorted(set(files)))}" for m, files in sorted(majors.items()))
            problems.append(
                f"{target}@{sha[:12]} is annotated with {len(majors)} different versions — {detail}. "
                f"The comment is what a human reads instead of resolving the SHA")
    return problems


def test_the_same_pin_is_not_annotated_with_two_different_versions():
    problems = pin_comment_conflicts({p.name: p.read_text(encoding="utf-8") for p in WORKFLOWS})
    assert not problems, "\n  - " + "\n  - ".join(problems)


def test_the_pin_comment_rule_can_go_red():
    """Replayed on the mistake that prompted it: one SHA, two version comments."""
    sha = "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    fixture = {
        "new.yml": f"      - uses: actions/upload-artifact@{sha}  # v4\n",
        "old.yml": f"      - uses: actions/upload-artifact@{sha}  # v7\n",
    }
    assert pin_comment_conflicts(fixture), "one SHA with two versions must be caught"
    # …and consistent comments, or a differently-pinned SHA, must not be.
    fixture["new.yml"] = f"      - uses: actions/upload-artifact@{sha}  # v7.0.1\n"
    assert pin_comment_conflicts(fixture) == [], "v7 and v7.0.1 name the same release line"

