#!/usr/bin/env python3
"""The claim window had two readers and they disagreed (issue #1826).

`claim-enforcer.yml` released a `/claim`ed issue when `ELAPSED < 4` hours — while the job's own name
("Enforce **8h** Claim Windows") and the notice it posts ("The **8-hour** exclusive /claim window has
expired") both said eight. The window was raised from 4h to 8h in June 2026
(`docs/ring0-founder-track.md`: "Global 8h window (increased from 4h in Jun 2026)"); the arithmetic was
the half that got left behind, so issues were released four hours early and told eight hours were up.

The fix is one variable with one reader per use — the comparison and the notice both interpolate
`CLAIM_WINDOW_HOURS` — so they cannot drift apart again. These tests pin the value to the document that
owns it, and pin both uses to the variable.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "claim-enforcer.yml"
DOC = REPO / "docs" / "ring0-founder-track.md"


def _run_block() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps") or []:
            if "ELAPSED" in (step.get("run") or ""):
                return step["run"]
    raise AssertionError("no step computes ELAPSED — the enforcer is gone or renamed")


def _declared_hours() -> int:
    match = re.search(r"(?m)^\s*CLAIM_WINDOW_HOURS=(\d+)\s*$", _run_block())
    assert match, "the window is not declared as CLAIM_WINDOW_HOURS in the run block"
    return int(match.group(1))


def _documented_hours() -> int:
    """The window as the documentation states it — the value that owns the number."""
    text = DOC.read_text(encoding="utf-8")
    match = re.search(r"Global (\d+)h window", text)
    assert match, "docs/ring0-founder-track.md no longer states the global claim window"
    return int(match.group(1))


def test_the_window_matches_the_documented_one():
    assert _declared_hours() == _documented_hours(), (
        f"the enforcer uses {_declared_hours()}h and docs/ring0-founder-track.md says "
        f"{_documented_hours()}h — one of them is stale, and the last time this drifted the workflow "
        "kept the old 4h after the document raised it to 8h (#1826)"
    )


def test_the_comparison_reads_the_variable_not_a_literal():
    run = _run_block()
    assert re.search(r'\[ "\$ELAPSED" -lt "\$CLAIM_WINDOW_HOURS" \]', run), (
        "the comparison is a literal again — that is how it survived the move from 4h to 8h"
    )
    assert not re.search(r'\[ "\$ELAPSED" -lt \d+ \]', run), run


def test_the_notice_interpolates_the_same_variable():
    """The message is the half a human reads; if it is a literal, it can disagree with the gate."""
    run = _run_block()
    assert "${CLAIM_WINDOW_HOURS}-hour" in run, run
    assert not re.search(r"The \d+-hour exclusive", run), (
        "the notice hard-codes a number again, so it can contradict the comparison"
    )


def test_the_notice_still_names_the_window_twice():
    """Once for 'has expired', once for 'to claim within' — both must come from the variable."""
    run = _run_block()
    assert run.count("${CLAIM_WINDOW_HOURS}") >= 2, run
