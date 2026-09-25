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
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from posix_shell import require_posix_shell

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "intake-salvage-digest.yml"
STEP_NAME = "Generate salvage digest"

STUB_GH = """#!/bin/bash
# Stub gh for tests/test_salvage_digest_script.py.
# It enforces authentication the way the real `gh` does — exit 4 when no token is in
# the environment — because a stub that accepts anything made the executable test pass
# even after the workflow's job-level GH_TOKEN was deleted (an adversarial review
# demonstrated exactly that, 2026-09-12). With this, removing the token fails here too.
if [ -z "${GH_TOKEN:-}" ] && [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "gh: authentication required (no GH_TOKEN in environment)" >&2
  exit 4
fi
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


def workflow_env() -> dict:
    """The digest job's own `env:` block, so the harness reproduces the runner."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return (workflow.get("jobs", {}).get("salvage-digest", {}) or {}).get("env") or {}

def _step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["salvage-digest"]["steps"]
    for step in steps:
        if step.get("name") == STEP_NAME:
            return step["run"]
    raise AssertionError(f"step {STEP_NAME!r} not found in {WORKFLOW.name}")


def _shell_path(shell: str, path) -> str:
    """`path` in the form *this* shell can open — POSIX, never a bare Windows path.

    Two places need it, and neither is cosmetic. A Windows path interpolated into the step's own
    *text* loses its backslashes, because MSYS reads `\\` as an escape: `> C:\\Users\\x\\d.md`
    becomes `> C:Usersxd.md`, the redirect fails, `bash -e` kills the step and the digest is
    written nowhere. And a `C:\\…` (or `C:/…`) entry inside a `:`-joined PATH is split at the
    colon, so the stub directory silently leaves the shell's PATH. `cygpath -u` is the general
    conversion — it yields `/c/…` for a drive letter and needs no interpretation — while forward
    slashes remain a correct fallback for a plain argv, so the helper degrades instead of failing.
    """
    posix_ish = Path(path).as_posix()
    if os.name != "nt":
        return posix_ish
    try:
        converted = subprocess.run(
            [shell, "-c", 'cygpath -u "$1"', "sh", posix_ish],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return posix_ish
    out = (converted.stdout or "").strip()
    return out if converted.returncode == 0 and out.startswith("/") else posix_ish


def _inherited_path(shell: str) -> str:
    """PATH as the shell itself sees it, for the child environment.

    On Windows the native `C:\\…;C:\\…` list cannot be prefixed with `:` — the first entry then
    reads `C:\\…\\bin:C:\\Windows`, and whether the stub `gh` is still found depends on how MSYS
    guesses at that string. The shell has already converted the Windows PATH into its own POSIX
    form at startup, so ask it for that instead of guessing here.
    """
    if os.name != "nt":
        return os.environ.get("PATH", "")
    probe = subprocess.run([shell, "-c", 'printf %s "$PATH"'], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    return (probe.stdout or "").strip() or os.environ.get("PATH", "")


def _ensure_python3(shell: str, bindir: Path, env: dict) -> None:
    """Give the replayed step a `python3` where this platform's shell has none.

    The step parses the issue list with `python3 -c …` because it is written for
    `ubuntu-latest`. The Windows images expose the same interpreter as `python`, so without this
    the replay would measure the runner's naming rather than the step's shell code. The shim is
    the interpreter already running this suite, so nothing the step *does* changes — only that
    the name resolves. Where `python3` really runs (Linux, macOS, and any Windows image that has
    it) no shim is created and the real interpreter is used.
    """
    try:
        probe = subprocess.run([shell, "-c", 'python3 -c "print(1)"'], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
        usable = probe.returncode == 0 and "1" in (probe.stdout or "")
    except (OSError, subprocess.SubprocessError):
        usable = False
    if usable:
        return
    shim = bindir / "python3"
    shim.write_text(f'#!/bin/bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n',
                    encoding="utf-8")
    shim.chmod(0o755)


@pytest.fixture()
def digest_run(tmp_path):
    """Run the step under `bash -e` with a stub gh, returning its result."""
    shell = require_posix_shell()  # Git Bash on Windows — `bash` on PATH there is the WSL stub
    calls = tmp_path / "gh-calls.log"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(STUB_GH, encoding="utf-8")
    gh.chmod(0o755)

    # Keep the run hermetic: the step writes to /tmp, which is fine in a runner but
    # not in a test suite. The replacement has to be a *shell-usable* path (see
    # `_shell_path`) and is shell-quoted, so a temp directory containing a space works too.
    script_body = (_step_script()
                   .replace("${{ github.repository }}", "Ikalus1988/MisakaNet")
                   .replace("/tmp/", shlex.quote(_shell_path(shell, tmp_path)) + "/"))
    script = tmp_path / "step.sh"
    script.write_text("set -e\n" + script_body, encoding="utf-8")

    # The step only works if the workflow actually exports a token to `gh`. Feed the
    # harness the job's own `env:` so deleting it there breaks this test as well (the
    # secret expression is substituted with a dummy: the point is presence, not value).
    job_env = (workflow_env() or {})
    resolved_env = {
        str(key): re.sub(r"\$\{\{.*?\}\}", "test-token-placeholder", str(value))
        for key, value in job_env.items()
    }
    # Everything the shell reads — the script it opens, the stub it must find first on PATH,
    # the log the stub writes, the directory the step writes into — is handed over in the
    # shell's own path form, never as a Windows path.
    env = {**os.environ, **resolved_env,
           "PATH": f"{_shell_path(shell, bindir)}:{_inherited_path(shell)}",
           "GH_CALLS": _shell_path(shell, calls)}
    _ensure_python3(shell, bindir, env)
    result = subprocess.run([shell, "-e", _shell_path(shell, script)], capture_output=True,
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

def test_the_step_fails_without_a_token_in_the_environment(digest_run):
    """The runner's own behaviour: a stub that ignores auth hides a missing GH_TOKEN.

    Deleting the job-level `env: GH_TOKEN` used to leave this file green while the real
    workflow failed with `exit code 4` — the failure that hid for ten days. The stub now
    exits 4 without a token, and the harness passes the workflow's job env, so removing
    it fails both this file and tests/test_workflow_gh_auth.py.
    """
    assert workflow_env().get("GH_TOKEN"), (
        "the digest job must export GH_TOKEN — permissions: alone does not put a token "
        "in the environment")
    assert digest_run.returncode == 0, digest_run.stderr
