#!/usr/bin/env python3
"""A failed contribution must not leave a branch behind (2026-09-18 review, 意见 10).

`contribute()` makes seven GitHub API calls, four of which used to `return False` *after* the branch
existed: a failed blob, tree or commit left a `contribute/<slug>` branch in the repository with nothing
pointing at it, and the maintainer cleaned those up by hand. The test drives the real function with a
stubbed `_api` — no network — and asserts on the calls it made, not on the prose it printed.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

LESSON = "irrelevant: the loader is stubbed below\n"


@pytest.fixture()
def lesson_file(tmp_path: Path) -> Path:
    path = tmp_path / "lesson.md"
    path.write_text(LESSON, encoding="utf-8")
    return path


def _drive(monkeypatch, lesson_file: Path, fail_at: str) -> list[tuple[str, str]]:
    """Run contribute() with a stub that fails at `fail_at`; return the (path, method) calls made."""
    import contribute

    calls: list[tuple[str, str]] = []

    def fake_api(path: str, data: dict | None = None, method: str = "POST"):
        calls.append((path, method))
        if fail_at in path:
            return None
        if path == "git/ref/heads/main":
            return {"object": {"sha": "base-sha"}}
        if path == "git/refs":
            return {"ref": "refs/heads/contribute/x"}
        if path == "git/blobs":
            return {"sha": "blob-sha"}
        if path == "git/trees":
            return {"sha": "tree-sha"}
        if path == "git/commits":
            return {"sha": "commit-sha"}
        if path.startswith("git/refs/heads/"):
            return {"ref": path}
        if path == "pulls":
            return {"html_url": "https://example.invalid/pr/1"}
        return {}

    # defaultdict: the PR payload reads several lesson fields, and this test is about the API chain
    # and its rollback, not about which keys a lesson happens to carry.
    monkeypatch.setattr(contribute, "_read_lesson", lambda path: defaultdict(str, {
        "title": "Rollback test lesson", "domain": "python", "tags": ["test"],
        "content": "## Problem\nSomething breaks.\n", "filename": "rollback-test-lesson.md",
    }))
    monkeypatch.setattr(contribute, "_api", fake_api)
    monkeypatch.setattr(contribute, "_get_token", lambda: "token")
    contribute.contribute(str(lesson_file))
    return calls


def test_a_failed_blob_deletes_the_branch_it_created(monkeypatch, lesson_file: Path):
    calls = _drive(monkeypatch, lesson_file, fail_at="git/blobs")
    assert any(p == "git/refs" for p, _ in calls), "the branch was created before the failure"
    deletes = [(p, m) for p, m in calls if m == "DELETE" and p.startswith("git/refs/heads/")]
    assert deletes, f"a failure after the branch exists must delete it; calls were {calls}"


def test_a_failed_commit_deletes_the_branch(monkeypatch, lesson_file: Path):
    calls = _drive(monkeypatch, lesson_file, fail_at="git/commits")
    assert any(m == "DELETE" for _, m in calls), f"expected a rollback; calls were {calls}"


def test_a_failed_tree_deletes_the_branch(monkeypatch, lesson_file: Path):
    calls = _drive(monkeypatch, lesson_file, fail_at="git/trees")
    assert any(m == "DELETE" for _, m in calls), f"expected a rollback; calls were {calls}"


def test_a_failure_before_the_branch_needs_no_rollback(monkeypatch, lesson_file: Path):
    """Guard the guard: no `DELETE` may be attempted when nothing was created."""
    calls = _drive(monkeypatch, lesson_file, fail_at="git/ref/heads/main")
    assert not any(m == "DELETE" for _, m in calls), calls


def test_nothing_was_rolled_back_on_a_clean_run(monkeypatch, lesson_file: Path):
    calls = _drive(monkeypatch, lesson_file, fail_at="__never__")
    assert not any(m == "DELETE" for _, m in calls), f"a successful run rolls nothing back: {calls}"
    assert any(p == "pulls" for p, _ in calls), "the clean run must reach the PR"
