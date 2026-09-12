#!/usr/bin/env python3
"""Run the salvage digest's shell step against a stub `gh` (2026-09-12).

Why this exists
---------------
`Intake Salvage Digest` failed on its daily schedule from at least 2026-09-09 and
nobody noticed, because a red run in a list of daily schedules looks like
background noise. When it was finally investigated it turned out to hold *three*
stacked shell bugs, each of which could only be seen by running the script:

1. `gh` was never given a token (exit 4 = gh's auth failure);
2. `$(date -u +%Y-%m-%d %H:%M UTC)` was unquoted, so `%H:%M` became an extra
   operand and `date` exited 1;
3. backticks inside double-quoted strings — `` `/salvage-review` `` and
   `` `## Error` `` — were command substitutions: the shell tried to execute them
   (exit 127) and the digest silently lost those lines.

Every one of those is invisible to a YAML lint, to a workflow-pin test, and to
reading the diff. They are visible to `bash -e` with a stubbed `gh`, which is what
this test does: extract the step from the workflow, substitute the `${{ … }}`
expressions, and run it.

The stub answers the two `gh issue list` shapes and records every call, so the
assertions can also check that the digest still asks for the right things.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "intake-salvage-digest.yml"
STEP_NAME = "Generate salvage digest"

STUB_GH = """#!/bin/bash
# Stub gh for tests/test_salvage_digest_script.py
echo "gh $*" >> "$GH_CALLS"
case "$*" in
  *"issue list"*"auto-rejected"*)
    echo '[{"number":1630,"title":"[Intake] Roleplay chat app (Go)","labels":[],"createdAt":"2026-09-11T10:00:00Z"},{"number":1574,"title":"[Intake] god-moding","labels":[],"createdAt":"2026-09-11T11:00:00Z"}]' ;;
  *"issue list"*"salvage-digest"*) echo "" ;;
  *"issue create"*) echo "https://example.invalid/issues/9999" ;;
  *"issue comment"*) echo "ok" ;;
  *) echo "[]" ;;
esac
"""


def _step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["salvage-digest"]["steps"]
    for step in steps:
        if step.get("name") == STEP_NAME:
            return step["run"]
    raise AssertionError(f"step {STEP_NAME!r} not found in {WORKFLOW.name}")


@pytest.fixture()
def digest_run(tmp_path):
    """Run the step under `bash -e` with a stub gh, returning its result."""
    calls = tmp_path / "gh-calls.log"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(STUB_GH, encoding="utf-8")
    gh.chmod(0o755)

    # Keep the run hermetic: the step writes to /tmp, which is fine in a runner but
    # not in a test suite.
    script_body = (_step_script()
                   .replace("${{ github.repository }}", "Ikalus1988/MisakaNet")
                   .replace("/tmp/", f"{tmp_path}/"))
    script = tmp_path / "step.sh"
    script.write_text("set -e\n" + script_body, encoding="utf-8")

    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "GH_CALLS": str(calls)}
    result = subprocess.run(["bash", "-e", str(script)], capture_output=True,
                            text=True, env=env, cwd=tmp_path)
    result.calls = calls.read_text(encoding="utf-8") if calls.exists() else ""
    result.digest = (tmp_path / "salvage_digest.md")
    return result


def test_the_step_survives_bash_e(digest_run):
    assert digest_run.returncode == 0, (
        "the digest step fails under `bash -e`, which is how the workflow runs it:\n"
        f"--- stdout ---\n{digest_run.stdout}\n--- stderr ---\n{digest_run.stderr}"
    )


def test_it_asks_gh_for_the_rejected_issues(digest_run):
    assert "issue list" in digest_run.calls
    assert "--label auto-rejected" in digest_run.calls
    assert "--state open" in digest_run.calls


def test_the_digest_keeps_its_backticked_instructions(digest_run):
    """Backticks in a double-quoted string become command substitution.

    `` `/salvage-review` `` was executed as a command (exit 127) and the
    `` `## Error` `` / `` `## Verification` `` fragments were substituted away, so
    the digest's own instructions were being mangled before it ever got posted.
    """
    text = digest_run.digest.read_text(encoding="utf-8")
    assert "/salvage-review" in text, "the digest lost its /salvage-review instruction"
    assert "`## Error`" in text and "`## Verification`" in text, (
        "backticked section names were eaten by command substitution"
    )
    assert "[Intake] Roleplay chat app (Go)" in text, "the issue table is empty"


def test_the_timestamp_is_a_timestamp(digest_run):
    """`$(date -u +%Y-%m-%d %H:%M UTC)` unquoted makes date exit 1."""
    text = digest_run.digest.read_text(encoding="utf-8")
    assert "**Generated:**" in text
    generated = text.split("**Generated:**", 1)[1].splitlines()[0].strip()
    assert generated.endswith("UTC") and len(generated) == len("2026-09-12 12:39 UTC"), generated
    assert "extra operand" not in digest_run.stderr
