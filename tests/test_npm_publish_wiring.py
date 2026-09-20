#!/usr/bin/env python3
"""Publishing to npm is automatic, and the only human step is approving the run.

The npm bundle line has a specific meaning — "the version that is on npm" — and
`tests/test_version_consistency.py` enforces that `package.json` may lag the repository release line but
never lead it. On 2026-09-20 it was at 2.30.2 while the repository and PyPI were at 2.31.0, and the cause
was structural rather than forgetfulness: **nothing wrote that line**. `misakanet-publish.yml` was
`workflow_dispatch`-only (so a release produced no publish at all), and the alignment that would have moved
`package.json` was mentioned solely inside an error message ("fix with: python3 scripts/align_versions.py
--source $TAG_VERSION") that a human had to read and act on.

The arrangement these tests pin:

* the release flow **dispatches** the publish, so a release cannot be forgotten;
* the publish run **moves** the npm line before publishing (that is the writer), and
  **records** it afterwards, so the line cannot drift back;
* the `release` environment stays on the job, so the run waits for a required reviewer — the human gate is
  kept, it is just no longer a *memory* gate;
* ordering matters in both directions: bumping after `npm publish` would publish the wrong version, and
  recording before it would claim a publish that might still fail.

Each assertion below is one of those failure modes, and `_wiring_problems` is exercised against scratch
copies so the rule cannot pass vacuously.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
PUBLISH = WORKFLOWS / "misakanet-publish.yml"
RELEASE_PLEASE = WORKFLOWS / "release-please.yml"


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(path: Path) -> list[dict]:
    steps: list[dict] = []
    for job in _workflow(path)["jobs"].values():
        steps.extend(job.get("steps", []))
    return steps


def _index_of(path: Path, needle: str) -> int:
    for index, step in enumerate(_steps(path)):
        if needle.lower() in (step.get("name") or "").lower():
            return index
    raise AssertionError(f"no step matching {needle!r} in {path.name}")


def _wiring_problems(root: Path) -> list[str]:
    """Every way this arrangement can be broken, checked against whatever tree is passed in."""
    publish = root / ".github" / "workflows" / "misakanet-publish.yml"
    release_please = root / ".github" / "workflows" / "release-please.yml"
    problems: list[str] = []

    # 1. the release flow has to start it
    dispatches = [
        (step.get("run") or "")
        for step in _steps(release_please)
        if "misakanet-publish.yml" in (step.get("run") or "")
    ]
    if not dispatches:
        problems.append("release-please.yml never dispatches misakanet-publish.yml")
    elif not any("version=" in run for run in dispatches):
        problems.append("the dispatch does not pass a version, so the publish run cannot know what to ship")

    # 2. the human gate stays
    job = _workflow(publish)["jobs"]["publish"]
    environment = job.get("environment")
    environment = environment.get("name") if isinstance(environment, dict) else environment
    if environment != "release":
        problems.append(
            f"the publish job declares environment={environment!r}; without the protected environment "
            "an automatic dispatch would publish the moment a release lands, with nobody looking")

    # 3. a version input exists, and a version dispatch publishes
    dispatch = _workflow(publish).get("on", _workflow(publish).get(True, {}))
    inputs = (dispatch or {}).get("workflow_dispatch", {}).get("inputs", {}) if isinstance(dispatch, dict) else {}
    if "version" not in inputs:
        problems.append("workflow_dispatch has no `version` input, so there is no way to publish a release")
    publish_condition = next(
        (step.get("if") or "" for step in _steps(publish) if "Publish to npm" in (step.get("name") or "")),
        "",
    )
    if "inputs.version" not in publish_condition and "github.event_name == 'push'" not in publish_condition:
        problems.append("the publish step cannot be reached by a version dispatch")

    # 4. ordering: move the line, publish, then record
    try:
        move = _index_of(publish, "Move the npm line")
        publish_at = _index_of(publish, "Publish to npm")
        record = _index_of(publish, "Record the published version")
    except AssertionError as error:
        problems.append(str(error))
    else:
        if not move < publish_at:
            problems.append("the npm line is moved at or after `npm publish` — the published version would be stale")
        if not record > publish_at:
            problems.append("the published version is recorded before `npm publish` succeeds")
        move_step = _steps(publish)[move]
        if "align_versions" not in (move_step.get("run") or ""):
            problems.append("the move step does not run align_versions.py, so nothing actually moves the line")
    return problems


def test_the_publish_is_wired_end_to_end():
    problems = _wiring_problems(REPO)
    assert not problems, (
        "the automatic npm publish is broken in these ways:\n  - " + "\n  - ".join(problems))


def test_the_wiring_check_notices_a_publish_that_nobody_starts(tmp_path):
    """Guard the guard: drop the dispatch and the rule must fail, or it is decoration."""
    scratch = tmp_path / "repo"
    (scratch / ".github" / "workflows").mkdir(parents=True)
    for path in (PUBLISH, RELEASE_PLEASE):
        shutil.copy(path, scratch / ".github" / "workflows" / path.name)
    assert _wiring_problems(scratch) == [], "the copied tree must start clean"

    release_please = scratch / ".github" / "workflows" / "release-please.yml"
    release_please.write_text(
        release_please.read_text(encoding="utf-8").replace("misakanet-publish.yml", "some-other.yml"),
        encoding="utf-8")
    assert any("never dispatches" in problem for problem in _wiring_problems(scratch))


def test_the_wiring_check_notices_a_lost_approval_gate(tmp_path):
    scratch = tmp_path / "repo"
    (scratch / ".github" / "workflows").mkdir(parents=True)
    for path in (PUBLISH, RELEASE_PLEASE):
        shutil.copy(path, scratch / ".github" / "workflows" / path.name)

    publish = scratch / ".github" / "workflows" / "misakanet-publish.yml"
    publish.write_text(
        publish.read_text(encoding="utf-8").replace("    environment: release\n", ""),
        encoding="utf-8")
    assert any("without the protected environment" in problem for problem in _wiring_problems(scratch))
