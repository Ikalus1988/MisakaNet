#!/usr/bin/env python3
"""Every converted workflow must call the lander with arguments the lander will accept.

`tests/test_no_workflow_pushes_to_main.py` proves no workflow writes `main` by push any more. That
leaves the other half of the same question unasked: *does the call that replaced the push actually
work?* The failures that costs are all silent-ish and all cheap to catch here instead —

* a `--branch` that is not a `bot/…` name (the lander refuses it at runtime, in a scheduled run,
  hours after the edit);
* a `--title` carrying a `[skip ci]` marker, which suppresses the pull request's own runs so the
  required checks never report and the auto-merge waits forever;
* a missing `--title` altogether (`argparse` fails, so this one is loud, but only at 04:41 UTC);
* `GH_TOKEN` bound to `GITHUB_TOKEN` instead of the PAT — the single most expensive of the four,
  because the pull request is created, looks correct, and simply never gets checks;
* a `--paths` name that no longer exists, which turns a real regeneration into "nothing to land".

The arguments are read out of the workflow and handed to the lander's **own** `check_branch` and
`check_title`, not to a second copy of the rules — a test that re-implements the validator can
agree with itself while disagreeing with production, which is how this repository has lost gates
before.

What this cannot check is the run itself (an actual runner, the real secret, the real API). That
half was proven live on 2026-09-23 with pull requests #2104 and #2105 —
`docs/maintainer/automation-lands-via-pr.md` — and the first scheduled run after the conversion
merges is the production confirmation.
"""
from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow steps")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
sys.path.insert(0, str(REPO / "scripts" / "ci"))

import land_change  # noqa: E402  (path inserted above)

# workflow → the branch the lander must be told to use.
EXPECTED_BRANCH = {
    "sync-node-counter.yml": "bot/sync-node-counter",
    "update-lessons.yml": "bot/update-lessons",
    "build-feed.yml": "bot/build-feed",
    "leaderboard-watch.yml": "bot/leaderboard-watch",
    "benchmark-workers-ai.yml": "bot/benchmark-workers-ai",
    "d1-bootstrap.yml": "bot/d1-bootstrap",
    "release-please.yml": "bot/release-version-sync",
}


def lander_invocations(workflow: Path) -> list[tuple[str, dict]]:
    """Each `run:` that calls the lander, as (command line with continuations joined, step)."""
    data = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    found = []
    for job in (data.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            if not isinstance(step, dict):
                continue
            script = step.get("run")
            if not isinstance(script, str) or "scripts/ci/land_change.py" not in script:
                continue
            joined = script.replace("\\\n", " ")
            command = next(
                line.strip() for line in joined.splitlines()
                if "scripts/ci/land_change.py" in line
            )
            found.append((command, step))
    return found


def args_of(command: str) -> list[str]:
    """The arguments after the script path, shell-decoded (`--note "a b"` is one argument)."""
    tokens = shlex.split(command)
    return tokens[tokens.index(next(t for t in tokens if t.endswith("land_change.py"))) + 1:]


def value_of(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args else None


def test_every_converted_workflow_calls_the_lander_exactly_once():
    for name in EXPECTED_BRANCH:
        invocations = lander_invocations(WORKFLOWS / name)
        assert len(invocations) == 1, (
            f"{name}: expected exactly one lander call, found {len(invocations)}"
        )


def test_the_arguments_are_ones_the_lander_accepts():
    for name, expected_branch in EXPECTED_BRANCH.items():
        command, _ = lander_invocations(WORKFLOWS / name)[0]
        args = args_of(command)

        branch = value_of(args, "--branch")
        assert branch == expected_branch, f"{name}: --branch is {branch!r}, expected {expected_branch!r}"
        # The lander's own validator, not a copy of its rules.
        assert land_change.check_branch(branch) == branch

        title = value_of(args, "--title")
        assert title, f"{name}: no --title"
        # Refuses a `[skip ci]` marker — it would suppress the required checks this PR needs.
        assert land_change.check_title(title) == title


def test_the_lander_is_handed_a_pat_not_the_workflow_token():
    for name in EXPECTED_BRANCH:
        _, step = lander_invocations(WORKFLOWS / name)[0]
        token = (step.get("env") or {}).get("GH_TOKEN", "")
        assert "SHELDON_PAT" in token, (
            f"{name}: GH_TOKEN is {token!r}. A branch pushed with GITHUB_TOKEN starts no workflow "
            "runs, so the required checks never report and auto-merge waits forever."
        )


def test_named_paths_still_exist():
    """`--paths` naming a file nobody writes is a silent 'nothing to land' forever."""
    for name in EXPECTED_BRANCH:
        command, _ = lander_invocations(WORKFLOWS / name)[0]
        args = args_of(command)
        if "--paths" not in args:
            continue
        rest = args[args.index("--paths") + 1:]
        paths = []
        for token in rest:
            if token.startswith("--"):
                break  # argparse stops at the next flag; so does this
            paths.append(token)
        assert paths, f"{name}: --paths with no value"
        for path in paths:
            assert (REPO / path).exists(), f"{name}: --paths names {path!r}, which does not exist"


def test_the_scan_would_notice_a_broken_call(tmp_path):
    """The scan must be able to fail: a workflow with no lander call, and one with a bad branch."""
    empty = tmp_path / "empty.yml"
    empty.write_text(
        "name: x\non: {workflow_dispatch: {}}\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo hi\n",
        encoding="utf-8",
    )
    assert lander_invocations(empty) == []

    broken = tmp_path / "broken.yml"
    broken.write_text(
        "name: x\non: {workflow_dispatch: {}}\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: |\n          python3 scripts/ci/land_change.py \\\n"
        '            --branch main \\\n            --title "chore: x [skip ci]"\n',
        encoding="utf-8",
    )
    command, _ = lander_invocations(broken)[0]
    args = args_of(command)
    assert value_of(args, "--branch") == "main"
    with pytest.raises(land_change.LandError):
        land_change.check_branch("main")
    with pytest.raises(land_change.LandError):
        land_change.check_title(value_of(args, "--title"))
