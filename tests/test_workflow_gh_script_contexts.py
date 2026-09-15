#!/usr/bin/env python3
"""No `github-script` body may read the event off the ``github`` object — 2026-09-15.

``actions/github-script`` hands the script body the ``@actions/github`` module: ``context``,
``getOctokit`` and ``GitHub``. It has no ``event`` property, so ``github.event.…`` throws
``Cannot read properties of undefined (reading '…')`` — which is exactly how
``.github/workflows/pr-thank-you.yml`` failed on *every* merged PR for weeks: the workflow
went red and never posted the comment it exists for (issue #1685, found while merging PR
#1684 and watching an unrelated check fail).

A step's ``if:``, ``env:`` and ``with:`` values are workflow *expressions* — a different
language, in which the event payload **is** spelled that way and is correct. So this test
looks only inside ``script: |`` bodies, which is where the two get confused.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))

# Written as a variable so this file's own prose stays readable; the check is a substring
# search, not a regular expression, because the bug is a plain property access.
FORBIDDEN = "github" + "." + "event"


def _script_bodies(text: str) -> list[tuple[int, str]]:
    """Every ``script: |`` block, as (first line number, body).

    Indentation defines the block: a `script: |` line opens it, and the first following line
    that is not indented deeper closes it. No YAML parser, for the same reason
    tests/test_workflow_pins.py does not use one — the workflows are read as text, and a
    parser would hide the line numbers this test reports.
    """
    bodies: list[tuple[int, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index]
        indent = len(stripped) - len(stripped.lstrip(" "))
        if stripped.strip().startswith("script: |"):
            body: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                line = lines[cursor]
                if line.strip() and (len(line) - len(line.lstrip(" "))) <= indent:
                    break
                body.append(line)
                cursor += 1
            bodies.append((index + 1, "\n".join(body)))
            index = cursor
            continue
        index += 1
    return bodies


def _code_without_expressions_and_comments(body: str) -> str:
    """Body text with ``${{ … }}`` interpolations and ``//`` comments removed.

    Both are legitimate places for the event payload to appear: a ``${{ … }}`` inside a script
    is a workflow *expression* evaluated before the script runs (`manual-audit.yml` reads
    `inputs.pr_number` that way), and a comment explaining the bug is documentation, not code.
    What must never survive is an actual property access — which is what the remaining texts
    are searched for.
    """
    without_expressions = re.sub(r"\$\{\{.*?\}\}", "", body, flags=re.DOTALL)
    return "\n".join(
        line for line in without_expressions.splitlines()
        if not line.strip().startswith("//")
    )


def test_no_script_body_reads_the_event_off_the_github_module():
    offenders = []
    checked = 0
    for path in WORKFLOWS:
        for first_line, body in _script_bodies(path.read_text(encoding="utf-8")):
            checked += 1
            code = _code_without_expressions_and_comments(body)
            if FORBIDDEN in code:
                for offset, line in enumerate(body.splitlines()):
                    if FORBIDDEN in _code_without_expressions_and_comments(line):
                        offenders.append(f"{path.name}:{first_line + offset}: {line.strip()[:100]}")

    assert checked > 0, "no github-script bodies were scanned — the extractor stopped matching"
    assert offenders == [], (
        "these script bodies read the event payload off the github module, which has no such "
        "property (use context.payload / context.eventName instead — a script is not a "
        "workflow expression):\n  - " + "\n  - ".join(offenders)
    )


def test_the_extractor_finds_the_block_it_is_named_after():
    """A guard on the guard: the indentation walk must end where the block ends."""
    sample = (
        "      - uses: actions/github-script@abc\n"
        "        with:\n"
        "          script: |\n"
        "            const a = 1;\n"
        "            const b = 2;\n"
        "      - name: next step\n"
        "        run: echo hi\n"
    )
    bodies = _script_bodies(sample)
    assert len(bodies) == 1, bodies
    _, body = bodies[0]
    assert "const a = 1;" in body and "const b = 2;" in body
    assert "next step" not in body, "the block must stop at the step that follows it"
