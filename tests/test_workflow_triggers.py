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

import yaml

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


# GitHub's activity types for `workflow_run`. `completed` is what most consumers want; `requested` fires
# when a run is *created*, which is the only moment at which a run can be reported as waiting for approval.
VALID_WORKFLOW_RUN_TYPES = ("completed", "in_progress", "requested")


def workflow_run_blocks(path: Path) -> list[dict]:
    """The `workflow_run` trigger(s) in one workflow file, as parsed YAML.

    Parsed rather than string-matched, and that is the point of this version (2026-09-29): the rule below
    used to accept only the literal spellings `types: [completed]` or a `types:` block, so
    `types: [requested]` — valid YAML, valid GitHub, and the only type that can see a run enter the
    approval queue — was reported as a *missing* declaration. That is the "assert on the wording instead of
    the mechanism" failure this repository has a lesson about; the intent here is "name your activity types
    explicitly", and the spelling is not the mechanism.
    """
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        return []
    triggers = spec.get("on") or spec.get(True) or {}
    if not isinstance(triggers, dict):
        return []
    block = triggers.get("workflow_run")
    if block is None:
        return []
    return block if isinstance(block, list) else [block]


def activity_type_problems(path: Path) -> list[str]:
    """Problems with one file's `workflow_run` activity types — empty when the file is fine.

    A function rather than an inline assertion so the rule's own failure mode can be driven from a fixture.
    """
    problems: list[str] = []
    for block in workflow_run_blocks(path):
        types = block.get("types") if isinstance(block, dict) else None
        if not types:
            problems.append(
                f"{path.name}: a workflow_run trigger with no `types` fires on every activity type")
            continue
        unknown = sorted(set(types) - set(VALID_WORKFLOW_RUN_TYPES))
        if unknown:
            problems.append(f"{path.name}: {unknown} is not a workflow_run activity type "
                            f"(valid: {list(VALID_WORKFLOW_RUN_TYPES)})")
    return problems


def test_workflow_run_consumers_still_declare_a_valid_trigger_type():
    """A `workflow_run` without `types` fires on every activity type; each consumer must name its own."""
    problems = [problem for path in _workflow_run_files() for problem in activity_type_problems(path)]
    assert not problems, "\n  - ".join(["workflow_run triggers must declare valid activity types:"] + problems)


def test_the_activity_type_rule_notices_a_missing_or_invalid_types_list(tmp_path):
    """Guard the guard: the rule reads the real repository, so its failure modes need fixtures."""
    def write(name: str, trigger: str) -> Path:
        path = tmp_path / name
        path.write_text("name: Fixture\non:\n" + trigger + "\njobs: {}\n", encoding="utf-8")
        return path

    fine = write("fine.yml", "  workflow_run:\n    workflows: [\"A\"]\n    types: [requested]\n")
    assert activity_type_problems(fine) == [], "an inline list is a declaration like any other"

    block_form = write("block.yml", "  workflow_run:\n    workflows: [\"A\"]\n    types:\n      - completed\n")
    assert activity_type_problems(block_form) == [], "the block form must keep working"

    missing = write("missing.yml", "  workflow_run:\n    workflows: [\"A\"]\n")
    assert activity_type_problems(missing) == [
        "missing.yml: a workflow_run trigger with no `types` fires on every activity type"], (
        "a trigger that fires on every activity type must be reported")

    bogus = write("bogus.yml", "  workflow_run:\n    workflows: [\"A\"]\n    types: [finished]\n")
    assert any("not a workflow_run activity type" in problem for problem in activity_type_problems(bogus)), (
        "an activity type GitHub does not have must be reported")

    plain = write("plain.yml", "  push:\n    branches: [main]\n")
    assert activity_type_problems(plain) == [], "a workflow with no workflow_run trigger is not this rule's business"


# ── a `workflow_run` that names a workflow which does not exist fires never ─────────────────────────
# Found by an architecture review, 2026-09-29: `update-badges.yml` listened for
# `workflows: ["Lesson Quality Gate", "Update Lessons"]`, and no workflow is named "Update Lessons" —
# the file is `update-lessons.yml` and its `name:` is "Update lessons.json". GitHub matches on the name,
# so that half of the trigger could never fire and the badges refreshed only on the weekly cron, with no
# error anywhere. A trigger that cannot fire is invisible in exactly the way a check that cannot fail is.
def declared_workflow_names(root: Path | None = None) -> set[str]:
    """Every `name:` a workflow file declares (the string `workflow_run.workflows` is matched against)."""
    directory = (root or WORKFLOWS)
    names = set()
    for path in sorted(directory.glob("*.y*ml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(spec, dict) and spec.get("name"):
            names.add(str(spec["name"]))
    return names


def unknown_watched_workflows(root: Path | None = None) -> list[str]:
    """`file: name` for every `workflow_run.workflows` entry that no workflow declares."""
    directory = (root or WORKFLOWS)
    known = declared_workflow_names(directory)
    problems = []
    for path in sorted(directory.glob("*.y*ml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            continue
        triggers = spec.get("on") or spec.get(True) or {}
        block = triggers.get("workflow_run") if isinstance(triggers, dict) else None
        for entry in ([block] if isinstance(block, dict) else (block or [])):
            for name in (entry or {}).get("workflows") or []:
                if name != "*" and name not in known:
                    problems.append(f"{path.name}: {name}")
    return problems


def test_every_workflow_run_trigger_names_a_workflow_that_exists():
    problems = unknown_watched_workflows()
    assert not problems, (
        "these `workflow_run` triggers name a workflow no file declares, so they can never fire — GitHub "
        "matches on `name:`, and a typo here is silent (the fix is to correct the name or drop the "
        "trigger deliberately):\n  - " + "\n  - ".join(problems))


def test_the_name_rule_notices_a_typo(tmp_path):
    """Guard the guard: the rule reads the real repository, so its failure mode needs a fixture."""
    (tmp_path / "real.yml").write_text(
        "name: Update lessons.json\non: [push]\njobs: {}\n", encoding="utf-8")
    (tmp_path / "watcher.yml").write_text(
        "name: Watcher\non:\n  workflow_run:\n    workflows: [\"Update Lessons\"]\n    types: [completed]\n"
        "jobs: {}\n", encoding="utf-8")
    assert declared_workflow_names(tmp_path) == {"Update lessons.json", "Watcher"}, declared_workflow_names(tmp_path)
    problems = unknown_watched_workflows(tmp_path)
    assert problems == ["watcher.yml: Update Lessons"], problems

    # …and the wildcard escape hatch this repository documents is not flagged.
    (tmp_path / "watcher.yml").write_text(
        "name: Watcher\non:\n  workflow_run:\n    workflows: [\"*\"]\n    types: [completed]\n"
        "jobs: {}\n", encoding="utf-8")
    assert unknown_watched_workflows(tmp_path) == [], "the documented wildcard is not a typo"
