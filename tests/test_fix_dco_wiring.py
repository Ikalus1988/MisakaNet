#!/usr/bin/env python3
"""The DCO help text, the DCO auto-fix, and the token the auto-fix pushes with — one chain, three bugs.

Measured 2026-09-25 on PR #2201/#2202, in order:

1. `dco-audit` posts a failure comment whose body *contains the string* ``/fix-dco`` as instruction
   ("Same-repo PRs can also comment ``/fix-dco`` to auto-apply the sign-off.").
2. `fix-dco.yml` triggers on `contains(comment.body, '/fix-dco')` — so its own receipt ran the auto-fix
   without anyone asking.
3. The auto-fix force-pushed with the built-in `GITHUB_TOKEN`, and GitHub created the new head's
   `pull_request: synchronize` runs as **held** (`action_required`, `actor=github-actions[bot]`).
   `DCO / Signed-off-by` is one of the three required checks on `main`, so the PR then sat at
   "Expected — waiting for status to be reported" for ever: the fix for a missing sign-off is what made
   the PR unmergeable. The repository already knew this shape —
   `lessons/contrib/ci-github-token-push-does-not-trigger-workflows.md` — and `auto-sync-prs.yml`
   solves it by pushing with a PAT.
4. The comment that started it all listed **no commits**: the action's comment step read
   `steps.scan.outputs.failed-commits-log` while the scan step writes `failed_commits_log`, and an
   unresolved output name is the empty string, not an error. It also printed its `\\n` separators
   literally.

This file executes the action's two shell steps against a real temporary git repository, so the receipt
is checked as rendered text rather than as a template, and it holds the push identity and trigger as
properties.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from posix_shell import require_posix_shell
from subprocess_env import POSIX_PATH, child_env

REPO = Path(__file__).resolve().parents[1]
ACTION = REPO / ".github" / "actions" / "dco-audit" / "action.yml"
WORKFLOW = REPO / ".github" / "workflows" / "fix-dco.yml"

pytestmark = pytest.mark.skipif(
    not shutil.which("git"), reason="these steps drive git; without it they prove nothing"
)


def _bash() -> str:
    """The shell the action's steps declare (`shell: bash`), not merely a POSIX one.

    The scan step uses process substitution, and running it under `dash` would be testing a script
    GitHub never runs.
    """
    shell = require_posix_shell()
    if "bash" not in Path(shell).name:
        found = shutil.which("bash")
        if not found:
            pytest.skip(f"the action's steps declare `shell: bash`; {shell} is not bash and no bash exists")
        return found
    return shell


def _action() -> dict:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def _step(name_start: str) -> dict:
    for step in _action()["runs"]["steps"]:
        if (step.get("name") or "").startswith(name_start):
            return step
    raise AssertionError(f"no step named like {name_start!r} in {ACTION.name}")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=120,
                          env=child_env({"GIT_CONFIG_GLOBAL": os.devnull,
                                         "GIT_CONFIG_NOSYSTEM": "1",
                                         "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
                                         "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com"}),
                          check=True).stdout.strip()


def _repo_with_one_unsigned_commit(tmp_path: Path) -> tuple[Path, str, str]:
    """A repo whose range has a signed commit, an unsigned one, and nothing else."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "f.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-s", "-m", "signed base")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "f.txt").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "forgot the trailer")
    unsigned = _git(repo, "rev-parse", "HEAD")
    return repo, base, unsigned


def _substitute(script: str, values: dict[str, str]) -> str:
    """What GitHub does to `run:` before bash sees it: resolve `${{ … }}`, unknown → empty string."""
    def resolve(match: re.Match) -> str:
        return values.get(match.group(1).strip(), "")

    return re.sub(r"\$\{\{\s*([^}]+?)\s*\}\}", resolve, script)


def _scan_outputs(repo: Path, base: str, head: str, tmp_path: Path) -> dict[str, str]:
    """Run the scan step for real and read back the outputs it wrote."""
    out = tmp_path / "gh_output"
    out.write_text("", encoding="utf-8")
    script = _substitute(_step("Scan DCO")["run"], {
        "inputs.base-sha": base, "inputs.head-sha": head,
    })
    proc = subprocess.run([_bash(), "-c", script], cwd=repo, capture_output=True, text=True,
                          timeout=120,
                          env=child_env({"GITHUB_OUTPUT": str(out), "HOME": str(tmp_path)}))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = out.read_text(encoding="utf-8")

    outputs: dict[str, str] = {}
    for match in re.finditer(r"^([\w-]+)=(.*)$", text, re.M):
        outputs[match.group(1)] = match.group(2)
    for match in re.finditer(r"^([\w-]+)<<(\w+)\n(.*?)\n\2$", text, re.M | re.S):
        outputs[match.group(1)] = match.group(3)
    return outputs


def _render_comment(repo: Path, outputs: dict[str, str], tmp_path: Path) -> str:
    """Run the comment step and return the file it wrote — the text a contributor would see."""
    scan = f"{_step('Scan DCO')['id']}"
    values = {
        "inputs.pr-number": "2201", "inputs.repo": "Ikalus1988/MisakaNet", "inputs.token": "stub",
        # Only outputs the scan step actually wrote resolve; anything else is empty, as on GitHub.
        **{f"steps.{scan}.outputs.{name}": value for name, value in outputs.items()},
    }
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir(exist_ok=True)
    script = _substitute(_step("Post DCO Failure Comment")["run"], values)
    subprocess.run([_bash(), "-c", script], cwd=repo, capture_output=True, text=True, timeout=120,
                   env=child_env({"RUNNER_TEMP": str(runner_temp), "HOME": str(tmp_path),
                                  "GH_TOKEN": "stub", "PATH": f"{runner_temp}:{POSIX_PATH}"}))
    written = runner_temp / "dco_comment.md"
    assert written.exists(), "the comment step wrote nothing — check RUNNER_TEMP handling"
    return written.read_text(encoding="utf-8")


# ── the receipt names the offending commits ─────────────────────────────────────────
def test_the_dco_failure_comment_names_the_commit_that_is_missing_sign_off(tmp_path):
    repo, base, unsigned = _repo_with_one_unsigned_commit(tmp_path)
    outputs = _scan_outputs(repo, base, unsigned, tmp_path)
    assert outputs.get("dco_passed") == "false", outputs
    assert outputs.get("failed_count") == "1", outputs

    body = _render_comment(repo, outputs, tmp_path)
    assert "misakanet-dco-block" in body, body
    assert unsigned[:7] in body, (
        "the comment that tells a contributor what to fix does not say which commit — this is the "
        f"hyphen/underscore output-name bug (`failed-commits-log` vs `failed_commits_log`):\n{body}")
    assert "forgot the trailer" in body, body
    assert "\\n" not in body, "the offender list is being printed with literal backslash-n separators"


def test_the_comment_is_only_posted_when_the_gate_is_red():
    """A failure comment on a passing PR is worse than none: it teaches the wrong fix."""
    condition = str(_step("Post DCO Failure Comment").get("if") or "")
    assert "dco_passed == 'false'" in condition, condition
    assert "inputs.pr-number" in condition, condition


# ── the auto-fix must not be triggered by its own help text ─────────────────────────
def _trigger_condition() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return str(workflow["jobs"]["fix-dco"]["if"])


def test_the_help_text_that_teaches_fix_dco_is_not_the_command(tmp_path):
    """The bug in one line: the receipt telling a contributor about `/fix-dco` also *was* `/fix-dco`."""
    repo, base, unsigned = _repo_with_one_unsigned_commit(tmp_path)
    body = _render_comment(repo, _scan_outputs(repo, base, unsigned, tmp_path), tmp_path)
    assert "/fix-dco" in body, "the comment no longer teaches the command — update this test, not the rule"
    condition = _trigger_condition()
    assert "misakanet-dco-block" in condition, (
        "fix-dco triggers on `contains(body, '/fix-dco')`, and dco-audit's own failure comment contains "
        "that string as help text — so every DCO failure silently runs the auto-fix. The condition must "
        f"exclude the audit's comment:\n{condition}")


# ── the push must be one whose runs are allowed to run ──────────────────────────────
def _push_step() -> dict:
    for step in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["fix-dco"]["steps"]:
        if "git push" in (step.get("run") or ""):
            return step
    raise AssertionError(f"no step in {WORKFLOW.name} pushes")


def test_the_force_push_does_not_authenticate_with_the_built_in_token():
    """A `GITHUB_TOKEN` push creates held runs, and `DCO / Signed-off-by` is a required check."""
    step = _push_step()
    run = step["run"]
    references = set(re.findall(r"x-access-token:\$\{?(\w+)\}?", run))
    assert references, "the push no longer builds an authenticated remote URL — re-check this rule"
    env = step.get("env") or {}
    for variable in references:
        value = str(env.get(variable, ""))
        assert value, f"{variable} is used to push but is not defined in the step's env"
        assert "secrets.GITHUB_TOKEN" not in value, (
            f"the force push authenticates with GITHUB_TOKEN ({variable}={value}); GitHub creates the "
            "new head's runs as `action_required` (held), which leaves this PR stuck at "
            "'Expected — waiting for status to be reported' because DCO is a required check")


def test_the_push_skips_instead_of_pushing_with_a_token_that_would_strand_the_pr(tmp_path):
    """With no PAT the step must not push at all: a held head is worse than a red one."""
    step = _push_step()
    workdir = tmp_path / "pr-code"
    workdir.mkdir()
    _git(workdir, "init", "-q")
    (workdir / "f.txt").write_text("x\n", encoding="utf-8")
    _git(workdir, "add", "f.txt")
    _git(workdir, "commit", "-q", "-s", "-m", "c")
    before = _git(workdir, "rev-parse", "HEAD")
    _git(workdir, "remote", "add", "origin", "https://example.invalid/does-not-exist.git")

    env = dict(step.get("env") or {})
    for key in list(env):
        env[key] = "" if "SHELDON" in str(env[key]) else "stub"
    env["PUSH_TOKEN"] = ""
    script = _substitute(step["run"], {"steps.pr.outputs.headRef": "some-branch",
                                       "github.repository": "Ikalus1988/MisakaNet"})
    # The timeout is load-bearing: with the guard removed this step tries to reach github.com, and a
    # test that *hangs* on the mutation is a test nobody can trust to fail.
    proc = subprocess.run([_bash(), "-c", script], cwd=workdir, capture_output=True, text=True,
                          timeout=30,
                          env=child_env({**env, "HOME": str(tmp_path),
                                         "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"}))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SHELDON_PAT is empty" in proc.stdout, proc.stdout
    assert _git(workdir, "rev-parse", "HEAD") == before


def test_the_checkout_does_not_leave_a_second_authorization_header_behind():
    """`persist-credentials: true` + a PAT push = two Authorization headers, and the server picks the
    checkout's — the workflow then believes it pushed as the PAT while the runs say `[bot]`."""
    checkout = [s for s in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["fix-dco"]["steps"]
                if str(s.get("uses", "")).startswith("actions/checkout")]
    assert checkout, "fix-dco no longer checks out the PR branch — re-check this rule"
    assert (checkout[0].get("with") or {}).get("persist-credentials") is False, checkout[0].get("with")


def test_the_workflow_can_still_be_triggered_by_a_human_command():
    """The exclusion must not have been achieved by disabling the feature."""
    condition = _trigger_condition()
    assert "contains(github.event.comment.body, '/fix-dco')" in condition, condition
    assert "github.event.issue.pull_request" in condition, condition
    assert json.dumps(["MEMBER", "OWNER", "COLLABORATOR"]) in condition, condition
