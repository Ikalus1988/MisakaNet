#!/usr/bin/env python3
"""The npm publish runs itself on a release, and refuses to ship a version nobody released.

History, because the arrangement below replaced an earlier one on purpose (2026-09-30, owner decision
D1 = A) and the reasons are what keep it from regressing:

* On 2026-09-20 the npm bundle line was at 2.30.2 while the repository and PyPI were at 2.31.0. The
  cause was structural rather than forgetfulness: **nothing wrote that line**. `misakanet-publish.yml`
  was `workflow_dispatch`-only, and the alignment was mentioned solely inside an error message
  ("fix with: python3 scripts/align_versions.py --source $TAG_VERSION") that a human had to read.
  The repair was to *move* the line inside the publish run and *record* it afterwards through a PR.
* On 2026-09-30 the line joined release-please (`extra-files` → `{"type": "json", "path":
  "package.json", "jsonpath": "$.version"}`), so a writer exists *before* the tag does: the release PR
  carries the bump, and the release commit is the tree that is tagged. That made both halves of the
  old repair wrong rather than redundant. A publish job that rewrites the version it is about to
  publish can put a fresh number on old bytes — the stale-bundle failure the guard below exists to
  refuse — and a job that records the version *after* publishing is bookkeeping for a fact the release
  PR already wrote.

So what these tests pin now:

* the release flow still **dispatches** the publish (a release cannot be forgotten), and a
  **published release** also triggers it directly, so the publish does not depend on the dispatch
  surviving a lost event (measured failure mode: a `GITHUB_TOKEN` push cannot trigger workflows, so a
  trigger can look right and never fire — `publish-mcp-registry.yml`'s header records it);
* the publish job **fails loudly** when `package.json` disagrees with the version that was released,
  which is executed for real below rather than string-matched;
* the job declares its own environment (`npm-release`), so an unattended publish cannot un-gate the
  `release` environment that `deploy-worker.yml` waits on — two trust boundaries, two environments;
* the job **does not write the tree**: no `align_versions`, no commit, no push. release-please is the
  writer now, and a publisher that also writes is two writers for one fact;
* both trigger paths fire for the same release, so the second run has to be a no-op instead of a red
  run (npm cannot publish a version twice).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from posix_shell import require_posix_shell

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
PUBLISH = WORKFLOWS / "misakanet-publish.yml"
RELEASE_PLEASE = WORKFLOWS / "release-please.yml"

GUARD = "The released version is the one in package.json"


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on_block(workflow: dict) -> dict:
    """The `on:` mapping. PyYAML resolves the bare key `on` to the boolean True (YAML 1.1)."""
    block = workflow.get("on") or workflow.get(True) or {}
    return block if isinstance(block, dict) else {}


def _steps(path: Path) -> list[dict]:
    steps: list[dict] = []
    for job in _workflow(path)["jobs"].values():
        steps.extend(job.get("steps", []))
    return steps


def _step(path: Path, needle: str) -> dict:
    for step in _steps(path):
        if needle in (step.get("name") or ""):
            return step
    raise AssertionError(f"no step matching {needle!r} in {path.name}")


def _index_of(path: Path, needle: str) -> int:
    for index, step in enumerate(_steps(path)):
        if needle.lower() in (step.get("name") or "").lower():
            return index
    raise AssertionError(f"no step matching {needle!r} in {path.name}")


def _publish_condition(path: Path) -> str:
    return next((step.get("if") or "" for step in _steps(path)
                 if "Publish to npm" in (step.get("name") or "")), "")


# Markers that mean "this job writes the repository". Checked against the *scripts*, not the prose:
# this file's header talks about commits and pushes, and a rule satisfied by a comment would be a rule
# that cannot fail.
TREE_WRITE_MARKERS = ("align_versions", "git commit", "git push", "git add ", "gh pr create")


def _wiring_problems(root: Path) -> list[str]:
    """Every way this arrangement can be broken, checked against whatever tree is passed in."""
    publish = root / ".github" / "workflows" / "misakanet-publish.yml"
    release_please = root / ".github" / "workflows" / "release-please.yml"
    problems: list[str] = []

    # 1. the release flow has to start it, with the version that was released
    dispatches = [
        (step.get("run") or "")
        for step in _steps(release_please)
        if "misakanet-publish.yml" in (step.get("run") or "")
    ]
    if not dispatches:
        problems.append("release-please.yml never dispatches misakanet-publish.yml")
    elif not any("version=" in run for run in dispatches):
        problems.append("the dispatch does not pass a version, so the publish run cannot know what to ship")

    spec = _workflow(publish)
    triggers = _on_block(spec)
    dispatch_trigger = triggers.get("workflow_dispatch") or {}

    # 2. the human gate stays
    job = spec["jobs"]["publish"]
    environment = job.get("environment")
    environment = environment.get("name") if isinstance(environment, dict) else environment
    # Its **own** environment, not `release`: `release` also gates `deploy-worker.yml`, so publishing
    # unattended there would un-gate production worker deploys as a side effect (intake #2486, D1 = A —
    # the orchestrator created `npm-release` with no required reviewer and branch policies `main` + `v*`).
    if environment != "npm-release":
        problems.append(
            f"the publish job declares environment={environment!r}; unattended publishing needs an "
            "environment without a required reviewer, and it must not be `release` (which gates worker "
            "deploys) — see the workflow header")

    # 3. a version input exists, and every way of starting the run can reach the publish step
    if "version" not in (dispatch_trigger.get("inputs") or {}):
        problems.append("workflow_dispatch has no `version` input, so there is no way to publish a release")
    if "workflow_dispatch" not in triggers:
        problems.append("workflow_dispatch is gone, so a manual republish has no escape hatch")
    # A release is published by `release-please.yml` (`gh release create`), and the publish has to follow
    # it without another workflow remembering to dispatch. A tag trigger is not a substitute: the tag is
    # pushed with GITHUB_TOKEN, and a GITHUB_TOKEN push creates no workflow run at all.
    release_trigger = triggers.get("release")
    types = (release_trigger or {}).get("types") if isinstance(release_trigger, dict) else None
    if types != ["published"]:
        problems.append(
            f"`on.release` is {release_trigger!r}; a published release must start this workflow "
            "directly (`on: release: types: [published]`), or the only path from a release to npm is "
            "another workflow's dispatch surviving")
    condition = _publish_condition(publish)
    if "github.event_name == 'release'" not in condition:
        problems.append(
            f"the publish step's condition is {condition!r}; it cannot be reached by the release event, "
            "so the automatic trigger would run every check and publish nothing")
    if "inputs.version" not in condition and "github.event_name == 'push'" not in condition:
        problems.append("the publish step cannot be reached by a version dispatch or a tag push")

    # 4. the guard runs, and runs before anything is published
    try:
        guard = _index_of(publish, "The released version is the one in package.json")
        publish_at = _index_of(publish, "Publish to npm")
    except AssertionError as error:
        problems.append(str(error))
    else:
        if not guard < publish_at:
            problems.append(
                "the version guard runs at or after `npm publish`, which is the one thing it exists to "
                "prevent: a stale bundle under a fresh number")
        guard_run = _steps(publish)[guard].get("run") or ""
        for needed in ("package.json", "exit 1"):
            if needed not in guard_run:
                problems.append(f"the guard script does not mention {needed!r}, so it cannot be checking it")

    # 5. the publisher does not write the tree — release-please is the writer
    perms = job.get("permissions") or spec.get("permissions") or {}
    if perms.get("contents") != "read":
        problems.append(
            f"the job asks for contents: {perms.get('contents')!r}; publishing needs no write access, "
            "and the write scope is what a publish-back step would hide behind")
    for step in _steps(publish):
        run = step.get("run") or ""
        found = [marker for marker in TREE_WRITE_MARKERS if marker in run]
        if found:
            problems.append(
                f"step {step.get('name')!r} writes the tree ({', '.join(found)}); release-please owns "
                "package.json now, and a publish that rewrites the version it publishes can ship stale "
                "bytes under a fresh number")

    # 6. two triggers fire for one release, so the second run must stand down instead of failing
    skip = next((step for step in _steps(publish)
                 if "already" in (step.get("name") or "").lower()), None)
    if skip is None:
        problems.append(
            "no step checks whether npm already has the version; the release event and the dispatch "
            "both fire for the same release, and a second `npm publish` of it fails the run")
    elif "already" not in (skip.get("run") or ""):
        problems.append("the already-published step does not record an output, so nothing can act on it")
    elif "npm_state.outputs.already" not in _publish_condition(publish):
        problems.append("the publish step ignores the already-published check")
    return problems


def test_the_publish_is_wired_end_to_end():
    problems = _wiring_problems(REPO)
    assert not problems, (
        "the automatic npm publish is broken in these ways:\n  - " + "\n  - ".join(problems))


def _scratch_workflows(tmp_path: Path) -> Path:
    scratch = tmp_path / "repo"
    (scratch / ".github" / "workflows").mkdir(parents=True)
    for path in (PUBLISH, RELEASE_PLEASE):
        shutil.copy(path, scratch / ".github" / "workflows" / path.name)
    return scratch


def _scratch_publish(tmp_path: Path):
    """A scratch copy plus a loader/saver for its workflow, so a mutation is structural, not textual."""
    scratch = _scratch_workflows(tmp_path)

    def load():
        path = scratch / ".github" / "workflows" / "misakanet-publish.yml"
        return path, yaml.safe_load(path.read_text(encoding="utf-8"))

    def save(path: Path, data: dict) -> None:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    return scratch, load, save


def test_the_wiring_check_notices_a_publish_that_nobody_starts(tmp_path):
    """Guard the guard: drop the dispatch and the rule must fail, or it is decoration."""
    scratch = _scratch_workflows(tmp_path)
    assert _wiring_problems(scratch) == [], "the copied tree must start clean"

    release_please = scratch / ".github" / "workflows" / "release-please.yml"
    release_please.write_text(
        release_please.read_text(encoding="utf-8").replace("misakanet-publish.yml", "some-other.yml"),
        encoding="utf-8")
    assert any("never dispatches" in problem for problem in _wiring_problems(scratch))


def test_the_wiring_check_notices_a_lost_release_trigger(tmp_path):
    """The automatic half is a trigger, so removing the trigger must be what the rule reports."""
    scratch, load, save = _scratch_publish(tmp_path)
    assert _wiring_problems(scratch) == [], "the copied tree must start clean"

    path, data = load()
    triggers = data.get("on") or data.get(True)
    assert "release" in triggers, "the trigger this test removes is not there to remove"
    del triggers["release"]
    save(path, data)
    assert any("on.release" in problem for problem in _wiring_problems(scratch))


def test_the_wiring_check_notices_a_lost_approval_gate(tmp_path):
    scratch = _scratch_workflows(tmp_path)
    publish = scratch / ".github" / "workflows" / "misakanet-publish.yml"
    publish.write_text(
        publish.read_text(encoding="utf-8").replace("    environment: npm-release\n", ""),
        encoding="utf-8")
    assert any("unattended publishing needs an environment" in problem for problem in _wiring_problems(scratch)), (
        "removing the environment must be reported as a lost gate, not silently accepted")


def test_the_wiring_check_notices_a_publish_that_writes_the_tree(tmp_path):
    """The half of the old arrangement that had to go: a publisher that moves the line it publishes.

    Replayed on the step that used to do it (`align_versions.py --source $VERSION`, removed
    2026-09-30), because that step is exactly how a version nobody released could end up on npm.
    """
    scratch, load, save = _scratch_publish(tmp_path)
    assert _wiring_problems(scratch) == [], "the copied tree must start clean"

    path, data = load()
    steps = data["jobs"]["publish"]["steps"]
    steps.insert(1, {"name": "Move the npm line to the version being published",
                     "run": 'python3 scripts/align_versions.py --source "$EXPECTED"'})
    save(path, data)
    assert any("writes the tree" in problem for problem in _wiring_problems(scratch)), (
        "a step that runs align_versions.py inside the publish job must be reported")


# ── the guard, executed ─────────────────────────────────────────────────────────────────────────────
# The rule above proves a step *named* like a guard exists and mentions `package.json`. That is not the
# same claim as "a mismatch fails the job", and this repository has been burned by tests that assert on
# wording instead of mechanism. So the guard's script is lifted out of the workflow and run: a scratch
# `package.json`, the environment variables the workflow passes, and the exit code as the verdict.

def _guard_script() -> str:
    return _step(PUBLISH, GUARD)["run"]


def _run_guard(tmp_path: Path, package_version: str, **env: str) -> subprocess.CompletedProcess:
    tree = tmp_path / "tree"
    tree.mkdir(parents=True, exist_ok=True)
    (tree / "package.json").write_text(
        json.dumps({"name": "misakanet", "version": package_version}) + "\n", encoding="utf-8")
    script = tmp_path / "guard.sh"
    script.write_text(_guard_script(), encoding="utf-8")
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", ""),
        "GITHUB_OUTPUT": str(output),
        # The exact keys the workflow's guard step passes through `env:`; a rename on either side has to
        # break this test rather than the guard's ability to read the event.
        "EVENT_NAME": "", "RELEASE_TAG": "", "REF_TYPE": "", "REF_NAME": "", "REQUESTED_VERSION": "",
    }
    environment.update(env)
    # A usable POSIX shell or a skip that names the problem: on Windows `bash` is the WSL launcher and
    # fails with "no installed distributions", which is an environment fact rather than a test result
    # (2026-09-30 — the first version of these tests reported exactly that on three Windows legs).
    shell = require_posix_shell()
    return subprocess.run([shell, str(script)], cwd=tree, env=environment,
                          capture_output=True, text=True)


def test_a_release_whose_version_the_tree_does_not_carry_fails_the_job(tmp_path):
    """The guard's whole purpose: an automatic run can never publish a stale bundle."""
    failure = _run_guard(tmp_path / "mismatch", "2.38.0", EVENT_NAME="release", RELEASE_TAG="v2.39.0")
    assert failure.returncode != 0, (
        f"package.json 2.38.0 with release v2.39.0 published anyway:\n{failure.stdout}{failure.stderr}")
    combined = failure.stdout + failure.stderr
    assert "::error::" in combined, "a mismatch must reach the Actions error annotation"
    for value in ("2.39.0", "2.38.0"):
        assert value in combined, f"the error must name both versions, got: {combined}"


def test_a_release_the_tree_carries_passes_and_reports_the_version(tmp_path):
    """The negative fixture: without it, the test above passes for a guard that always fails."""
    ok = _run_guard(tmp_path / "match", "2.39.0", EVENT_NAME="release", RELEASE_TAG="v2.39.0")
    assert ok.returncode == 0, f"a matching release must pass:\n{ok.stdout}{ok.stderr}"
    assert "version=2.39.0" in (tmp_path / "match" / "github_output").read_text(encoding="utf-8"), (
        "the version the later steps publish has to come from this step's output")


def test_the_guard_reads_every_trigger_it_can_be_started_by(tmp_path):
    """Three spellings reach the same job: a published release, a `misakanet-v*` tag push, a dispatch."""
    tag = _run_guard(tmp_path / "tag", "2.39.0",
                     EVENT_NAME="push", REF_TYPE="tag", REF_NAME="misakanet-v2.39.0")
    assert tag.returncode == 0, f"the documented tag push must pass:\n{tag.stdout}{tag.stderr}"

    stale_tag = _run_guard(tmp_path / "stale-tag", "2.39.0",
                           EVENT_NAME="push", REF_TYPE="tag", REF_NAME="misakanet-v2.38.0")
    assert stale_tag.returncode != 0, "a tag that disagrees with package.json must not publish"

    dispatched = _run_guard(tmp_path / "dispatch", "2.39.0", EVENT_NAME="workflow_dispatch", REQUESTED_VERSION="2.39.0")
    assert dispatched.returncode == 0, f"a version dispatch must pass:\n{dispatched.stdout}{dispatched.stderr}"

    wrong_dispatch = _run_guard(tmp_path / "wrong-dispatch", "2.38.0",
                               EVENT_NAME="workflow_dispatch", REQUESTED_VERSION="2.39.0")
    assert wrong_dispatch.returncode != 0, (
        "a dispatch that names a version the tree does not carry must fail, not move the line")


def test_a_manual_dispatch_without_a_version_still_publishes_what_the_tree_says(tmp_path):
    """The escape hatch: republishing a tree by hand does not require naming a version.

    Nothing to compare against, so the guard says so (`::warning::`) instead of inventing a verdict —
    and the version the job publishes still comes from `package.json`, which is why the output is
    written on every path.
    """
    manual = _run_guard(tmp_path / "manual", "2.39.0", EVENT_NAME="workflow_dispatch")
    assert manual.returncode == 0, f"a dry-run dispatch must not fail on the guard:\n{manual.stdout}{manual.stderr}"
    assert "::warning::" in manual.stdout + manual.stderr, (
        "an unverifiable run must say it could not check, not report success")
    assert "version=2.39.0" in (tmp_path / "manual" / "github_output").read_text(encoding="utf-8")


# ── the already-published check, executed ───────────────────────────────────────────────────────────
# Its verdict decides whether the publish step runs at all, and it reads a *registry* — a live network
# call, which is exactly why the parsing has to be pinned here with a stub instead: a test that needed
# npmjs would be a test that fails for the weather.

def _stub_npm(tmp_path: Path, stdout: str, exit_code: int = 0) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    npm = bin_dir / "npm"
    # A failure speaks on stderr, like npm does (`npm error 404 ...`); a success prints the version.
    stream = " >&2" if exit_code else ""
    npm.write_text(f"#!/bin/bash\nprintf '%s\\n' {stdout!r}{stream}\nexit {exit_code}\n", encoding="utf-8")
    npm.chmod(0o755)
    return bin_dir


def _run_skip_step(tmp_path: Path, stdout: str, exit_code: int = 0) -> tuple[int, str, str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    script = tmp_path / "skip.sh"
    script.write_text(_step(PUBLISH, "already has this version")["run"], encoding="utf-8")
    bin_dir = _stub_npm(tmp_path, stdout, exit_code)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    environment = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "HOME": os.environ.get("HOME", ""),
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
        "VERSION": "2.39.0",
    }
    shell = require_posix_shell()
    proc = subprocess.run([shell, str(script)], cwd=tmp_path, env=environment,
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout, output.read_text(encoding="utf-8")


def test_the_already_published_check_reads_the_registry_and_stands_down(tmp_path):
    code, out, recorded = _run_skip_step(tmp_path / "hit", "2.39.0")
    assert code == 0, f"{out}"
    assert "already=true" in recorded, (
        "a version npm already has must make the publish step stand down, or the second trigger of one "
        f"release fails the run; recorded: {recorded!r}")


def test_the_already_published_check_lets_a_new_version_through(tmp_path):
    for name, stdout, rc in (("missing", "", 1), ("other", "2.38.0", 0)):
        code, out, recorded = _run_skip_step(tmp_path / name, stdout, rc)
        assert code == 0, f"{name}: {out}"
        assert "already=false" in recorded, (
            f"{name}: only the exact version counts, other output must not stop a publish; "
            f"recorded: {recorded!r}")


def test_the_already_published_check_is_not_a_precondition(tmp_path):
    """A registry read that fails must not stop the run — the publish step is the loud path.

    An `npm view` that 404s (the version is not published) and one that cannot reach the registry both
    exit non-zero; if the step failed on either, a first publish could never happen.
    """
    code, out, recorded = _run_skip_step(tmp_path / "error", "npm error 404 Not Found", 1)
    assert code == 0, f"a failing registry read must not fail the step: {out}{recorded}"
    assert "already=false" in recorded, recorded
    assert "npm view:" in out, (
        "the read's stderr should reach the log, so a wrong verdict is diagnosable: " + out)


# ── release-please bookkeeping that predates this change and still has to hold ──────────────────────

def test_the_release_flow_marks_its_release_pr_as_tagged():
    """Tagging the commit is only half the bookkeeping, and the missing half blocks the next release.

    `release-please.yml` skips release-please's own release creation (v5 refuses it for these tokens) and
    tags the commit itself. But the action's release-creation code is *also* what moves the release PR from
    `autorelease: pending` to `autorelease: tagged`, and the action decides whether a merged release PR is
    "outstanding" by that **label**, not by the tag. So on 2026-09-20 every run since the 2.31.0 release
    aborted with

        ⚠ There are untagged, merged release PRs outstanding - aborting

    and no new release PR was proposed until #1862 was relabelled by hand — the same manual step that had
    cleared the 2.30.0 deadlock (#1631), two releases in a row.
    """
    steps = _steps(RELEASE_PLEASE)
    flip = [s for s in steps if "autorelease: tagged" in (s.get("run") or "")]
    assert flip, (
        "no step moves a merged release PR from `autorelease: pending` to `autorelease: tagged`, so the "
        "next release-please run will abort and the release after that cannot be prepared")
    script = flip[0]["run"]
    assert "autorelease: pending" in script, "the step must remove the pending label it is replacing"
    # Gated on `created == 'true'` this would repair nothing in the state the repository was actually in:
    # the tag existed and only the label was wrong. The step has to be unconditional (and idempotent).
    condition = flip[0].get("if") or ""
    assert "created" not in condition, (
        "the relabel step runs only when this run created the tag, so a release whose tag already exists "
        "but whose label is still pending stays stuck forever")


def test_the_relabel_step_is_not_merely_defined(tmp_path):
    scratch = tmp_path / "repo"
    (scratch / ".github" / "workflows").mkdir(parents=True)
    for path in (PUBLISH, RELEASE_PLEASE):
        shutil.copy(path, scratch / ".github" / "workflows" / path.name)
    release_please = scratch / ".github" / "workflows" / "release-please.yml"
    release_please.write_text(
        release_please.read_text(encoding="utf-8").replace("autorelease: tagged", "autorelease: whatever"),
        encoding="utf-8")
    assert not [s for s in _steps(release_please) if "autorelease: tagged" in (s.get("run") or "")], (
        "the mutation did not take, so the assertion above proves nothing")


# ── the release must carry the npm line, because the publish no longer moves it ──────────────────────
# The dispatch passes `version=$VERSION` and the publish refuses a mismatch, so the release flow has to be
# the thing that puts the right number in `package.json` — that is release-please's `extra-files` entry,
# and `tests/test_version_consistency.py` holds the value side. This holds the other end: the dispatch
# must name the same version the manifest says, or every automatic release fails at the guard.

def test_the_dispatch_names_the_version_the_tree_carries():
    dispatch = _step(RELEASE_PLEASE, "Dispatch the npm publish")
    assert dispatch["if"] == "steps.release_tag.outputs.created == 'true'", (
        "an unconditional dispatch would republish the same version on every push to main")
    assert "gh workflow run misakanet-publish.yml" in dispatch["run"]
    assert dispatch["env"]["VERSION"] == "${{ steps.release_tag.outputs.version }}", (
        "the release flow knows the version it just tagged; pass it so the publish can refuse a "
        "mismatch instead of publishing whatever is in the tree")
    assert '-f "version=$VERSION"' in dispatch["run"]
    assert "${{" not in dispatch["run"], (
        "no expression may be interpolated into the dispatched shell command")

# ── trusted publishing: the job must be able to authenticate with no token at all (D1, 2026-09-30) ───
# npm's docs: trusted publishing needs npm CLI >= 11.5.1 and Node >= 22.14; the CLI "automatically detects
# OIDC environments and uses them for authentication before falling back to traditional tokens"; GitHub
# exposes `ACTIONS_ID_TOKEN_REQUEST_URL` when the job asks for `id-token: write`. These rules pin the three
# things that make the migration real rather than aspirational: the permission, the toolchain floor, and an
# identity step that does not demand a secret it no longer needs.

def test_the_publish_job_can_authenticate_without_a_long_lived_token():
    spec = yaml.safe_load(PUBLISH.read_text(encoding="utf-8"))
    workflow_permissions = spec.get("permissions") or {}
    job_permissions = (spec["jobs"]["publish"].get("permissions") or {})
    granted = {**workflow_permissions, **job_permissions}
    assert granted.get("id-token") == "write", (
        f"the publish job does not grant `id-token: write` (granted: {granted}); without it there is no "
        "OIDC token to exchange and the release still depends on a long-lived secret")


def test_the_toolchain_meets_the_trusted_publishing_floor():
    spec = yaml.safe_load(PUBLISH.read_text(encoding="utf-8"))
    steps = spec["jobs"]["publish"]["steps"]
    node = next((s for s in steps if str(s.get("uses", "")).startswith("actions/setup-node")), None)
    assert node, "the publish job no longer pins a Node version"
    version = str((node.get("with") or {}).get("node-version", ""))
    major = int(re.match(r"\d+", version).group()) if re.match(r"\d+", version) else 0
    # npm CLI >= 11.5.1 requires Node >= 22.14; a bare major >= 22 resolves to the newest 22.x, so the
    # floor is expressed as "22 or newer" rather than pinning a patch.
    assert major >= 22, (
        f"node-version is {version!r}; trusted publishing requires Node >= 22.14 (npm CLI >= 11.5.1), and "
        "Node 24 is what the npm docs' example uses")


def _run_identity_step(tmp_path: Path, **env: str):
    """Execute the real 'Check npm identity' step, with a stubbed npm on PATH."""
    step = next(s for s in yaml.safe_load(PUBLISH.read_text(encoding="utf-8"))["jobs"]["publish"]["steps"]
                if s.get("name") == "Check npm identity")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "npm").write_text('#!/bin/bash\nif [ "$1" = "whoami" ]; then echo "ci-bot"; exit 0; fi\necho "9.9.9"\n', encoding="utf-8")
    (bin_dir / "npm").chmod(0o755)
    (bin_dir / "node").write_text('#!/bin/bash\necho "v24.0.0"\n', encoding="utf-8")
    (bin_dir / "node").chmod(0o755)
    script = tmp_path / "identity.sh"
    script.write_text(step["run"], encoding="utf-8")
    environment = {"PATH": f"{bin_dir}:{os.environ['PATH']}", "HOME": os.environ.get("HOME", "")}
    environment.update(env)
    shell = require_posix_shell()
    return subprocess.run([shell, str(script)], cwd=tmp_path, env=environment, capture_output=True, text=True)


def test_the_identity_step_accepts_oidc_when_no_token_is_present(tmp_path):
    """The point of the migration: a release must be publishable with the secret deleted."""
    proc = _run_identity_step(tmp_path / "oidc", ACTIONS_ID_TOKEN_REQUEST_URL="https://oidc.example/token",
                              NODE_AUTH_TOKEN="")
    assert proc.returncode == 0, (
        "the identity step refused to continue although OIDC was available — that would keep the release "
        f"dependent on NPM_TOKEN:\n{proc.stdout[-400:]}{proc.stderr[-300:]}")
    assert "trusted publishing" in proc.stdout


def test_the_identity_step_still_fails_loudly_with_neither_mechanism(tmp_path):
    """Positive control: removing the fallback must not turn a missing credential into a silent pass."""
    proc = _run_identity_step(tmp_path / "nothing", ACTIONS_ID_TOKEN_REQUEST_URL="", NODE_AUTH_TOKEN="")
    assert proc.returncode != 0, proc.stdout
    assert "Neither trusted publishing" in proc.stdout and "npm-release" in proc.stdout, proc.stdout


def test_the_identity_step_keeps_the_token_diagnostics(tmp_path):
    """The transitional path is still the one most releases will use until the npm side is configured."""
    proc = _run_identity_step(tmp_path / "token", ACTIONS_ID_TOKEN_REQUEST_URL="", NODE_AUTH_TOKEN="npm_x")
    assert proc.returncode == 0, proc.stdout
    assert "token fallback" in proc.stdout, proc.stdout
# ── every workflow that publishes to npm must be able to do it without a long-lived secret ───────────
# There are three publishing workflows (`misakanet`, `@misaka-net/misakanet-setup`, `@misaka-net/fatal-guard`)
# and they shared one `NPM_TOKEN`. Migrating only the first would have left the other two unable to publish
# through trusted publishing — and, worse, deleting the token afterwards would have broken them. So the rule
# is repo-wide: any job whose steps run `npm publish` must grant `id-token: write` and run on a Node that
# meets npm's trusted-publishing floor (CLI >= 11.5.1, i.e. Node >= 22.14).

def publish_auth_problems(workflow_dir: Path) -> list[str]:
    """Jobs that run `npm publish` without the means to authenticate through OIDC."""
    problems: list[str] = []
    found = 0
    for path in sorted(workflow_dir.glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (spec.get("jobs") or {}).items():
            steps = job.get("steps") or []
            if not any("npm publish" in str(step.get("run") or "") for step in steps):
                continue
            found += 1
            granted = {**(spec.get("permissions") or {}), **(job.get("permissions") or {})}
            if granted.get("id-token") != "write":
                problems.append(
                    f"{path.name}:{job_name} runs `npm publish` without `id-token: write`, so npm trusted "
                    "publishing cannot authenticate it (the release then depends on a long-lived secret)")
            node = next((s for s in steps if str(s.get("uses", "")).startswith("actions/setup-node")), None)
            version = str(((node or {}).get("with") or {}).get("node-version", ""))
            major = int(re.match(r"\d+", version).group()) if re.match(r"\d+", version) else 0
            if major < 22:
                problems.append(
                    f"{path.name}:{job_name} pins Node {version!r}; trusted publishing needs npm CLI >= 11.5.1, "
                    "which means Node >= 22.14")
            # A publish step that cannot name its two credentials fails as a bare 401 instead.
            publish_run = "\n".join(str(step.get("run") or "") for step in steps if "npm publish" in str(step.get("run") or ""))
            if "ACTIONS_ID_TOKEN_REQUEST_URL" not in publish_run and "NODE_AUTH_TOKEN" not in str(steps):
                problems.append(
                    f"{path.name}:{job_name} neither detects an OIDC environment nor passes a token to "
                    "`npm publish`, so a missing credential surfaces as an unexplained 401")
    if found == 0:
        problems.append(f"no workflow in {workflow_dir.name}/ runs `npm publish` — this rule would be vacuous")
    return problems


def test_every_publishing_workflow_can_authenticate_without_a_long_lived_secret():
    problems = publish_auth_problems(WORKFLOWS)
    assert not problems, "\n  - ".join(["publishing workflows that cannot use trusted publishing:"] + problems)


def test_the_publish_auth_rule_notices_a_token_only_workflow(tmp_path):
    """Guard: the rule reads the real workflow directory, so its red case needs a fixture."""
    (tmp_path / "token-only.yml").write_text(
        "permissions:\n  contents: read\njobs:\n  publish:\n    steps:\n"
        "      - uses: actions/setup-node@v7\n        with:\n          node-version: \"20\"\n"
        "      - name: Publish\n        run: npm publish --access public\n", encoding="utf-8")
    problems = publish_auth_problems(tmp_path)
    assert any("id-token" in p for p in problems), problems
    assert any("Node '20'" in p for p in problems), problems
    (tmp_path / "good.yml").write_text(
        "permissions:\n  contents: read\n  id-token: write\njobs:\n  publish:\n    steps:\n"
        "      - uses: actions/setup-node@v7\n        with:\n          node-version: \"24\"\n"
        "      - name: Publish\n        run: |\n          if [ -n \"${ACTIONS_ID_TOKEN_REQUEST_URL:-}\" ]; then true; fi\n"
        "          npm publish --access public\n        env:\n          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}\n",
        encoding="utf-8")
    (tmp_path / "token-only.yml").unlink()
    assert publish_auth_problems(tmp_path) == []
