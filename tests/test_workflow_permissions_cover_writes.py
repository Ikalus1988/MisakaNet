#!/usr/bin/env python3
"""A step that writes issues needs a token that may write them.

Why (2026-11-02)
----------------
`sync-question-answers.yml` declared `permissions: contents: read` and then ran
`gh issue edit --add-label answered` with the default `GITHUB_TOKEN`. GitHub returns 403 for a scope
the workflow did not request, the step exited 1, and the **next** step — the actual D1 sync — never
ran. The run history showed "failure" for days and nothing said why; the answer to "which crons are
just load?" turned out to include one that was producing nothing because of a one-line omission.

The rule this file enforces is the narrow version that caught it, not a general permissions audit:

* only steps whose token is the **default** `GITHUB_TOKEN` are checked — a job using a PAT is out of
  scope, because that permission lives on the credential, not on the workflow;
* only `gh issue …` / `gh pr …` **write** verbs count — `gh issue view`/`list` are reads and need
  nothing beyond `contents: read`;
* the effective block is job-level if present, otherwise workflow-level, matching how GitHub reads it
  (declaring `permissions:` at all turns every unlisted scope into `none`).

It is deliberately not a full action-permission model: `tests/test_documented_action_permissions.py`
already derives the `create-github-app-token` requirements from the action's own metadata. This one
covers the plain-`gh` case that has no metadata to derive from.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

#: `gh issue edit --add-label x`, `gh pr comment 1`, … — the write verbs that need a write scope.
WRITE_COMMAND = re.compile(r"\bgh (issue|pr) (edit|create|comment|close|delete|merge)\b")
DEFAULT_TOKEN = re.compile(r"GH_TOKEN:\s*\$\{\{\s*secrets\.GITHUB_TOKEN\s*\}\}")

SCOPE = {"issue": "issues", "pr": "pull-requests"}


def _workflows() -> list[tuple[str, dict, str]]:
    out = []
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        out.append((path.name, yaml.safe_load(text) or {}, text))
    return out


def _offenders() -> list[str]:
    problems = []
    for name, data, text in _workflows():
        commands = set(WRITE_COMMAND.findall(text))
        if not commands or not DEFAULT_TOKEN.search(text):
            continue
        workflow_perms = data.get("permissions")
        for job_name, job in (data.get("jobs") or {}).items():
            job = job if isinstance(job, dict) else {}
            perms = job.get("permissions", workflow_perms)
            for verb, scope in ((c[0], SCOPE[c[0]]) for c in commands):
                if not isinstance(perms, dict):
                    problems.append(
                        f"{name}::{job_name}: runs `gh {verb} …` with the default token but declares "
                        "no `permissions:` block")
                    continue
                if perms.get(scope) != "write":
                    problems.append(
                        f"{name}::{job_name}: runs `gh {verb} …` with the default token but "
                        f"{scope}={perms.get(scope)!r} — a scope that is not requested is `none`")
    return problems


def test_no_step_writes_issues_without_the_scope_to_do_it() -> None:
    problems = _offenders()
    assert not problems, (
        "a step whose token cannot perform the write fails with 403, and the step after it never "
        "runs — that is how the answer sync stopped delivering for days while reporting only "
        "'failure':\n  " + "\n  ".join(problems))


def test_the_rule_still_finds_the_case_it_was_written_for() -> None:
    """A gate that matches nothing is indistinguishable from a gate that is broken."""
    names = {name for name, _, _ in _workflows()}
    assert "sync-question-answers.yml" in names
    data = yaml.safe_load((WORKFLOWS / "sync-question-answers.yml").read_text(encoding="utf-8"))
    assert data["permissions"].get("issues") == "write", (
        "the fix for run 41315405837 was `issues: write` on this workflow; if it is gone, the daily "
        "cron is back to labelling 0/9 and skipping the sync")
