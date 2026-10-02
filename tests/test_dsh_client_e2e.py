#!/usr/bin/env python3
"""The DSH client e2e gate must keep doing the things that made it worth adding.

`tests/e2e/run_client_e2e.py` is the only check in this repository that runs the client half in a real host
and a real browser, so the ways it can quietly become useless are worth pinning:

* a scenario renamed or dropped leaves the suite green while covering less;
* a `pkill -f "<port>"` creeps back in — this repository has killed its own shell twice that way, because the
  pattern matches the invoking command line;
* the library is no longer intercepted, so the gate starts depending on the public site being reachable;
* a fresh `DSH_HOME` opens its first-run modals and mounts the composer inert, and a suite that does not handle
  both simply times out with no explanation;
* the seeded workspace record loses a field its schema requires, so the domain drops it and the composer stays
  a chooser — the failure that looked like "a fresh profile cannot create a first session";
* the runner goes back to *driving the workspace chooser*, which is what hid that rejection in the first place;
* the workflow grows a `paths:` filter on `pull_request`, which `lesson-gate.yml` already documents as the way
  a gate goes missing on the PRs it skips (GitHub leaves them at "Expected" forever).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow")

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tests" / "e2e" / "run_client_e2e.py"
WORKFLOW = REPO / ".github" / "workflows" / "dsh-client-e2e.yml"
CI_DOC = REPO / "docs" / "CI.md"


def script_text() -> str:
    assert SCRIPT.is_file(), "the e2e runner is the whole point of this gate"
    return SCRIPT.read_text(encoding="utf-8")


def workflow() -> dict:
    assert WORKFLOW.is_file(), "the workflow is how the runner reaches CI"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_three_scenarios_are_still_named_and_driven():
    text = script_text()
    for name in ("slash-overlay", "frame-wide-toast", "settings-to-panel"):
        assert f'"{name}"' in text, f"the {name} scenario is gone or renamed"
    # each one is a function, and main() runs all three
    for function in ("scenario_slash_overlay", "scenario_frame_wide_toast", "scenario_settings_to_panel"):
        assert f"def {function}(" in text, f"{function} is missing"
    assert text.count("lambda:") >= 3, "main() no longer drives the scenarios"


def test_it_never_kills_its_host_by_pattern():
    text = script_text()
    assert "pkill" not in text, (
        "pkill -f matches the invoking shell's own command line; this repo has killed its own shell twice")
    assert "lsof" in text and "tcp:" in text, "the host must be stopped by the port it actually listens on"


def test_the_library_is_intercepted_so_the_gate_is_hermetic():
    text = script_text()
    assert 'page.route("**/api/lessons*"' in text, "the lesson library must be answered from the fixture"
    assert "route.fulfill" in text, "an interception that never fulfils is a hang, not a fixture"
    # and it asserts the request the page actually made, which is the contract worth pinning
    assert "q=pip" in text and "limit=" in text, "the scenario must assert endpoint, q and limit"


def test_a_fresh_profile_is_made_usable():
    text = script_text()
    assert "seed_workspace" in text and "workspace.json" in text, (
        "a fresh DSH_HOME has no workspace, and the composer mounts inert without one")
    assert "Configure later" in text, (
        "a fresh profile asks for an API key; the suite must decline it rather than need credentials")
    assert "Continue" in text, "the Preview Notice is the other first-run modal"


def test_the_seeded_workspace_record_carries_the_fields_its_schema_requires():
    """The bug that hid behind "a fresh profile cannot create a session" was two missing fields.

    The workspace domain validates every stored record, and `createdAt` / `updatedAt` are required. The first
    version of `seed_workspace` omitted them, so the record was dropped, the profile came up with no usable
    workspace, and the composer stayed a chooser — with no error message anywhere the suite could see. This
    asserts the fields are written, and that the runner does not go back to *driving the chooser*, which is
    what made the rejection invisible for a day.
    """
    text = script_text()
    assert '"createdAt": now' in text and '"updatedAt": now' in text, (
        "the workspace record must carry createdAt/updatedAt; without them the domain drops it")
    assert "wait_for_live_composer" in text, (
        "the composer must be asserted live, with a stub reported as a failure")
    assert "choose_workspace" not in text and "ensure_session" not in text, (
        "driving the workspace chooser masks a rejected workspace record; the host creates the first session")


def test_the_suite_runs_on_pull_requests_now_that_it_can_pass():
    """It was manual and nightly while a fresh profile could not reach a live composer; that is fixed.

    The promotion is `pull_request:` **without** a `paths:` filter — a filtered workflow reports nothing for
    the PRs it skips and GitHub leaves them waiting forever (`lesson-gate.yml` carries that measurement). The
    run/scope decision lives inside the job instead, so every PR gets a result either way. Whether the check
    is *required* is a ruleset change, which is why this only asserts the trigger.
    """
    data = workflow()
    triggers = data.get("on") or data.get(True) or {}
    assert "pull_request" in triggers, (
        "the composer blocker is fixed (see seed_workspace); the PR trigger belongs back")
    assert "paths" not in (triggers.get("pull_request") or {}), (
        "a paths: filter leaves the skipped PRs at 'Expected' forever — filter inside the job instead")
    assert "workflow_dispatch" in triggers and "schedule" in triggers, "keep a manual and a nightly path"


def test_the_workflow_pins_what_it_installs_and_uploads_evidence():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r'DSH_VERSION:\s*"\d+\.\d+\.\d+-rc\.\d+"', text), "pin the DSH release explicitly"
    assert "tests/e2e/run_client_e2e.py" in text, "the workflow must call the runner"
    assert "upload-artifact" in text, "screenshots are the evidence a failure needs"
    for used in re.findall(r"uses:\s*(\S+)", text):
        assert re.search(r"@[0-9a-f]{40}$", used), f"{used} is not pinned to a commit"


def test_the_ci_page_lists_the_workflow():
    """`tests/test_workflow_inventory.py` owns the rule; this says why it matters here."""
    assert "dsh-client-e2e.yml" in CI_DOC.read_text(encoding="utf-8"), (
        "every workflow must appear in docs/CI.md, and this one is a gate people will look for")


def _scope_step_run() -> str:
    """The `run:` body of the step that decides whether the suite is worth running."""
    data = workflow()
    for step in data["jobs"]["client-e2e"]["steps"]:
        if step.get("name") == "Decide whether the client half moved":
            return step["run"]
    raise AssertionError("the scope step was renamed — this test reads it to check what ships")


def test_the_scope_step_never_fetches_the_base_branch_shallowly():
    """`--depth=1` on the ref being compared against removes the merge base the diff needs.

    Measured 2026-10-02 on #2697, the first pull request to exercise the restored `pull_request`
    trigger: the step fetched `origin/main` with `--depth=1` and the next command died with
    `fatal: origin/main...HEAD: no merge base` (exit 128), so the check went red on every PR before
    the suite had started. The checkout's `fetch-depth: 0` is undone by a shallow fetch of the very
    ref the comparison names.
    """
    run = _scope_step_run()
    # Only real fetch commands count: the step's own comment names `--depth=1` to explain the trap,
    # and an assertion on the raw text would fail on that documentation.
    shallow = [line.strip() for line in run.splitlines()
               if line.strip().startswith("git fetch") and "--depth" in line]
    assert not shallow, (
        "the scope step fetches the base branch shallowly again, which breaks the three-dot diff "
        f"below it: {shallow}")
    assert "fetch-depth: 0" in WORKFLOW.read_text(encoding="utf-8"), "the checkout needs the full graph"


def test_the_scope_step_runs_the_suite_when_it_cannot_decide(tmp_path):
    """Behavioural, not a source check: execute the step with a base ref that cannot be fetched.

    That is the same shape as the CI failure above (the comparison could not be made). The step must
    decide to **run** the suite — with a warning — and exit 0, because a probe that cannot see the
    change is not evidence that the client half is untouched, and a red check here hides the failures
    the suite exists to find. Only the suite itself may fail this job.

    Removing either `|| fail_open` turns this red: the unguarded form exits non-zero (measured 1).
    """
    script = _scope_step_run()
    script = script.replace("${{ github.event_name }}", "pull_request")
    script = script.replace("${{ github.base_ref }}", "no-such-base-ref-cannot-be-fetched")
    outputs = tmp_path / "github_output"
    outputs.write_text("", encoding="utf-8")
    script = script.replace('"$GITHUB_OUTPUT"', str(outputs))

    proc = subprocess.run(["bash", "-c", script], cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, (
        "the scope step failed the job instead of falling back to running the suite\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
    assert "run=yes" in outputs.read_text(encoding="utf-8"), (
        f"the step did not decide to run the suite; outputs: {outputs.read_text(encoding='utf-8')!r}")
    assert "::warning::" in (proc.stdout + proc.stderr), (
        "the fallback must announce itself, or a silent skip looks like a considered decision")
