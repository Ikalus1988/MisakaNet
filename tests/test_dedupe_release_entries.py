#!/usr/bin/env python3
"""The release-notes repair: it has to run on the generator's output, and it has to be the gate's own rule.

`release-please` regenerates the release PR's newest section on every push to `main`, so a changelog
repaired by hand is undone by the next push. `release-please.yml` therefore calls
`scripts/dedupe_release_entries.py` after the action — this file covers the repair itself, and then pins the
two things that make it work in place:

* it must run **after** the step that regenerates the section (deduping before it is a no-op);
* it must push with something other than `GITHUB_TOKEN`, because a bot push creates *held* runs on the
  release PR and `DCO / Signed-off-by` is a required check (#2204's lesson).

The duplicate rule is not re-implemented here: the fixtures are checked against
`tests/test_changelog_shape.py`'s `duplicate_entries()`, which is the function that actually blocks a
release.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from scripts.dedupe_release_entries import (  # noqa: E402
    dedupe,
    newest_section_bounds,
    normalise,
    reference_count,
)
import test_changelog_shape as gate  # noqa: E402

WORKFLOW = REPO / ".github" / "workflows" / "release-please.yml"
SCRIPT = REPO / "scripts" / "dedupe_release_entries.py"

# The shape measured on the 2.35.0 release PR: the branch commit and the merge commit that carried the
# same title, each rendered as its own entry.
TWO_COPIES = """# Changelog

## [2.35.0](https://example/compare/v2.34.0...v2.35.0) (2026-09-25)


### Features

* **intake:** detect intakes whose work is already merged ([c1a3a08](https://example/c1a3a08))
* **tools:** compare the two search implementations ([6868b6b](https://example/6868b6b))
* **intake:** detect intakes whose work is already merged ([a6923ea](https://example/a6923ea))
* **tools:** compare the two search implementations ([#2121](https://example/2121)) ([a1abb31](https://example/a1abb31))
* **site:** a change that appears once ([ddddddd](https://example/ddddddd))
"""


def section_of(text: str) -> str:
    lines = text.splitlines()
    start, end = newest_section_bounds(lines)
    return "\n".join(lines[start:end])


# ── the repair ──────────────────────────────────────────────────────────────────────
def test_the_duplicates_the_gate_refuses_to_release_with_are_removed():
    assert gate.duplicate_entries(section_of(TWO_COPIES)), "the fixture no longer reproduces the failure"
    repaired, dropped = dedupe(TWO_COPIES)
    assert len(dropped) == 2, dropped
    assert gate.duplicate_entries(section_of(repaired)) == [], section_of(repaired)


def test_each_change_survives_exactly_once_and_the_order_holds():
    repaired, _ = dedupe(TWO_COPIES)
    bullets = [line for line in repaired.splitlines() if line.strip().startswith("* ")]
    assert len(bullets) == 3, bullets
    assert [normalise(b) for b in bullets] == [
        "* **intake:** detect intakes whose work is already merged",
        "* **tools:** compare the two search implementations",
        "* **site:** a change that appears once",
    ], bullets


def test_the_copy_carrying_the_pull_request_link_is_the_one_kept():
    """Both copies name the commit; only one names the PR. Dropping that one loses the only link a reader
    can follow to the discussion."""
    repaired, _ = dedupe(TWO_COPIES)
    tool_lines = [line for line in repaired.splitlines() if "compare the two search implementations" in line]
    assert len(tool_lines) == 1, tool_lines
    assert "[#2121]" in tool_lines[0], tool_lines[0]


def test_a_later_copy_does_not_move_the_entry_down_the_list():
    """The kept copy takes the position of the first occurrence: the notes' order is the generator's."""
    repaired, _ = dedupe(TWO_COPIES)
    bullets = [line for line in repaired.splitlines() if line.strip().startswith("* ")]
    assert bullets[0].startswith("* **intake:**"), bullets[0]


def test_a_clean_section_is_returned_unchanged():
    once = TWO_COPIES.replace(
        "* **intake:** detect intakes whose work is already merged ([a6923ea](https://example/a6923ea))\n", ""
    ).replace(
        "* **tools:** compare the two search implementations ([6868b6b](https://example/6868b6b))\n", ""
    )
    assert dedupe(once) == (once, [])
    # …and running it twice changes nothing the second time.
    repaired, _ = dedupe(TWO_COPIES)
    assert dedupe(repaired) == (repaired, [])


def test_older_releases_are_left_alone():
    """Same wording in two *different* releases is normal (a regression fixed again is a new change); the
    gate reads the newest section only, and so does this."""
    text = TWO_COPIES + """
## [2.34.0](https://example/compare/v2.33.0...v2.34.0) (2026-09-21)

* **intake:** detect intakes whose work is already merged ([1111111](https://example/1111111))
* **intake:** detect intakes whose work is already merged ([2222222](https://example/2222222))
"""
    repaired, _ = dedupe(text)
    assert repaired.endswith(text[len(TWO_COPIES):]), "an older release section was rewritten"


def test_the_normalised_key_ignores_reference_groups_only():
    assert normalise("* **a:** b ([#1](x)) ([abc](y))") == "* **a:** b"
    assert reference_count("* **a:** b ([#1](x)) ([abc](y))") == 2
    # A subject that legitimately ends with parentheses must survive intact.
    assert normalise("* **a:** b (not a reference)") == "* **a:** b"
    assert reference_count("* **a:** b (not a reference)") == 1


# ── the CLI the workflow calls ──────────────────────────────────────────────────────
def test_check_mode_reports_and_writes_nothing(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(TWO_COPIES, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", str(path)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "2 duplicate entries" in proc.stdout, proc.stdout
    assert path.read_text(encoding="utf-8") == TWO_COPIES, "--check rewrote the file"


def test_running_it_rewrites_and_then_reports_clean(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(TWO_COPIES, encoding="utf-8")
    first = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True, timeout=60)
    assert first.returncode == 0, first.stdout + first.stderr
    assert gate.duplicate_entries(section_of(path.read_text(encoding="utf-8"))) == []
    second = subprocess.run([sys.executable, str(SCRIPT), "--check", str(path)],
                            capture_output=True, text=True, timeout=60)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "no duplicate entries" in second.stdout


# ── the wiring that makes the repair outlive the next push ──────────────────────────
def steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["release"]["steps"]


def step_running_the_script() -> dict:
    for step in steps():
        if "dedupe_release_entries.py" in (step.get("run") or ""):
            return step
    raise AssertionError(f"no step in {WORKFLOW.name} runs dedupe_release_entries.py")


def test_the_repair_runs_after_the_step_that_regenerates_the_section():
    """Deduping a section that is regenerated two steps later is a no-op, and the release PR stays red."""
    names = [str(s.get("name") or s.get("uses") or "") for s in steps()]
    regenerator = next(i for i, n in enumerate(names) if "release-please-action" in n)
    repair = next(i for i, n in enumerate(names) if n == str(step_running_the_script().get("name")))
    assert repair > regenerator, f"the repair ({repair}) runs before the generator ({regenerator}): {names}"


def test_the_repair_push_does_not_use_the_built_in_token():
    step = step_running_the_script()
    run = step["run"]
    references = set(__import__("re").findall(r"x-access-token:\$\{?(\w+)\}?", run))
    assert references, "the push no longer builds an authenticated remote URL — re-check this rule"
    env = step.get("env") or {}
    for variable in references:
        value = str(env.get(variable, ""))
        assert value, f"{variable} is used to push but is not in the step's env"
        assert "secrets.GITHUB_TOKEN" not in value, (
            f"the release-changelog push authenticates with GITHUB_TOKEN ({variable}={value}); the new "
            "head's runs would be held, and DCO is a required check")


def test_every_invocation_passes_the_changelog_path_explicitly():
    """The step runs a *copy* of the script from `$RUNNER_TEMP`, so the script's `__file__`-relative default
    points outside the repository: `/home/runner/work/CHANGELOG.md`. The first run of the step died on
    exactly that (`FileNotFoundError`, run 36105826072) — the default is right for a checkout and wrong for
    a copy, and only an explicit argument covers both.
    """
    run = step_running_the_script()["run"]
    calls = [line for line in run.splitlines()
             if "python3" in line and "dedupe_release_entries.py" in line]
    assert calls, f"no invocation found in the step:\n{run}"
    for line in calls:
        assert "CHANGELOG.md" in line, (
            "this invocation relies on the script's default path, which resolves next to the copy, not "
            f"next to the checkout:\n{line}")


def test_a_missing_changelog_is_a_sentence_not_a_traceback(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", str(tmp_path / "nope.md")],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "no such file" in proc.stderr and "Traceback" not in proc.stderr, proc.stderr


def test_the_repair_tool_exists_where_the_workflow_reads_it_from():
    assert SCRIPT.is_file(), f"{WORKFLOW.name} copies {SCRIPT.name} from the #main checkout"
    assert (REPO / "CHANGELOG.md").is_file(), "the file the repair edits must exist in the checkout"


def test_the_current_changelog_on_main_needs_no_repair():
    """If this goes red, `main` itself carries duplicates — the repair is for the release branch, and this
    is the signal that the same shape reached `main` through a path that squashes."""
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert gate.duplicate_entries(section_of(text)) == []
