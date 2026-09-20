#!/usr/bin/env python3
"""A bare `paths:` filter does not exclude tag pushes.

GitHub only compares `branches`/`tags` selectors against the pushed ref. A workflow that declares
`on: push: paths: [...]` and no branch or tag selector therefore runs for **every** tag push — the
`paths` list is never consulted, because a tag is not a path-bearing branch ref.

This was invisible for as long as every tag in this repository was created by release-please with
`GITHUB_TOKEN`, and a `GITHUB_TOKEN` push does not trigger workflows at all. The first tag pushed by
a human or a PAT — the intake bot's `v1`, see action.yml — fired three branch-CI workflows against a
commit main had already tested (runs 35510965110/…113/…131). The fix is a selector: `branches: ['**']`
keeps "any branch" behaviour exactly and drops tags; `tags: [...]` makes a workflow tag-only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow triggers")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.y*ml"))
SELECTORS = ("branches", "branches-ignore", "tags", "tags-ignore")


def _triggers(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # `on` is the boolean True key under YAML 1.1; read it either way.
    on = data.get("on") or data.get(True) or {}
    if isinstance(on, str):
        return {on: None}
    return on if isinstance(on, dict) else {}


def test_every_push_trigger_says_which_refs_it_wants():
    offenders = []
    for path in WORKFLOWS:
        push = _triggers(path).get("push")
        if push is None:
            continue
        # `push:` with no filters at all runs on every push, tags included — same defect.
        if not isinstance(push, dict) or not push:
            offenders.append(f"{path.name}: `push:` with no filters")
            continue
        if not any(sel in push for sel in SELECTORS):
            offenders.append(
                f"{path.name}: push filters {sorted(push)} — no branch/tag selector, so tag pushes "
                f"run this workflow too"
            )
    assert not offenders, (
        "these push triggers also fire on tag pushes; add `branches: ['**']` (any branch, no tags) "
        "or a release-shaped `tags:` list:\n  " + "\n  ".join(offenders)
    )


def test_the_gate_sees_a_real_number_of_workflows():
    # Guard the guard: a broken glob would make the assertion above vacuous.
    assert len(WORKFLOWS) > 50, f"expected the repository's workflows, found {len(WORKFLOWS)}"
    assert any(_triggers(p).get("push") for p in WORKFLOWS), (
        "no workflow declares a push trigger — the check above proved nothing"
    )


def test_the_branch_selector_used_by_branch_ci_keeps_every_branch():
    """`branches: ['**']` is the deliberate spelling of "any branch" — not a narrowed list."""
    for name in ("fatal-guard.yml", "intake-benchmark.yml", "lesson-security.yml"):
        push = _triggers(REPO / ".github" / "workflows" / name).get("push")
        assert push and push.get("branches") == ["**"], (
            f"{name} is branch CI: it must run for every branch and for no tag"
        )
        assert "paths" in push, "the path filter is the point of these workflows; keep it"
