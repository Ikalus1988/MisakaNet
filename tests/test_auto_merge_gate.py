#!/usr/bin/env python3
"""The Auto-Merge Gate compared two different API spellings and could never merge (#1826).

`gh api …/pulls/N --jq '.mergeable'` reads the **REST** field, a JSON boolean: `true`, `false`, or
`null` while GitHub is still computing it. The line then compared it to `"MERGEABLE"`, which is the
**GraphQL** enum spelling. The two are never equal, so the gate skipped every PR:

    Mergeable: true
    Not mergeable. Skipping.

"All green PRs auto-merge" was therefore a branch that could not be reached — the whole history
contains no `Auto-merge #N` commit. The same mistake had already been made and fixed once in
`scripts/lesson_pr_mergeable.py`, whose docstring is the canonical explanation and whose
`mergeable_is_clean()` is the helper Python callers use. This test pins both sides so the trap cannot
be re-set in either language.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

from scripts.lesson_pr_mergeable import mergeable_is_clean  # noqa: E402
from posix_shell import require_posix_shell  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PR_CHECKS = REPO / ".github" / "workflows" / "pr-checks.yml"


def _code(script: str) -> str:
    """Executable lines only — the comments name the constructs these tests forbid."""
    return "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))


def _gate_step() -> dict:
    workflow = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Auto-Merge Gate":
                return step
    raise AssertionError("the Auto-Merge Gate step disappeared — #1826 tracked it as dead, not unwanted")


def _gate_script() -> str:
    return _gate_step()["run"]


def test_the_gate_reads_the_rest_boolean_not_the_graphql_enum():
    script = _gate_script()
    assert "--jq '.mergeable'" in script, "the gate reads the REST pull request, so the value is a boolean"
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
    assert '"MERGEABLE"' not in code and "'MERGEABLE'" not in code, (
        "comparing a REST boolean to the GraphQL enum is the bug in #1826: it is always unequal, "
        "so the gate can never merge anything"
    )
    # Exactly `true` counts. `null` means GitHub has not computed it yet, and treating that as
    # mergeable would merge a conflicted PR.
    assert re.search(r'\[ "\$MERGEABLE" = "true" \]', code), "only the boolean true is mergeable"


def test_the_gates_that_must_stay_between_mergeable_and_merging_stay():
    script = _gate_script()
    code = _code(script)
    # Lesson content is executed by agents: an auto-merged attacker-authored lesson is a poisoning
    # vector (2026-08-30 security gate).
    assert "lessons/" in script, "the lessons/ human-merge gate must not be dropped"
    # Unchecked acceptance criteria mean the PR does not claim to be finished. The pattern is
    # escaped inside the shell double quotes, so match the code that greps for it.
    assert "UNCHECKED" in script and r'\[ \]' in script
    assert "gh pr merge" in script and "--auto" in script, (
        "the gate must enable GitHub's auto-merge (which waits for required checks), not merge directly"
    )
    # A conventional-looking merge subject makes release-please list the merge commit *and* the
    # branch commit it merged: every auto-merged PR showed up twice in the next release notes.
    assert "--subject" not in code, (
        "let GitHub write the default merge subject ('Merge pull request #N from …'): it is not a "
        "conventional commit, so release-please skips it instead of duplicating the changelog entry"
    )


def test_both_spellings_are_understood_by_the_python_helper_but_only_one_is_clean():
    # The helper is deliberately lenient (it accepts the enum form so a GraphQL caller cannot
    # silently disable a channel), while `null` — GitHub still computing — is never clean.
    assert mergeable_is_clean(True) is True
    assert mergeable_is_clean("MERGEABLE") is True
    assert mergeable_is_clean(False) is False
    assert mergeable_is_clean(None) is False
    assert mergeable_is_clean("UNKNOWN") is False


def test_a_release_pull_request_is_not_auto_merged():
    """The one PR a person should read before it ships.

    On 2026-09-20 this gate merged the 2.32.0 release PR while the maintainer was still reviewing its
    changelog — which held 30 duplicated entries and shipped as-is. The duplication is caught separately
    (`tests/test_changelog_shape.py`); what this asserts is that somebody gets the chance to look: a release
    PR carries the version bump and the changelog that becomes the release notes, and it is prepared by a
    bot, so nothing human has read it yet.

    Both signals are asserted because they cover different windows: release-please applies
    `autorelease: pending` to the PR it opens, and the branch name is there even before that label lands.
    """
    script = _gate_script()
    assert "autorelease:" in script, (
        "the gate does not look at the `autorelease:` label, so a release PR can be merged by a bot")
    assert "release-please--" in script, (
        "the gate does not check the branch name, so a release PR opened without the label yet can be "
        "merged by a bot")
    assert re.search(r'case "\$PR_LABELS"', script) and re.search(r'case "\$PR_BRANCH"', script), (
        "the release checks are not wired to a skip path")


def _gate_script_of(path):
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == "Auto-Merge Gate":
                return step["run"]
    raise AssertionError(f"no Auto-Merge Gate step in {path}")


def test_the_release_check_notices_a_stripped_guard(tmp_path):
    """A rule that cannot fail is not a rule: strip the branch check and the assertion must notice."""
    import shutil

    scratch = tmp_path / "repo"
    (scratch / ".github" / "workflows").mkdir(parents=True)
    victim = scratch / ".github" / "workflows" / "pr-checks.yml"
    shutil.copy(PR_CHECKS, victim)
    victim.write_text(victim.read_text(encoding="utf-8").replace("release-please--", "some-branch-"),
                      encoding="utf-8")
    mutated = _gate_script_of(victim)
    assert "release-please--" not in mutated, "the mutation did not take"
    assert "autorelease:" in mutated, "the label check survived, so only the branch check is under test"


# ── Fork PRs: the gate was red-checking the contributors we ask for (#1952, #1954) ──────────────
#
# A `pull_request` run from a fork gets a read-only GITHUB_TOKEN and no repository secrets, so the
# `gh pr merge --auto` at the end of the gate answered
# `GraphQL: Resource not accessible by integration (mergePullRequest)`. The step exits non-zero, the
# whole `audit` job goes red — and `audit` is the one check contributors are told to trust. On
# 2026-09-20 that is exactly what happened to #1952 and #1954, whose test suite was fully green
# ("1638 passed"): the only thing wrong with them was that they came from a fork.
#
# The tests below *run the real script* with a stub `gh` rather than pattern-matching its text, and
# the mutation case reproduces the CI failure before the fix, because "the guard is present" and
# "the guard is what keeps the audit green" are different claims.

_GH_STUB = """#!/usr/bin/env bash
# Records every call and mimics only what the Auto-Merge Gate asks for.
echo "$*" >> "$GH_STUB_LOG"
if [ "$1" = "api" ]; then
  case "$*" in
    *--jq*".mergeable"*) echo "true"; exit 0 ;;
    *"--jq"*"labels[].name"*) echo ""; exit 0 ;;
    *--jq*".head.ref"*) echo "feature-branch"; exit 0 ;;
    *--jq*".body"*) printf -- '- [x] everything done\\n'; exit 0 ;;
  esac
  exit 0
fi
if [ "$1" = "pr" ] && [ "$2" = "diff" ]; then
  printf '%s\\n' "${GH_STUB_CHANGED_FILES:-}"
  exit 0
fi
if [ "$1" = "pr" ] && [ "$2" = "merge" ]; then
  # A fork run holds a read-only token: this is the real GitHub answer, verbatim from run logs.
  if [ "${GH_READ_ONLY:-0}" = "1" ]; then
    echo "GraphQL: Resource not accessible by integration (mergePullRequest)"
    exit 1
  fi
  # A PAT without the `workflow` scope cannot enable auto-merge on a PR that edits CI. Verbatim
  # from #1964's run.
  if printf '%s\\n' "${GH_STUB_CHANGED_FILES:-}" | grep -q '^\\.github/workflows/'; then
    echo 'GraphQL: Pull request refusing to allow a Personal Access Token to create or update workflow `.github/workflows/pr-checks.yml` without `workflow` scope (enablePullRequestAutoMerge)'
    exit 1
  fi
  exit 0
fi
exit 0
"""


def _run_gate(tmp_path, *, fork: bool, read_only: bool, mutate=None, changed_files=(), gh_token=None):
    """Execute the Auto-Merge Gate step's real shell, against a stub `gh`.

    `gh_token=None` keeps the stub credential. An empty string is the case the step's `-z "$GH_TOKEN"`
    guard exists for, and it has to be settable *to* empty — hence a value-oriented parameter and the
    mapping form below, never a keyword argument spelled next to a quoted value (that assignment shape
    is what `tests/test_scanner_secret_patterns.py` scans for, and it caught this line once).
    """
    import os
    import subprocess

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(_GH_STUB, encoding="utf-8")
    gh.chmod(0o755)
    log = tmp_path / "gh-calls.log"
    log.write_text("", encoding="utf-8")

    script = _gate_script()
    # The step's only two Actions expressions; the rest of the step is plain shell.
    script = script.replace("${{ github.event.pull_request.head.repo.full_name }}",
                            "someone/MisakaNet" if fork else "Ikalus1988/MisakaNet")
    script = script.replace("${{ github.repository }}", "Ikalus1988/MisakaNet")
    assert "${{" not in script, "an unsubstituted Actions expression would be a shell syntax error"
    if mutate is not None:
        script = mutate(script)

    body = tmp_path / "step.sh"
    body.write_text(script, encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "PATH": f"{bin_dir}:{env['PATH']}",
        "GH_STUB_LOG": str(log),
        "GH_READ_ONLY": "1" if read_only else "0",
        "GH_STUB_CHANGED_FILES": "\n".join(changed_files),
        "GH_TOKEN": "stub-token" if gh_token is None else gh_token,
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "PR_NUM": "1952",
        "PR_TITLE": "docs: fix 23 broken relative links",
    })
    proc = subprocess.run([require_posix_shell(), "-e", str(body)], capture_output=True, text=True, env=env)
    return proc, log.read_text(encoding="utf-8"), (tmp_path / "summary.md")


def test_a_fork_pull_request_skips_auto_merge_instead_of_failing_the_audit(tmp_path):
    proc, calls, summary = _run_gate(tmp_path, fork=True, read_only=True)
    assert proc.returncode == 0, (
        "the gate must not fail the audit for a fork PR — that is the #1952/#1954 false red:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    assert "pr merge" not in calls, "a fork run must not even attempt `gh pr merge` with a read-only token"
    assert "Fork PR" in proc.stdout and "maintainer" in proc.stdout, "the skip must say why, in the log"
    assert "fork" in summary.read_text(encoding="utf-8").lower(), (
        "the step summary is the part a maintainer reads; it must say the PR was skipped for a fork")


def test_the_same_repo_channel_still_merges(tmp_path):
    """The fork guard must not switch the channel off for the PRs it was built for."""
    proc, calls, _ = _run_gate(tmp_path, fork=False, read_only=False,
                               changed_files=("docs/index.html", "tests/test_auto_merge_gate.py"))
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "pr merge" in calls, "a same-repo, green, AC-checked PR must still have auto-merge enabled"
    assert "Release PR" not in proc.stdout


# ── A PR that edits CI: same shape, different credential limit (#1964) ──────────────────────────
#
# `SHELDON_PAT` has no `workflow` scope, so GitHub refuses to let it enable auto-merge on a PR that
# changes a workflow file — "refusing to allow a Personal Access Token to create or update workflow…
# without `workflow` scope (enablePullRequestAutoMerge)". #1964 hit it with every real gate green
# ("Mergeable: true / Changed lesson files: 0 / Unchecked AC items: 0") and the `audit` check went red
# for a credential's limitation. Same rule as forks: enabling auto-merge is a convenience, not a gate.


def test_a_pull_request_that_edits_ci_skips_auto_merge_without_failing_the_audit(tmp_path):
    proc, calls, summary = _run_gate(tmp_path, fork=False, read_only=False,
                                     changed_files=(".github/workflows/pr-checks.yml",
                                                    "tests/test_audit_report_truth.py"))
    assert proc.returncode == 0, (
        "a CI-editing PR must not fail the audit because a PAT lacks the `workflow` scope:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    assert "pr merge" not in calls, (
        "the merge must not even be attempted once the file list says the token cannot enable it")
    assert "workflow" in proc.stdout, "the skip must name the scope that is missing"
    assert "workflow" in summary.read_text(encoding="utf-8").lower(), (
        "the summary is what a maintainer reads; it must carry the reason")


def test_a_pull_request_that_only_touches_lessons_still_skips_for_lessons(tmp_path):
    """The two skips must not be confused: the lessons/ rule is a security gate, not a credential one."""
    proc, calls, _ = _run_gate(tmp_path, fork=False, read_only=False,
                               changed_files=("lessons/contrib/example.md",))
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "pr merge" not in calls
    assert "lessons/" in proc.stdout and "human merge" in proc.stdout


def test_stripping_the_ci_file_skip_reproduces_the_ci_failure(tmp_path):
    """Mutation: without the CI-file skip the very same run goes red — that was #1964."""
    def strip(script: str) -> str:
        # Line-based: the YAML block scalar removes the leading indentation, so matching on the
        # indented source text would silently fail to mutate (and a mutation that does not mutate
        # asserts nothing).
        lines = script.splitlines(keepends=True)
        start = next(i for i, l in enumerate(lines) if "A PR that changes a workflow" in l)
        end = next(i for i, l in enumerate(lines) if "Release PRs are the one artifact" in l)
        assert start < end, "the two markers are in the wrong order"
        return "".join(lines[:start] + lines[end:])

    proc, calls, _ = _run_gate(tmp_path, fork=False, read_only=False, mutate=strip,
                               changed_files=(".github/workflows/pr-checks.yml",))
    assert proc.returncode != 0, "without the skip the step must fail — this is the state #1964 was in"
    assert "pr merge" in calls, "the mutation has to reach the merge attempt, or it proves nothing"
    assert "without `workflow` scope" in proc.stdout


def test_stripping_the_fork_guard_reproduces_the_ci_failure(tmp_path):
    """Mutation: remove the fork check and the very same run goes red again — on a fork PR."""
    def strip(script: str) -> str:
        start = script.index("HEAD_REPO=")
        end = script.index("# Fork PRs are already gone by now")
        return script[:start] + script[end:]

    proc, calls, _ = _run_gate(tmp_path, fork=True, read_only=True, mutate=strip)
    assert proc.returncode != 0, (
        "without the fork guard the step must fail — this is the state #1952 and #1954 were in")
    assert "pr merge" in calls, "the mutation has to reach the merge attempt, or it proves nothing"
    assert "Resource not accessible" in proc.stdout + proc.stderr


# ── The fallback token, and a guard that could not be reached ───────────────────────────────────────
#
# The step's env was `GH_TOKEN: ${{ secrets.SHELDON_PAT || secrets.GITHUB_TOKEN }}`, and the guard it
# documents — "no token at all (a missing secret on a same-repo run) … report, do not fail" — tested
# `-z "$GH_TOKEN"`. `secrets.GITHUB_TOKEN` is never empty, so the second operand always won and the
# guard was dead code: a PAT-less same-repo run went on to `gh pr merge --auto` holding a token this job
# deliberately scopes to `contents: read` (`contents: write` is what a merge needs, and what the audit
# job must not have — see below). The answer is the read-only
# `Resource not accessible by integration` that the fork guard exists to prevent: the same red check on
# a PR whose every real gate passed, reached by a different route.
#
# Two ways to "fix" it, and only one is right:
#
#   * give the audit job `contents: write` — rejected. This job runs the pull request's own test suite,
#     so write access to the repository would let a branch that entered through `adopt-pr` rewrite
#     `main` from inside a test. Least privilege is the property, not an inconvenience.
#   * drop the fallback, so the step runs with the PAT or with nothing — which is what the guard was
#     always written for. Enabling auto-merge is a convenience, not a gate.

def test_the_audit_job_keeps_a_read_only_token():
    """The regression guard for the tempting fix: this job executes the PR's code."""
    permissions = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))["jobs"]["audit"]["permissions"]
    assert permissions.get("contents") == "read", (
        f"the audit job now has {permissions.get('contents')!r} on `contents`. It runs `pytest` over the "
        "pull request, so `contents: write` lets a test rewrite the repository — a merge needs write "
        "access, and that is why the merge step uses a PAT instead of widening this job"
    )
    assert permissions.get("issues") == "write" and permissions.get("pull-requests") == "write", (
        f"the report comment and the review writes need these scopes: {permissions}")


def test_the_merge_step_does_not_fall_back_to_the_github_token():
    token = _gate_step()["env"]["GH_TOKEN"]
    assert "SHELDON_PAT" in token, f"the merge credential changed ({token!r}) — a PAT is what can merge here"
    assert "GITHUB_TOKEN" not in token, (
        f"the step falls back to GITHUB_TOKEN again ({token!r}). That operand is never empty, so the "
        "`-z \"$GH_TOKEN\"` guard below it can never fire and a PAT-less run merges with a token scoped to "
        "`contents: read` — a red audit for a credential reason"
    )


def test_a_run_without_a_pat_skips_instead_of_failing_the_audit(tmp_path):
    """The guard the fallback made unreachable, exercised with the empty token it looks for."""
    proc, calls, _ = _run_gate(tmp_path, fork=False, read_only=True, gh_token="")
    assert proc.returncode == 0, (
        "a missing PAT must not fail the audit — that is the red-with-no-cause shape this file keeps "
        f"having to fix:\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    assert "pr merge" not in calls, "with no credential there is nothing to merge with, so do not try"
    assert "GH_TOKEN is empty" in proc.stdout, "the skip has to name the missing secret"
    assert "Auto-merge skipped" in proc.stdout, "and it has to be an annotation, not a silent exit"


def test_the_read_only_token_is_what_used_to_turn_the_audit_red(tmp_path):
    """The mutation half: with *a* token the merge attempt reaches GitHub, and the read-only answer
    fails the step — exactly where the removed fallback left a PAT-less run."""
    proc, calls, _ = _run_gate(tmp_path, fork=False, read_only=True)
    assert proc.returncode != 0, f"the read-only answer must fail the step:\n{proc.stdout}"
    assert "pr merge" in calls, "the run has to reach the merge attempt, or it proves nothing"
    assert "Resource not accessible" in proc.stdout + proc.stderr
