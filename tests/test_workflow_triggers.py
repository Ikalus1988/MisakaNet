#!/usr/bin/env python3
"""Workflow triggers that quietly multiply runs (2026-09-17).

`workflow_run: workflows: ["*"]` means "start me whenever *any* workflow in this repository
completes". With 68 workflows that turns one workflow into a run per completion of every other
one: `intake-bot-demo.yml` had **21,126 runs**, of which **98.1% were skipped** by its own
job-level `if` — the run is created before the condition is evaluated, so the filter saves
nothing. The Actions history becomes unreadable and the minutes are spent either way.

A wildcard is legitimate when the follow-up really does need to see everything, so this test is a
narrow rule about intent, not a blanket ban: name the workflows, or say in a comment next to the
wildcard why every completion matters.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# `workflows: ["*"]`, `workflows: '*'`, `workflows: ["*", "X"]` — the wildcard in any of the
# spellings YAML allows.
_WILDCARD = re.compile(r"^\s*workflows\s*:\s*(\[\s*['\"]\*['\"]\s*\]|['\"]\*['\"])\s*$", re.MULTILINE)


def _workflow_run_files() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.y*ml") if "workflow_run" in p.read_text(encoding="utf-8"))


def test_no_workflow_run_trigger_watches_every_workflow():
    offenders = []
    for path in _workflow_run_files():
        text = path.read_text(encoding="utf-8")
        for match in _WILDCARD.finditer(text):
            # An explicit justification immediately above is the documented escape hatch.
            before = text[: match.start()].rstrip().splitlines()
            justified = any("wildcard" in line.lower() or "every workflow" in line.lower()
                            for line in before[-4:])
            if not justified:
                offenders.append(path.name)
    assert not offenders, (
        "these workflows trigger on the completion of *every* other workflow, which multiplies "
        f"runs by the number of workflows: {offenders}. Name the workflows you actually need "
        "(see intake-bot-demo.yml), or justify the wildcard in a comment."
    )


def test_the_intake_bot_demo_names_its_trigger_source():
    """Pin the specific repair: it reacts to the CI workflow, not to all 68."""
    text = (WORKFLOWS / "intake-bot-demo.yml").read_text(encoding="utf-8")
    assert 'workflows: ["Cross-Platform Tests"]' in text, (
        "intake-bot-demo must name the workflow whose failures it reacts to; a wildcard here "
        "created 21,126 runs with 98.1% skipped (2026-09-17)"
    )


def test_workflow_run_consumers_still_declare_a_valid_trigger_type():
    """A `workflow_run` without `types` fires on every activity type; all of ours want completed."""
    for path in _workflow_run_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*workflow_run\s*:", text, re.MULTILINE):
            assert "types: [completed]" in text or "types:\n" in text, path.name
