#!/usr/bin/env python3
"""The intake-kind audit must be able to *fail*, and the job must go red when it does (#3835).

`tests/test_intake_kind_audit.py` shows that the detector path and the digest/grep contract can fire.
This file is about the other half of a gate: the exit status.

The defect (#3835) was in two places at once, and each half hid the other:

* `scripts/audit_intake_kinds.py` returned 0 from **every** path, and its explicit-kind flip
  cross-check sat *after* the `--digest` early return. `--digest` is the only invocation CI makes, so
  the check was dead code and its `WARNING` had no consumer anywhere in the repository;
* `intake-kind-audit.yml` decided "clean" by grepping the digest for one sentence, so even a digest
  full of findings was green as long as the grep matched.

Two properties are pinned here, in both directions:

1. **The script's exit status is the conclusion.** A replay fixture with one explicit `Kind:` that the
   detector overrode exits 3; the same fixture without it exits 0; an empty corpus exits 4 rather than
   0/0 counting as a pass; unreadable input exits 2 rather than shortening the audit.
2. **The workflow reads that status.** The audit step's own shell is extracted from the YAML and run
   against a `python3` stub, so the mapping is executed rather than asserted textually: a flip or a
   zero-issue run fails the job and still posts a digest issue, a run that could not execute fails it
   without posting one, an exit 0 with no digest fails it, and a digest of *misfiled* intakes is
   reported in an issue while the job stays green — that last one is the old contract (#1396/#1397:
   reconciliation is maintainer work, not a build failure) and it is easy to lose by collapsing
   "not clean" and "must fail" into one flag. The gate step's shell is executed too: it must write a
   step summary and `exit 1`.

The flip fixture is a **recorded row** (`--out`'s format), not a detector run, because the detector
honours an explicit kind today — that is precisely why the cross-check is a regression tripwire. One
test drives the live detector to show the invariant holds, so the tripwire is not mistaken for noise.

No network: `--from-jsonl` was added for exactly this, and the workflow steps run against stubs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from subprocess_env import POSIX_PATH, child_env  # tests/subprocess_env.py
from posix_shell import require_posix_shell

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.audit_intake_kinds import (  # noqa: E402
    CLEAN_SENTENCE,
    EXIT_CLEAN,
    EXIT_EMPTY,
    EXIT_FLIP,
    EXIT_INPUT,
    audit_issue,
    exit_status,
    find_flipped,
)
from scripts.intake_kind import infer_intake_kind  # noqa: E402

SCRIPT = REPO / "scripts" / "audit_intake_kinds.py"
WORKFLOW = REPO / ".github" / "workflows" / "intake-kind-audit.yml"
BASH_ONLY = pytest.mark.skipif(os.name == "nt", reason="the workflow step is bash")


# ── the script: exit status is the conclusion ─────────────────────────────────────────────────────


def _row(number=1, kind_body="missing_lesson", auto=False, state="open") -> dict:
    """One row in the shape `--out` writes and `--from-jsonl` reads."""
    return {"number": number, "title": "t", "state": state, "labels": ["mcp-intake"],
            "kind_body": kind_body, "kind_detected": "question" if auto else kind_body,
            "auto_detected": auto, "problem_preview": "p"}


def _replay(tmp_path: Path, rows: list[dict], name="rows.jsonl") -> Path:
    p = tmp_path / name
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def _audit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(REPO),
                          capture_output=True, text=True, timeout=120)


def test_a_flipped_explicit_kind_fails_the_digest(tmp_path):
    """The acceptance case: `Kind: new_lesson_candidate` re-detected as `question` exits non-zero."""
    flipped = _row(901, kind_body="new_lesson_candidate", auto=True)
    proc = _audit("--from-jsonl", str(_replay(tmp_path, [flipped])), "--digest")

    assert proc.returncode == EXIT_FLIP, proc.stderr
    assert "auto-flipped" in proc.stdout
    assert "#901" in proc.stdout, "the digest must name the row it is failing on"
    # A digest that can fail must not also say it is clean — the grep-based consumer reads that line.
    assert CLEAN_SENTENCE not in proc.stdout
    assert f"exits {EXIT_FLIP}" in proc.stderr


def test_a_clean_replay_exits_zero_and_keeps_the_old_digest_line(tmp_path):
    """The other direction: without a flip, nothing changes for the existing digest consumers."""
    rows = [_row(1), _row(2, kind_body="missing_lesson", auto=True)]  # auto on missing_lesson: allowed
    proc = _audit("--from-jsonl", str(_replay(tmp_path, rows)), "--digest")

    assert proc.returncode == EXIT_CLEAN, proc.stderr
    assert proc.stdout.startswith(CLEAN_SENTENCE), proc.stdout
    assert "2 row(s) read" in proc.stdout


def test_bare_mode_also_fails_on_a_flip(tmp_path):
    """Four core lessons verify this audit as `python scripts/audit_intake_kinds.py` exiting 0.

    That command has to be able to fail, otherwise their `verify` field still only proves the script
    did not crash (#3835).
    """
    flipped = _row(902, kind_body="question", auto=True)
    proc = _audit("--from-jsonl", str(_replay(tmp_path, [flipped])))

    assert proc.returncode == EXIT_FLIP, proc.stdout + proc.stderr
    assert "auto-flipped" in proc.stderr


def test_zero_rows_read_is_not_a_pass(tmp_path):
    """0/0 is not 100%: a run that examined nothing must not report clean (#3759)."""
    proc = _audit("--from-jsonl", str(_replay(tmp_path, [])), "--digest")

    assert proc.returncode == EXIT_EMPTY, proc.stdout + proc.stderr
    assert "Nothing was audited" in proc.stdout
    assert CLEAN_SENTENCE not in proc.stdout
    assert "0 row(s) read" in proc.stdout


@pytest.mark.parametrize("line", [
    "{not json",
    '{"number": 1, "state": "open"}',                                  # fields missing
    '{"number": 1, "state": "open", "labels": [], "kind_body": "question",'
    ' "kind_detected": "question", "auto_detected": "false"}',          # a string, not a bool
    '["not", "an", "object"]',
])
def test_unreadable_replay_input_fails_instead_of_shortening_the_audit(tmp_path, line):
    """A skipped row is a row that was not checked — the failure mode this file exists to end."""
    p = tmp_path / "bad.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    proc = _audit("--from-jsonl", str(p), "--digest")

    assert proc.returncode == EXIT_INPUT, proc.stdout + proc.stderr
    assert proc.stdout.strip() == "", "nothing may be printed that could be read as a verdict"
    assert "replay not read" in proc.stderr


def test_the_digest_states_how_many_rows_it_read_and_what_ran(tmp_path):
    """#3759: 'no misfiles found' next to the denominator, and next to the checks that executed."""
    rows = [_row(1), _row(2, kind_body="question", auto=True)]
    proc = _audit("--from-jsonl", str(_replay(tmp_path, rows)), "--digest")

    assert proc.returncode == EXIT_FLIP
    assert "1 flipped" in proc.stdout
    assert "2 row(s)" in proc.stdout
    assert "find_flagged" in proc.stdout and "find_flipped" in proc.stdout


def test_an_absent_kind_auto_detected_as_a_question_is_not_a_flip():
    """`none` renders an absent `Kind:`; auto-detection is what it is *for*.

    The old inline predicate compared against `("", "missing_lesson")` while rows store `"none"`, so
    every Kind-less question would have been reported as a flipped explicit kind the moment this
    check started deciding an exit status.
    """
    rows = [_row(1, kind_body="none", auto=True),
            _row(2, kind_body="missing_lesson", auto=True),
            _row(3, kind_body="", auto=True)]
    assert find_flipped(rows) == []
    assert exit_status(rows, []) == EXIT_CLEAN


def test_the_live_detector_still_honours_an_explicit_kind():
    """Why the flip check is a tripwire, not a finding generator: it holds by construction today.

    If `infer_intake_kind` ever stops honouring an explicit non-`missing_lesson` kind (it mirrors
    `workers/lib/utils.js`, so it can), this test fails and `find_flipped` starts returning rows.
    """
    explicit = {
        "number": 1, "state": "open", "title": "[Question] how do I configure it?",
        "labels": [{"name": "mcp-intake"}],
        "body": "**Kind:** new_lesson_candidate\n\n## Problem\n\nHow do I configure the foobar?\n",
    }
    row = audit_issue(explicit, infer_intake_kind)
    assert row["kind_body"] == "new_lesson_candidate"
    assert row["auto_detected"] is False, row
    assert find_flipped([row]) == []

    absent = dict(explicit, body="## Problem\n\nHow do I configure the foobar?\n")
    auto_row = audit_issue(absent, infer_intake_kind)
    assert auto_row["kind_body"] == "none"
    assert auto_row["auto_detected"] is True, auto_row
    assert find_flipped([auto_row]) == [], "an absent kind is allowed to be auto-detected"


# ── the workflow: the steps' own shell, run against stubs ─────────────────────────────────────────


def _steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["audit"]["steps"]


def _step(step_id: str) -> dict:
    for step in _steps():
        if step.get("id") == step_id:
            return step
    raise AssertionError(f"workflow has no step with id={step_id!r}")


def _run_block(block: str, env: dict) -> subprocess.CompletedProcess[str]:
    """Run a step's `run:` the way GitHub does: bash -e (and pipefail)."""
    # `require_posix_shell()` instead of a literal "bash": on Windows the literal resolves to
    # System32\bash.exe (the WSL launcher) and fails with an environment error, and the portability
    # test rightly bans it. The helper skips with a reason when no POSIX shell is available.
    return subprocess.run([require_posix_shell(), "-eo", "pipefail", "-c", block], cwd=str(REPO), env=env,
                          capture_output=True, text=True, timeout=120)


def _stub_python3(tmp_path: Path, digest_text: str, status: int) -> tuple[Path, Path]:
    """A `python3` that prints a preset digest and exits with a preset status."""
    bin_dir = tmp_path / "bin-python"
    bin_dir.mkdir()
    stub = bin_dir / "python3"
    stub.write_text(
        "#!/bin/sh\n"
        'cat "$STUB_DIGEST"\n'
        'echo "stub stderr" >&2\n'
        'exit "$STUB_STATUS"\n',
        encoding="utf-8")
    stub.chmod(0o755)
    digest = tmp_path / "stub_digest.md"
    digest.write_text(digest_text, encoding="utf-8")
    return bin_dir, digest


def _run_audit_step(tmp_path: Path, *, status: int, digest_text: str) -> tuple[dict, str]:
    """Execute the `Run intake kind audit` step; return its GITHUB_OUTPUT map and stdout."""
    bin_dir, stub_digest = _stub_python3(tmp_path, digest_text, status)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = child_env(
        PATH=f"{bin_dir}:{POSIX_PATH}",
        RUNNER_TEMP=str(tmp_path),
        GITHUB_OUTPUT=str(output),
        STUB_DIGEST=str(stub_digest),
        STUB_STATUS=str(status),
    )
    proc = _run_block(_step("audit")["run"], env)
    assert proc.returncode == 0, proc.stdout + proc.stderr  # the step records, it does not fail
    outputs = {}
    for line in output.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            outputs[key] = value
    return outputs, proc.stdout


FLIP_DIGEST = "# 🧭 Intake Kind Audit\n\n## ⚠️ Explicit kinds that were auto-flipped: 1\n"


MISFILE_DIGEST = (
    "# 🧭 Intake Kind Audit\n\n"
    "## 🧭 Question-shaped intakes routed as lessons: 1\n\n"
    "| Issue | Reason | Title |\n|---|---|---|\n| [#7](https://example/7) | "
    "explicit-question-unlabeled | t |\n"
)


@BASH_ONLY
def test_a_flip_makes_the_audit_step_report_not_clean(tmp_path):
    outputs, _ = _run_audit_step(tmp_path, status=EXIT_FLIP, digest_text=FLIP_DIGEST)

    assert outputs["status"] == str(EXIT_FLIP)
    assert outputs["clean"] == "false", outputs
    assert outputs["verdict"] == "fail", "a flip is a code regression: the job has to go red"
    assert outputs["post_digest"] == "true", "the finding must still reach a digest issue"


@BASH_ONLY
def test_a_clean_run_reports_clean(tmp_path):
    outputs, _ = _run_audit_step(tmp_path, status=EXIT_CLEAN, digest_text=CLEAN_SENTENCE)

    assert outputs["clean"] == "true", outputs
    assert outputs["status"] == "0"
    assert outputs["verdict"] == "pass", outputs
    assert outputs["post_digest"] == "false", outputs


@BASH_ONLY
def test_misfiles_are_reported_without_failing_the_job(tmp_path):
    """The old contract kept: a misfiled question intake is maintainer work (#1396/#1397), not a
    build failure. The digest loses its clean sentence; the job stays green."""
    outputs, _ = _run_audit_step(tmp_path, status=EXIT_CLEAN, digest_text=MISFILE_DIGEST)

    assert outputs["status"] == "0"
    assert outputs["clean"] == "false", outputs
    assert outputs["post_digest"] == "true", "a misfile still has to become a digest issue"
    assert outputs["verdict"] == "pass", "reporting maintainer work must not turn the job red"


@BASH_ONLY
def test_an_audit_that_did_not_run_is_not_clean(tmp_path):
    """A 401/network failure is "unknown", not "clean" — the whole point of a separate status."""
    outputs, _ = _run_audit_step(tmp_path, status=1, digest_text="")

    assert outputs["clean"] == "false", outputs
    assert outputs["verdict"] == "fail", outputs
    assert outputs["post_digest"] == "false", "there is no digest to post when it did not run"


@BASH_ONLY
def test_an_empty_digest_with_exit_zero_is_not_clean(tmp_path):
    """The contract drift guard: status 0 must be accompanied by the artifact the workflow reads."""
    outputs, stdout = _run_audit_step(tmp_path, status=EXIT_CLEAN, digest_text="")

    assert outputs["clean"] == "false", outputs
    assert outputs["verdict"] == "fail", outputs
    assert "::error::" in stdout


@BASH_ONLY
def test_zero_issues_read_turns_the_job_red(tmp_path):
    outputs, _ = _run_audit_step(
        tmp_path, status=EXIT_EMPTY,
        digest_text="**Nothing was audited.** 0 rows were read.\n")

    assert outputs["status"] == str(EXIT_EMPTY)
    assert outputs["clean"] == "false", outputs
    assert outputs["verdict"] == "fail", outputs
    assert outputs["post_digest"] == "true", outputs


@BASH_ONLY
@pytest.mark.parametrize("status,needle", [
    (EXIT_FLIP, "auto-flipped"),
    (EXIT_EMPTY, "zero issues"),
    (1, "could not run"),
])
def test_the_gate_step_fails_the_job_and_writes_a_summary(tmp_path, status, needle):
    digest = tmp_path / "audit_digest.md"
    digest.write_text(FLIP_DIGEST, encoding="utf-8")
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    env = child_env(
        RUNNER_TEMP=str(tmp_path),
        GITHUB_STEP_SUMMARY=str(summary),
        AUDIT_STATUS=str(status),
        AUDIT_DIGEST=str(digest),
    )
    proc = _run_block(_step("gate")["run"], env)

    assert proc.returncode == 1, "the gate step is the job's only red; it has to exit non-zero"
    body = summary.read_text(encoding="utf-8")
    assert needle in body, body
    assert "::error title=Intake Kind Audit::" in proc.stdout
    if status == EXIT_FLIP:
        assert "auto-flipped" in body, "the summary must carry the digest's evidence"


def test_the_digest_issue_is_posted_whenever_there_is_something_to_post():
    """Driven by `post_digest`, so a misfile (status 0) still becomes an issue."""
    assert _step("digest-issue")["if"].strip() == "steps.audit.outputs.post_digest == 'true'"


def test_the_gate_step_runs_after_the_digest_issue_is_posted():
    """Order matters in Actions: a failing step stops the ones below it, so the gate goes last."""
    order = [s.get("id") for s in _steps()]
    assert order.index("gate") > order.index("digest-issue"), order


def _stub_gh(tmp_path: Path) -> tuple[Path, Path]:
    """A `gh` that answers `issue list` from a fixture and logs the write commands it was given."""
    bin_dir = tmp_path / "bin-gh"
    bin_dir.mkdir()
    stub = bin_dir / "gh"
    stub.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "issue" ] && [ "$2" = "list" ]; then\n'
        '  printf "%s\\n" "${STUB_ISSUES:-[]}"\n'
        '  exit 0\n'
        'fi\n'
        'body=""\n'
        'prev=""\n'
        'for arg in "$@"; do\n'
        '  if [ "$prev" = "--body-file" ]; then body="$arg"; fi\n'
        '  prev="$arg"\n'
        'done\n'
        'if [ -z "$body" ] || [ ! -f "$body" ]; then\n'
        '  echo "stub gh: --body-file missing or not a file: [$body]" >&2\n'
        '  exit 9\n'
        'fi\n'
        'printf "%s\\n" "$*" >> "$STUB_LOG"\n'
        'printf "body-from:%s\\n" "$(cat "$body")" >> "$STUB_LOG"\n'
        'exit 0\n',
        encoding="utf-8")
    stub.chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("", encoding="utf-8")
    return bin_dir, log


def _run_post_step(tmp_path: Path, issue_list: list[dict], digest_text: str) -> str:
    """Run the audit step, then the digest-issue step, and return what `gh` was asked to do."""
    gh_bin, log = _stub_gh(tmp_path)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    # 1) the audit step writes $RUNNER_TEMP/audit_digest.md from the python3 stub
    py_bin, stub_digest = _stub_python3(tmp_path, digest_text, EXIT_FLIP)
    audit_env = child_env(
        PATH=f"{py_bin}:{POSIX_PATH}",   # python3 is the audit stub here
        RUNNER_TEMP=str(tmp_path),
        GITHUB_OUTPUT=str(output),
        STUB_DIGEST=str(stub_digest),
        STUB_STATUS=str(EXIT_FLIP),
    )
    _run_block(_step("audit")["run"], audit_env)
    # 2) the post step must find that same file — a drift in the path fails the stub's file check.
    # `python3` is the real interpreter here: this step's only python is the JSON one-liner.
    post_env = child_env(
        PATH=f"{gh_bin}:{POSIX_PATH}",
        RUNNER_TEMP=str(tmp_path),
        STUB_LOG=str(log),
        STUB_ISSUES=json.dumps(issue_list),
    )
    proc = _run_block(_step("digest-issue")["run"], post_env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return log.read_text(encoding="utf-8")


@BASH_ONLY
def test_the_digest_issue_is_updated_rather_than_duplicated(tmp_path):
    """The issue list used to be parsed twice from one stdin, failing on the first week it mattered."""
    log = _run_post_step(tmp_path, [{"number": 42}], FLIP_DIGEST)

    assert "issue comment 42" in log, log
    assert "issue create" not in log, log
    assert "body-from:" + FLIP_DIGEST.strip() in log, log


@BASH_ONLY
def test_the_first_finding_creates_the_digest_issue(tmp_path):
    log = _run_post_step(tmp_path, [], FLIP_DIGEST)

    assert "issue create" in log, log
    assert "intake-kind-audit,needs-human-review" in log, log
    assert "issue comment" not in log, log


def test_the_grep_is_a_second_signal_not_the_verdict():
    """The old workflow's only judgment was a grep. It must no longer be the failure condition."""
    audit = _step("audit")
    assert "status=$?" in audit["run"], "the step has to capture the script's exit status"
    assert "GITHUB_OUTPUT" in audit["run"]

    gate = _step("gate")
    assert gate["if"].strip() == "steps.audit.outputs.verdict != 'pass'", gate["if"]
    assert "exit 1" in gate["run"]
    assert "GITHUB_STEP_SUMMARY" in gate["run"]
