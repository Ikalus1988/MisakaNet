#!/usr/bin/env python3
"""A lesson pull request must be complete, not merely correct.

Three pull requests in one afternoon were complete, well-written lessons that would have merged
cleanly and joined nothing. Two facts the repository already knew, and neither was enforced:

* **Location.** `lessons/` holds 389 lessons in `contrib/`, 14 in `core/`, and three files directly
  under `lessons/` — `TEMPLATE.md`, `LESSON_QUALITY_SCORING.md`, `README.md` — none of them
  lessons. `ACTIVE_LESSON_SUBDIRS` has been in `lesson_gate.py` since the corpus was split and every
  *discovery* path filters on it, so a lesson placed outside those directories is invisible: it
  passes every content rule and `update_lessons_json.py` never reads it.

* **Generated output.** `data/lessons.json`, `docs/data/lessons.json`, `docs/data/lessons-lite.json`
  and every lesson page are generated from `lessons/`. A pull request that adds a lesson without
  re-running the generators is **incomplete** rather than wrong, and incompleteness is the one thing
  no other check reported. The symptom arrived days later as a conflict with the next lesson pull
  request, which is how "add a lesson" learned to cost a round trip.

Both rules exist so the failure a contributor meets is one they can fix themselves, stated as a
command, at the moment they push — not a merge conflict three days later that nobody can explain.

**Why the generator half runs in a worktree.** The check is "run the generators, then look at the
diff". Running that here would rewrite the published files, and `tests/conftest.py` fails any test
that touches them — by size and mtime, so writing and restoring is not a way out either, and its
message says so by name. A throwaway worktree is the honest way to run a real write path: the
repository under test is not the repository being modified.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("lesson_gate", REPO / "scripts" / "lesson_gate.py")
assert _spec and _spec.loader
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

VALID_LESSON = """---
domain: "development"
title: "A lesson that satisfies every content rule and is still not a contribution yet"
tags: ["drift", "generators", "location"]
status: "published"
evidence_level: "E1"
summary_plain: "Content is valid; the file is simply in the wrong place or its outputs are stale."
trigger: "contribution lesson location generated index stale"
verify: "python3 scripts/lesson_gate.py lessons/contrib/example.md"
---

# A lesson that satisfies every content rule

## Problem

The content here is deliberately valid: the body is long enough, the frontmatter is complete, and
the domain is allowed. Whatever fails below fails for a reason that has nothing to do with quality.

## Root Cause

Placement and generated output are part of the contract, and neither is about whether the lesson is
any good. A lesson in a directory nothing reads is not in the corpus however well written it is, and
a lesson whose index has not been regenerated is not searchable either.

## Solution

Put the file in `lessons/contrib/`, then run `scripts/update_lessons_json.py` and
`scripts/build_lesson_pages.py` and commit what they write.

## Verification

`python3 scripts/lesson_gate.py` reports the location with the `git mv` to run, and re-running the
generators produces a diff naming every file the pull request failed to carry.
"""


# ── placement ───────────────────────────────────────────────────────────────────────────────────

def test_a_lesson_outside_the_corpus_directories_is_rejected_with_the_command() -> None:
    """The gate's job here is to say *where*, not *what* — the file is otherwise perfect."""
    wrong = REPO / "lessons" / "zz-probe-not-a-directory.md"
    assert not wrong.exists(), "a previous run left a probe behind"
    try:
        wrong.write_text(VALID_LESSON, encoding="utf-8")
        errors = gate.validate_file(wrong)
    finally:
        wrong.unlink()

    location = [e for e in errors if "lessons/contrib" in e]
    assert location, f"a lesson in lessons/ root was accepted: {errors}"
    assert "git mv lessons/zz-probe-not-a-directory.md" in location[0], (
        f"the error must carry the command that fixes it: {location[0]}"
    )
    # ...and nothing else is wrong with it, which is what makes this a placement finding
    assert not [e for e in errors if "too short" in e or "missing required section" in e], errors


def test_an_unknown_subdirectory_is_rejected_too() -> None:
    """`lessons/en/` is read, `lessons/translations/` would not be. A typo'd directory is invisible."""
    wrong = REPO / "lessons" / "translations" / "zz-probe.md"
    wrong.parent.mkdir(parents=True, exist_ok=True)
    try:
        wrong.write_text(VALID_LESSON, encoding="utf-8")
        errors = gate.validate_location(wrong)
    finally:
        wrong.unlink()
        wrong.parent.rmdir()
    assert errors, "lessons/translations/ is not a directory anything reads"
    assert "not a lesson directory" in errors[0], errors[0]
    assert "git mv" in errors[0]


def test_the_three_real_lesson_directories_are_accepted() -> None:
    """The rule has to accept everything the corpus actually reads, or it is a new blocker."""
    for sub in sorted(gate.ACTIVE_LESSON_SUBDIRS):
        assert gate.validate_location(REPO / "lessons" / sub / "example.md") == [], (
            f"lessons/{sub}/ is a real lesson directory and must not be flagged"
        )


def test_a_file_already_on_the_base_branch_keeps_whatever_directory_it_has() -> None:
    """Legacy placement is not a new pull request's debt (#1506's principle, applied to location).

    The whole reason the content rules have an `--existing` mode is that a metadata batch touching
    400 files must not be held to a rule those files predate. The same applies here: refusing every
    future edit to a misplaced lesson would make the repository less fixed, not more.
    """
    wrong = REPO / "lessons" / "zz-probe-legacy.md"
    try:
        wrong.write_text(VALID_LESSON, encoding="utf-8")
        assert gate.validate_file(wrong, existing=True) == [], (
            "an existing file must not be blocked on where it lives"
        )
    finally:
        wrong.unlink()


# ── generated output ─────────────────────────────────────────────────────────────────────────────

def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in ("MISAKANET_LESSONS_INDEX", "MISAKANET_DOCS_INDEX"):
        env.pop(name, None)
    return env


def _run(*argv: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], cwd=cwd, capture_output=True,
                          text=True, timeout=600, env=_clean_env())


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory) -> Path:
    """A copy of the repository the generator can safely rewrite.

    `git worktree add` would need this repository's own git metadata and a branch; a plain copy is
    enough because nothing in the test reads a commit, and it cannot reach the real checkout even if
    a step above is wrong.
    """
    root = tmp_path_factory.mktemp("lesson-contract")
    clone = root / "repo"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", "--depth", "1", str(REPO), str(clone)],
        check=True, capture_output=True, timeout=600,
    )
    # The working-tree version of the two scripts this change touches, which a clone of HEAD has not
    # seen. Copied so the sandbox exercises *this* branch rather than the base commit.
    for name in ("scripts/lesson_gate.py", "scripts/update_lessons_json.py",
                 ".github/workflows/lesson-gate.yml"):
        shutil.copy(REPO / name, clone / name)
    # `--allow-empty` is not optional here, it is the fix for a bug that only shows up in CI. The
    # clone is of HEAD, and the three files copied above are the working tree of a branch that is
    # *already committed* — so in a clean checkout they are byte-identical to what was cloned,
    # `git add -A` stages nothing, and a bare `git commit` exits 1. Every test that used this
    # sandbox therefore errored in CI on all nine platform legs while passing locally, because a
    # dirty worktree happened to leave something to commit. The commit exists to give the sandbox a
    # clean baseline, not to record a change, so an empty one is the intended outcome.
    subprocess.run(["git", "add", "-A"], cwd=clone, check=True, capture_output=True)
    subprocess.run(
        ["git",
         "-c", "user.email=t@example.invalid",
         "-c", "user.name=t",
         # A signing configuration from the host would turn this into a prompt in CI.
         "-c", "commit.gpgsign=false",
         "commit", "--quiet", "--allow-empty", "-m", "sandbox"],
        cwd=clone, check=True, capture_output=True,
    )
    return clone


def test_the_generators_are_a_no_op_on_an_unchanged_corpus(sandbox: Path) -> None:
    """The baseline. A check that is red on a clean tree is a check nobody will ever satisfy."""
    assert _run("scripts/update_lessons_json.py", cwd=sandbox).returncode == 0
    assert _run("scripts/build_lesson_pages.py", cwd=sandbox).returncode == 0
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=sandbox,
                           capture_output=True, text=True).stdout.strip()
    assert dirty == "", f"the committed corpus does not match its own generators:\n{dirty}"


def test_a_lesson_without_regenerated_output_is_caught(sandbox: Path) -> None:
    """The whole contract, end to end: add a lesson, change nothing else, and look at the diff.

    The lesson is committed — `canonical_lessons` reads git-tracked files, so an untracked one is
    invisible to the generator and this would pass for the wrong reason.
    """
    probe = sandbox / "lessons" / "contrib" / "zz-probe-drift.md"
    probe.write_text(VALID_LESSON, encoding="utf-8")
    subprocess.run(["git", "add", "lessons/contrib/zz-probe-drift.md"],
                   cwd=sandbox, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                    "commit", "--quiet", "-m", "add a lesson, forget the generators"],
                   cwd=sandbox, check=True, capture_output=True)

    _run("scripts/update_lessons_json.py", cwd=sandbox)
    _run("scripts/build_lesson_pages.py", cwd=sandbox)
    changed = subprocess.run(["git", "status", "--porcelain"], cwd=sandbox,
                             capture_output=True, text=True).stdout
    assert changed.strip(), "the generators produced nothing for a new lesson — this check is blind"
    for expected in ("data/lessons.json", "docs/data/lessons.json"):
        assert expected in changed, f"{expected} is not among the stale files:\n{changed}"
    # The lesson gate is happy with the same file, which is the point: nothing else caught this.
    gate_result = subprocess.run(
        [sys.executable, "scripts/lesson_gate.py", "lessons/contrib/zz-probe-drift.md"],
        cwd=sandbox, capture_output=True, text=True, timeout=300,
    )
    assert gate_result.returncode == 0, (
        f"the content gate accepts it, so the generator check is the only thing standing between "
        f"this lesson and being invisible:\n{gate_result.stdout}"
    )


def test_regenerating_first_makes_the_tree_clean(sandbox: Path) -> None:
    """The fix the failure message prints, verified in the same shape CI uses."""
    probe = sandbox / "lessons" / "contrib" / "zz-probe-drift.md"
    if not probe.exists():
        pytest.skip("depends on the previous test's probe")
    _run("scripts/update_lessons_json.py", cwd=sandbox)
    _run("scripts/build_lesson_pages.py", cwd=sandbox)
    subprocess.run(["git", "add", "-A"], cwd=sandbox, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t",
                    "commit", "--quiet", "-m", "regenerate"], cwd=sandbox, check=True,
                   capture_output=True)
    changed = subprocess.run(["git", "status", "--porcelain"], cwd=sandbox,
                             capture_output=True, text=True).stdout.strip()
    assert changed == "", f"the commands the gate prints did not make the tree clean:\n{changed}"


# ── the rule is actually wired up ────────────────────────────────────────────────────────────────

def test_the_generator_check_is_wired_into_the_lesson_gate() -> None:
    """A rule nothing runs documents an intention.

    Read off the parsed workflow's `run:` blocks rather than by substring over the file:
    `tests/test_workflow_env_is_used.py` records that a comment in a workflow satisfied a substring
    assertion five times in this repository, and this test is written after that was learned.
    """
    yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow")
    workflow = yaml.safe_load(
        (REPO / ".github" / "workflows" / "lesson-gate.yml").read_text(encoding="utf-8")
    )
    job = next(j for j in workflow["jobs"].values() if "steps" in j)
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "update_lessons_json.py" in runs, "the index generator is not run by the gate"
    assert "build_lesson_pages.py" in runs, "the page generator is not run by the gate"
    assert "git diff --quiet" in runs, (
        "running the generators is not the check; the check is whether they changed anything"
    )
    step = next(s for s in job["steps"] if "git diff --quiet" in (s.get("run") or ""))
    assert "exit 1" in step["run"], "a stale generated file must fail the required check"
    # and the failure has to name the fix
    assert "commit what they wrote" in step["run"], (
        "the error must say what to do, so the round trip is running two commands"
    )
