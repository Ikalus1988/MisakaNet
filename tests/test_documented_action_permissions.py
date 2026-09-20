#!/usr/bin/env python3
"""Every documented caller snippet must grant what the action actually calls.

The intake bot reads the failing job's log through the REST API
(`github.rest.actions.downloadJobLogsForWorkflowRun`), which requires `Actions: read`. A workflow
that declares `permissions:` at all sets every scope it leaves out to `none` — so the fetch 403s,
the step's `core.warning` swallows it, no error text is produced, and the bot reports
`No error input provided, skipping`: a green run that posted nothing. Same failure shape as #1825
(21,732 green runs, zero comments), different cause. It survived because the demo's *manual* trigger
always passes `error:` text explicitly, and the automatic path never does — and because every
documented snippet (README, docs/agents/external-usage.md, the demo workflow) omitted the scope.

So the requirement is derived from the action rather than listed here: a new REST namespace in
`action.yml` makes this test demand the corresponding scope from every snippet.

`actions: read` is required even of snippets that pass `error:` explicitly, because an empty error
input falls back to log extraction — the scope is not optional per-snippet, it is optional per-run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the action and the snippets")

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / "action.yml"

# Documented callers: files a stranger copies a workflow out of.
DOCS = (
    REPO / "README.md",
    REPO / "README.ja.md",
    REPO / "README.zh-CN.md",
    REPO / "docs" / "agents" / "external-usage.md",
)
DEMO = REPO / ".github" / "workflows" / "intake-bot-demo.yml"

# `github.rest.<namespace>.<method>` → the GITHUB_TOKEN scope that endpoint needs.
NAMESPACE_TO_SCOPE = {
    "actions": "actions",
    "issues": "issues",
    "pulls": "pull-requests",
    "checks": "checks",
    "repos": "contents",
}
READ_METHOD_PREFIXES = ("list", "get", "download", "check", "compare")


def _action() -> dict:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def required_permissions() -> dict[str, str]:
    """{scope: 'read'|'write'} derived from what action.yml's steps actually call."""
    need: dict[str, str] = {}
    for step in _action()["runs"]["steps"]:
        script = (step.get("with") or {}).get("script")
        if not script:
            continue
        for namespace, method in re.findall(r"github\.rest\.(\w+)\.(\w+)", script):
            scope = NAMESPACE_TO_SCOPE.get(namespace)
            if scope is None:
                continue
            level = "read" if method.startswith(READ_METHOD_PREFIXES) else "write"
            previous = need.get(scope)
            if previous is None:
                need[scope] = level
            elif level == "write":
                need[scope] = "write"
    return need


def _covers(granted: str, required: str) -> bool:
    return granted == "write" or granted == required


def _snippets() -> list[tuple[str, dict]]:
    """(where, permissions mapping) for each documented snippet that calls the action."""
    found: list[tuple[str, dict]] = []
    for path in DOCS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r"```ya?ml\n(.*?)```", text, re.S):
            if "Ikalus1988/MisakaNet@" not in block and "Ikalus1988/MisakaNet/.github" not in block:
                continue
            try:
                data = yaml.safe_load(block) or {}
            except yaml.YAMLError:  # a fragment (no `on:`) is not a caller snippet
                continue
            perms = data.get("permissions") if isinstance(data, dict) else None
            found.append((f"{path.relative_to(REPO)} snippet", perms if isinstance(perms, dict) else {}))
    workflow = yaml.safe_load(DEMO.read_text(encoding="utf-8")) or {}
    for job in (workflow.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            if isinstance(step, dict) and str(step.get("uses", "")).startswith("./"):
                found.append((f"{DEMO.name} job", job.get("permissions") or {}))
    return found


def test_the_requirement_is_derived_from_the_action_not_hardcoded():
    # Guard the guard: if the regex stopped matching, every assertion below would pass vacuously.
    need = required_permissions()
    assert need.get("actions") == "read", (
        "the action must still be seen to call the Actions API for job logs; otherwise the rest of "
        "this file proves nothing"
    )
    assert need.get("issues") == "write", "the comment path calls issues.createComment"


def test_every_documented_snippet_grants_the_required_scopes():
    need = required_permissions()
    problems = []
    for where, perms in _snippets():
        if not perms:
            problems.append(f"{where}: no `permissions:` block at all")
            continue
        for scope, level in need.items():
            granted = perms.get(scope)
            if granted is None:
                problems.append(
                    f"{where}: missing `{scope}: {level}` — the action calls a {scope} endpoint, and "
                    f"an omitted scope is `none` when `permissions:` is declared"
                )
            elif not _covers(str(granted), level):
                problems.append(f"{where}: `{scope}: {granted}` but the action needs `{level}`")
    assert not problems, (
        "documented workflows would run green and post nothing:\n  " + "\n  ".join(problems)
    )


def test_the_grid_of_documented_callers_is_not_empty():
    snippets = _snippets()
    assert len(snippets) >= 3, f"expected the README/docs/demo snippets, found {len(snippets)}"
    assert any("README.md" in w for w in dict(snippets)), "the README must show the action"
