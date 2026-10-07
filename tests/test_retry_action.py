#!/usr/bin/env python3
"""The retry action has to be able to run a script that contains a double quote.

`.github/actions/retry/action.yml` executes the caller's `run:` input as

    $SHELL_CMD -c "${{ inputs.run }}"

`${{ … }}` is substituted into the step **before bash parses it** — the mechanism #2938 measured
when a pull-request file name reached a `run:` body as `$(id)`. Applied here the substitution does
not inject anything; it destroys the script. A caller whose `run:` contains `"` closes the string
the script was inlined into:

    bash -c "if [ -n "$FOO" ]; then
      echo "value is $FOO"
    fi"
    -> syntax error: unexpected end of file   (exit 2)

and a single-line script is worse, because it does not fail — it runs a different command and
exits 0. Both callers in this repository (`cite-lesson.yml`, `lesson-notify.yml`) pass scripts full
of quotes, so the action could not run either of them. GitHub has no run of either workflow in the
retrievable window that was not `skipped`, so nothing had ever exercised the path.

The fix carries the caller's script through `env:` instead. Bash expands `"$RETRY_COMMAND"` as a
single word and does not re-scan the result, so the text arrives exactly as written.

These tests run the **real** action body and the **real** caller scripts, because the failure is a
property of the two being combined and neither half shows it alone. The action had no test at all:
`tests/test_retry.py` is about HTTP retries in `scripts/contribute.py` and has never touched it.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from posix_shell import require_posix_shell

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

#: Both workflows that use this action declare `runs-on: ubuntu-latest`, and the action's two
#: callers are `ubuntu-latest` jobs. Measured on `windows-latest` before this marker existed: the
#: step ran under Git Bash and every script that carried a non-ASCII literal came back mangled —
#: `assert '?? ? Lesson ??' == '📘 新 Lesson 贡献'` — because the runner's codepage is not UTF-8.
#: That is a property of the Windows image, not of the action, and these tests would be asserting
#: a platform the workflows never run on. A skip that says so beats a green that means nothing.
ubuntu_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the workflows under test declare `runs-on: ubuntu-latest`; Git Bash on windows-latest "
           "does not round-trip the non-ASCII literals these scripts contain",
)

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github" / "actions" / "retry" / "action.yml"
WORKFLOWS = REPO / ".github" / "workflows"

EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)


def action_step() -> dict:
    document = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    steps = document["runs"]["steps"]
    assert len(steps) == 1, f"the retry action grew a second step; this harness runs one: {steps}"
    return steps[0]


def resolve(text: str, values: dict[str, str]) -> str:
    """Substitute `${{ … }}` the way the runner does — textually, before bash sees anything."""
    def replace(match: re.Match) -> str:
        expression = match.group(1).strip()
        if expression not in values:
            raise AssertionError(
                f"the harness was not given a value for ${{{{ {expression} }}}}. Every `${{{{ … }}}}` "
                "in the step has to be resolved here, or the test would be reading substituted text "
                "instead of the caller's own.")
        return values[expression]
    return EXPRESSION.sub(replace, text)


def action_step_inputs() -> dict:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))["inputs"]


def run_action(script: str, *, env_extra: dict | None = None, cwd: Path | None = None,
               **inputs):
    """Run the composite action's real body with `script` as its `run:` input.

    The `env:` block is applied the way Actions applies it — as real process environment, not as
    text written into the step file. Writing it into the file would put the caller's quotes back
    into the generated script and reproduce the very bug this test exists to catch.

    `shell_override` is set to the shell this test is itself running under, because the step
    invokes `$SHELL_CMD` and the action's default of `bash` resolves to the WSL launcher on
    `windows-latest` — see `scripts/posix_shell.py` for the full account. Letting the two agree is
    also the honest arrangement: the step runs under the same shell the test can reason about.
    """
    shell = require_posix_shell()
    step = action_step()
    with_values = {"run": script, "shell_override": shell, **inputs}
    env_map = {name: str(spec.get("default", "")) for name, spec in action_step_inputs().items()}
    env_map.update({k: str(v) for k, v in with_values.items()})

    body = step["run"]
    unknown = {m.group(1).strip() for m in EXPRESSION.finditer(body)}
    leftovers = unknown - set(step.get("env") or {})
    assert not leftovers, (
        f"the action body still inlines {sorted(leftovers)} directly into the shell. That is the "
        "shape this file exists to rule out — carry it in `env:` and reference it as a variable.")

    resolved_body = resolve(body, {f"inputs.{k}": v for k, v in env_map.items()})
    workspace = Path(cwd) if cwd else Path(tempfile.mkdtemp())
    env = {**os.environ,
           "GITHUB_WORKSPACE": str(workspace),
           "GITHUB_OUTPUT": str(workspace / "out.txt"),
           **(env_extra or {})}
    # The step reads its inputs from the environment; Actions sets `env:` the same way.
    for name, value in (step.get("env") or {}).items():
        env[name] = resolve(str(value), {f"inputs.{k}": v for k, v in env_map.items()})

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "step.sh"
        target.write_text(resolved_body, encoding="utf-8")
        proc = subprocess.run([shell, str(target)], capture_output=True, text=True,
                              env=env, cwd=str(workspace), timeout=120)
    return proc


def caller_steps(workflow: str) -> list[tuple[str, dict]]:
    document = yaml.safe_load((WORKFLOWS / workflow).read_text(encoding="utf-8"))
    found = []
    for job_name, job in document["jobs"].items():
        for step in job.get("steps", []):
            if "actions/retry" in str(step.get("uses", "")):
                found.append((f"{workflow}:{job_name}:{step.get('name', '?')}", step))
    return found


#: Every test below that checks the caller's *text* arrived intact forces these, rather than
#: inheriting the action's declared defaults of `max_attempts: 3` / `backoff_base_seconds: 10`.
#: That combination sleeps 10s, then 100s, then 1000s — fine when the script succeeds on the first
#: try, and a multi-minute stall the moment a change under test makes it fail, which is exactly
#: when the suite should be reporting quickly. The retry arithmetic has its own tests below, which
#: do drive the real backoff.
ONE_ATTEMPT = {"max_attempts": 1, "backoff": "fixed", "backoff_base_seconds": 0}


# ── The class: a script with quotes has to survive ─────────────────────────────────────────────────

@ubuntu_only
def test_a_script_containing_double_quotes_runs():
    """The minimal shape: two double quotes around a variable, on one line.

    Under the old inlining this did not fail — it printed `hello` instead of `hello world` and
    exited 0, which is the version of this bug that would have gone unnoticed.
    """
    script = 'FOO="hello world"\necho "value is $FOO"\n'
    proc = run_action(script, **ONE_ATTEMPT)
    assert "syntax error" not in proc.stderr, f"the caller's quotes broke the step:\n{proc.stderr}"
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "value is hello world" in proc.stdout, (
        f"the step ran something other than the script it was given:\n{proc.stdout}")


@ubuntu_only
def test_a_multi_line_script_containing_double_quotes_runs():
    """The shape both real callers use. Under the old inlining this was a hard syntax error."""
    script = (
        'if [ -n "$FOO" ]; then\n'
        '  echo "value is $FOO"\n'
        '  if [ "$FOO" = "hello world" ]; then\n'
        '    echo "matched"\n'
        '  fi\n'
        'fi\n'
    )
    proc = run_action(script, env_extra={"FOO": "hello world"}, **ONE_ATTEMPT)
    assert "syntax error" not in proc.stderr, f"the caller's quotes broke the step:\n{proc.stderr}"
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "matched" in proc.stdout, proc.stdout


@ubuntu_only
def test_a_script_containing_a_command_substitution_is_not_expanded_by_the_outer_shell():
    """`$(…)` in the caller's script is the caller's business, not the action's.

    Carrying the script as a value is what makes this hold: the text is expanded once, by the inner
    shell. The old inlining gave the outer shell a chance to run it first — the same two-pass
    problem the #2938 injection fix turned on.
    """
    script = 'echo "outer=$(echo inner)"\n'
    proc = run_action(script, **ONE_ATTEMPT)
    assert "syntax error" not in proc.stderr, proc.stderr
    assert "outer=inner" in proc.stdout, proc.stdout


# ── The two real callers ───────────────────────────────────────────────────────────────────────────

@ubuntu_only
def test_the_real_lesson_notify_step_runs_through_the_action():
    """`lesson-notify.yml` builds a Feishu card; the script is quotes from top to bottom.

    Run with an empty webhook, which is the branch the workflow already has: it announces the skip
    and exits 0. The point is that it reaches that branch at all.
    """
    steps = caller_steps("lesson-notify.yml")
    assert steps, "lesson-notify.yml no longer uses the retry action — update this test"
    for label, step in steps:
        script = step["with"]["run"]
        caller_env = {name: resolve(str(value), {
            "secrets.FEISHU_WEBHOOK_URL": "",
            "github.event.issue.title": 'fix: handle "quoted" input',
            "github.event.issue.user.login": "someone",
            "github.event.issue.html_url": "https://example.invalid/1",
            "github.event.issue.body": "a body line",
        }) for name, value in (step.get("env") or {}).items()}
        proc = run_action(script, env_extra=caller_env, **ONE_ATTEMPT)
        assert "syntax error" not in proc.stderr, f"{label} could not be parsed:\n{proc.stderr}"
        assert proc.returncode == 0, f"{label} failed:\n{proc.stdout}\n{proc.stderr}"
        assert "No FEISHU_WEBHOOK_URL secret set" in proc.stdout, (
            f"{label} never reached its own first branch:\n{proc.stdout}")


@ubuntu_only
def test_both_real_cite_lesson_steps_survive_the_transformation():
    """`cite-lesson.yml` passes a python heredoc and two `git config` lines with quoted values.

    These are not executed for their effect — `git push` is in the second one — but they are
    executed far enough to prove the text arrives intact. The working directory is a throwaway git
    repository, so nothing here can reach this one.

    `max_attempts=1` and a zero backoff are forced: both steps declare `max_attempts: 3` with
    `backoff_base_seconds: 5`, so honouring them would sleep 5s + 25s + 125s per step to reach a
    conclusion this test does not depend on. The retry arithmetic has its own tests below.
    """
    steps = caller_steps("cite-lesson.yml")
    assert len(steps) == 2, f"cite-lesson.yml changed its retry call sites: {len(steps)}"
    for label, step in steps:
        script = step["with"]["run"]
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", "."], cwd=tmp, capture_output=True, check=True)
            proc = run_action(script, cwd=Path(tmp), max_attempts=1, backoff="fixed",
                              backoff_base_seconds=0, env_extra={
                                  "REPO": "example/repo", "ISSUE_NUMBER": "1", "RUNNER_TEMP": tmp,
                              })
        assert "syntax error" not in proc.stderr, (
            f"{label} could not be parsed once it was carried as a value:\n{proc.stderr}")


# ── The retry behaviour itself, which the rewrite had to preserve ───────────────────────────────────

@ubuntu_only
def test_a_failing_script_is_retried_the_configured_number_of_times():
    script = 'COUNT_FILE="$GITHUB_WORKSPACE/attempts"\necho x >> "$COUNT_FILE"\nexit 3\n'
    with tempfile.TemporaryDirectory() as tmp:
        proc = run_action(script, cwd=Path(tmp), max_attempts=3, backoff="fixed", backoff_base_seconds=0)
        attempts = (Path(tmp) / "attempts").read_text(encoding="utf-8").split()
    assert proc.returncode == 3, f"the final exit code must reach the caller:\n{proc.stdout}"
    assert len(attempts) == 3, f"expected 3 attempts, got {len(attempts)}"
    assert "Max attempts reached" in proc.stdout, proc.stdout


@ubuntu_only
def test_a_succeeding_script_is_not_retried():
    script = 'COUNT_FILE="$GITHUB_WORKSPACE/attempts"\necho x >> "$COUNT_FILE"\nexit 0\n'
    with tempfile.TemporaryDirectory() as tmp:
        proc = run_action(script, cwd=Path(tmp), max_attempts=3, backoff="fixed", backoff_base_seconds=0)
        attempts = (Path(tmp) / "attempts").read_text(encoding="utf-8").split()
    assert proc.returncode == 0
    assert len(attempts) == 1, f"a green first attempt must not be retried, got {len(attempts)}"
    assert "Success on attempt 1" in proc.stdout, proc.stdout


@ubuntu_only
def test_an_unlisted_exit_code_stops_immediately():
    """`retry_on_exit_code: "1"` is what `cite-lesson.yml` sets; a `git push` failure that is not
    code 1 should not burn the remaining attempts."""
    script = 'COUNT_FILE="$GITHUB_WORKSPACE/attempts"\necho x >> "$COUNT_FILE"\nexit 2\n'
    with tempfile.TemporaryDirectory() as tmp:
        proc = run_action(script, cwd=Path(tmp), max_attempts=4, backoff="fixed",
                          backoff_base_seconds=0, retry_on_exit_code="1")
        attempts = (Path(tmp) / "attempts").read_text(encoding="utf-8").split()
    assert proc.returncode == 2
    assert len(attempts) == 1, f"exit 2 is not in the retry list, so it must stop after 1: {len(attempts)}"
    assert "not in retry list" in proc.stdout, proc.stdout


@ubuntu_only
def test_a_listed_exit_code_is_retried():
    script = 'COUNT_FILE="$GITHUB_WORKSPACE/attempts"\necho x >> "$COUNT_FILE"\nexit 1\n'
    with tempfile.TemporaryDirectory() as tmp:
        proc = run_action(script, cwd=Path(tmp), max_attempts=2, backoff="fixed",
                          backoff_base_seconds=0, retry_on_exit_code="1")
        attempts = (Path(tmp) / "attempts").read_text(encoding="utf-8").split()
    assert proc.returncode == 1
    assert len(attempts) == 2, f"exit 1 is in the retry list, so both attempts should run: {len(attempts)}"


@ubuntu_only
def test_the_output_file_records_the_attempt_count():
    script = "exit 0\n"
    with tempfile.TemporaryDirectory() as tmp:
        proc = run_action(script, cwd=Path(tmp), **ONE_ATTEMPT)
        written = (Path(tmp) / "out.txt").read_text(encoding="utf-8")
    assert proc.returncode == 0
    assert "attempts_count=1" in written, written
    assert "final_exit_code=0" in written, written
