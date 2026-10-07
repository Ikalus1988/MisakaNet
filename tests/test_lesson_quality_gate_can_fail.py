#!/usr/bin/env python3
"""`lesson-quality.yml` must be able to go red — and must not report a clean corpus about a lint
it never managed to read.

`grep -n 'exit 1' .github/workflows/lesson-quality.yml` returned nothing for the whole file, and
the `lint-check` job carried `continue-on-error: true` while the lint step itself ended in
`|| true`. The answer of `--fail-on high` was therefore discarded twice over: once by the shell,
once by the job. #2940 §4.

There was a second failure of the same shape hiding inside the same step, which is why this file
does not stop at "there is an `exit` somewhere":

    python scripts/lesson_lint.py … > lint-output.json 2>&1 || true
    HIGH=$(python -c "json.load(open('lint-output.json')) …" 2>/dev/null || echo "0")

`2>&1` folds stderr into a file the next line parses as JSON, and `|| echo "0"` then turns a
failed parse into **zero high-severity issues**. A lint that crashed — or one that wrote a
diagnostic to stderr — reported "High: 0 | Medium: 0 | Low: 0". That is the same substitution as a
credential scanner printing "no secrets found" about a file it never opened (#2971), and the same
one `mcp_preflight.py` performed on a corrupt lesson index (#2940 §3).

The static half pins the shape; the behavioural half *runs the extracted step* under `bash -e` in a
sandbox holding a real copy of `scripts/lesson_lint.py`, because "the workflow contains an exit"
is not the claim — "the step exits non-zero when there is something to report" is.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "lesson-quality.yml"

sys.path.insert(0, str(REPO / "tests"))
from posix_shell import require_posix_shell  # noqa: E402


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lint_step_body(workflow: dict) -> str:
    step = next(s for s in workflow["jobs"]["lint-check"]["steps"] if s["name"] == "Run lesson lint")
    return step["run"]


def _commands(body: str) -> list:
    """The step's commands, with its comments dropped.

    The step explains *why* `|| true` and `|| echo "0"` had to go, so asserting their absence
    against the raw text matches the prose describing the fix. A static gate has to read the
    commands, not the commentary about them.
    """
    return [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


# ── the static shape ────────────────────────────────────────────────────────

def test_lint_job_has_no_continue_on_error(workflow):
    assert "continue-on-error" not in workflow["jobs"]["lint-check"], (
        "a job-level continue-on-error makes every step inside it advisory, whatever the step does"
    )


def test_the_lint_exit_status_is_captured_not_discarded(lint_step_body):
    commands = _commands(lint_step_body)
    assert any("lint_status=$?" in c for c in commands), (
        "the lint's exit code must be captured; `|| true` or a bare invocation under `bash -e` "
        "means the counts below never run when there is something to report, and the job never fails"
    )
    assert not any("|| true" in c for c in commands)


def test_the_step_exits_with_the_lint_status(lint_step_body):
    commands = _commands(lint_step_body)
    assert commands[-1] == 'exit "$lint_status"', (
        "the step's last command must carry the lint's verdict to the job; "
        f"found: {commands[-1]!r}"
    )


def test_stderr_is_not_folded_into_the_parsed_json(lint_step_body):
    for line in _commands(lint_step_body):
        if "lint-output.json" in line:
            assert "2>&1" not in line, (
                "stderr folded into a file the next command parses as JSON corrupts the parse, "
                f"and the old `|| echo 0` turned that into 'High: 0': {line!r}"
            )


def test_an_unreadable_count_file_is_not_counted_as_zero(lint_step_body):
    # The fallback that made a broken parse mean "no issues" is the thing to forbid.
    commands = _commands(lint_step_body)
    assert not any('|| echo "0"' in c or "|| echo 0" in c for c in commands)


# ── the step actually runs, and actually fails ──────────────────────────────

def _sandbox(tmp_path: pathlib.Path, dirty: bool) -> pathlib.Path:
    """A repo-shaped tree holding a real copy of lesson_lint.py and a lessons corpus."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "lessons" / "core").mkdir(parents=True)
    shutil.copy2(REPO / "scripts" / "lesson_lint.py", root / "scripts" / "lesson_lint.py")
    # A lesson that passes every rule, so the clean case is clean for a reason.
    shutil.copy2(
        REPO / "lessons" / "core" / "allowlist-must-be-tested-against-the-corpus.md",
        root / "lessons" / "core" / "good.md",
    )
    if dirty:
        (root / "lessons" / "core" / "zz-no-frontmatter.md").write_text(
            "a lesson body with no frontmatter at all\n", encoding="utf-8"
        )
    return root


def _run_step(tmp_path: pathlib.Path, root: pathlib.Path, body: str):
    """Execute the step body the way Actions does: `bash -e`, real GITHUB_OUTPUT / SUMMARY."""
    shell = require_posix_shell()
    work = tmp_path / f"run-{root.name}"
    work.mkdir()
    script = work / "step.sh"
    script.write_text(body, encoding="utf-8")

    # Actions' `python` is the one setup-python installed. Pin it to the interpreter running the
    # suite so the result does not depend on what happens to be first on this machine's PATH.
    shim = work / "bin"
    shim.mkdir()
    (shim / "python").symlink_to(sys.executable)
    (shim / "python3").symlink_to(sys.executable)

    outputs = work / "gh_output"
    summary = work / "gh_summary"
    outputs.write_text("", encoding="utf-8")
    summary.write_text("", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"
    env["GITHUB_OUTPUT"] = str(outputs)
    env["GITHUB_STEP_SUMMARY"] = str(summary)

    done = subprocess.run(
        [shell, "-e", str(script)], cwd=root, env=env, capture_output=True, text=True
    )
    return done, outputs.read_text(encoding="utf-8"), summary.read_text(encoding="utf-8")


def _counts(outputs: str) -> dict:
    parsed = {}
    for line in outputs.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def test_the_step_passes_on_a_clean_corpus_and_publishes_counts(tmp_path, lint_step_body):
    done, outputs, summary = _run_step(tmp_path, _sandbox(tmp_path, dirty=False), lint_step_body)
    assert done.returncode == 0, f"stdout={done.stdout}\nstderr={done.stderr}"
    assert _counts(outputs) == {"high": "0", "medium": "0", "low": "0"}
    assert "Lesson Lint Report" in summary


def test_the_step_goes_red_on_a_high_severity_issue(tmp_path, lint_step_body):
    done, outputs, summary = _run_step(tmp_path, _sandbox(tmp_path, dirty=True), lint_step_body)

    assert done.returncode != 0, (
        "the step went green on a corpus holding a lesson with no frontmatter — this is the "
        "defect #2940 §4 reports"
    )
    # The report is the point of the step; a failure must not cost us the counts.
    assert _counts(outputs).get("high") == "1", f"outputs were {outputs!r}"
    assert "High: 1" in summary


def test_a_corrupt_lint_output_is_not_reported_as_zero_issues(tmp_path, lint_step_body):
    """The `|| echo "0"` chain: a count file that cannot be parsed used to mean 'no issues'."""
    root = _sandbox(tmp_path, dirty=False)
    # A lint whose stdout is not the JSON the step goes on to parse. Pointing the step at a
    # `scripts/lesson_lint.py` that emits a diagnostic line reproduces `2>&1`'s effect without
    # putting stderr back into the command.
    (root / "scripts" / "lesson_lint.py").write_text(
        "import sys\nsys.stdout.write('warning: something went sideways\\n')\n"
        "sys.stdout.write('not json\\n')\nsys.exit(0)\n",
        encoding="utf-8",
    )
    done, outputs, _ = _run_step(tmp_path, root, lint_step_body)

    assert done.returncode != 0, f"a count file that will not parse was accepted: {outputs!r}"
    assert "high=0" not in outputs, (
        "an unparseable count file must not be published as zero high-severity issues"
    )