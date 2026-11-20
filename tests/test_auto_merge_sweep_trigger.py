#!/usr/bin/env python3
"""The sweep must wake on the gates it waits for, and must not wake on itself.

Two failure modes, both silent, both cheap to pin here:

* **a renamed workflow**. `workflow_run.workflows` matches by the `name:` of the other workflow, so
  renaming "Lesson Quality Gate" stops the wake-up with no error anywhere — the sweep just runs less.
  The schedule below it is still a backstop, which makes the defect *slower*, not *broken*, and
  therefore even easier to never notice.
* **an `if:` that filters out an event it was not meant to**. Measured 2026-11-20 on
  `Auto-Merge Lessons`: its job-level guard read `github.event.pull_request.labels`, which
  `workflow_dispatch` does not have, so every dispatched run was skipped before doing anything —
  green, zero steps (#5430). The same mistake here would silently disable the schedule.

So this file asserts the *list against the repository* and the *guard against the triggers*, without
running any workflow.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
SWEEP = WORKFLOWS / "auto-merge-sweep.yml"


def sweep() -> tuple[dict, dict]:
    document = yaml.safe_load(SWEEP.read_text(encoding="utf-8"))
    # PyYAML reads the bare `on:` key as the boolean `True` (YAML 1.1), which is why every reader in
    # this repository spells it this way.
    triggers = document.get(True) or document.get("on")
    return document, triggers


def declared_names() -> dict[str, Path]:
    names: dict[str, Path] = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and isinstance(document.get("name"), str):
            names[document["name"]] = path
    return names


def test_every_workflow_the_sweep_waits_for_still_exists():
    _, triggers = sweep()
    listed = triggers["workflow_run"]["workflows"]
    names = declared_names()
    missing = [name for name in listed if name not in names]
    assert not missing, f"workflow_run.workflows names nothing that exists: {missing}"


def test_the_sweep_does_not_wake_itself():
    """A workflow that triggers on its own completion is the 2026-10-02 fan-out, one indirection later."""
    document, triggers = sweep()
    own_name = document["name"]
    assert own_name not in triggers["workflow_run"]["workflows"]


def test_the_list_covers_the_required_checks():
    """The five gates `scripts/lesson_pr_mergeable.py` requires are the ones worth waking for.

    A new required check without a line here means a PR can go green without waking the sweep — the
    exact gap the trigger exists to close, reintroduced one check at a time.
    """
    sys_path = REPO / "scripts"
    import sys
    sys.path.insert(0, str(sys_path))
    import lesson_pr_mergeable as lpm  # noqa: E402

    _, triggers = sweep()
    listed = set(triggers["workflow_run"]["workflows"])
    # check name → the workflow that produces it (from `grep -l 'name: <check>' .github/workflows/`)
    producers = {
        "gate": "Lesson Quality Gate",
        "provenance": "Provenance Gate",
        "dco": "DCO Check",
        "audit-shape": "PR Shape Guard",
    }
    for check in lpm.REQUIRED_CHECKS:
        assert producers[check] in listed, f"required check {check!r} has no workflow in the wake-up list"
    assert lpm.REQUIRED_CHECK_PREFIXES == ("test (",)
    assert "Cross-Platform Tests" in listed, "the matrix legs come from Cross-Platform Tests"


def test_the_guard_leaves_every_other_trigger_alone():
    """A `workflow_run` filter must not swallow the schedule or a manual dispatch."""
    document, triggers = sweep()
    guard = document["jobs"]["sweep"]["if"]
    for event in ("schedule", "workflow_dispatch"):
        assert event in triggers, f"{event} is no longer a trigger"
    # The guard has to be false-able only for the workflow_run case; anything else is a regression.
    assert guard.startswith("github.event_name != 'workflow_run'"), guard
    assert "workflow_run.event == 'pull_request'" in guard, guard


def test_a_push_to_main_does_not_wake_it():
    """Only PR-initiated runs are questions about a pull request; the rest are answered by the schedule."""
    document, _ = sweep()
    guard = document["jobs"]["sweep"]["if"]
    assert "pull_request" in guard
    assert "== 'push'" not in guard
