#!/usr/bin/env python3
"""The local index is the *repository's* lessons, not whatever is on this disk.

`canonical_lessons` built its file list with `rglob`, so a stray `.md` under `lessons/` — an editor
scratch file, a draft, anything a local tool left behind — became part of the search corpus here while
CI and the hosted worker never saw it. That is the audit's P7: the mechanism is real even though the
number that first exposed it (437 against a clean 435) came from a dirty tree.

Git answers the "is this in the repository" question exactly, so it is asked first; a checkout without
git (an installed package, an exported tarball, a fixture that is not a repository) keeps the walk.

Both halves matter, and both are tested here — including the flag that is easy to forget:
`-c core.quotepath=false`. Without it git octal-escapes non-ASCII paths inside quotes, so a CJK lesson
filename turns into a path that does not exist and the lesson silently vanishes from the index.
`scripts/push_preflight.py` records the same lesson.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from misakanet.lesson_index import EXCLUDED_LESSON_FILES, canonical_lessons

REPO_ROOT = Path(__file__).resolve().parent.parent

LESSON = "---\ntitle: t\ndomain: test\n---\n\n## Problem\nx\n"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A repository whose `lessons/contrib` holds one tracked lesson."""
    contrib = tmp_path / "lessons" / "contrib"
    contrib.mkdir(parents=True)
    (contrib / "tracked.md").write_text(LESSON, encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    git(tmp_path, "add", "lessons")
    git(tmp_path, "commit", "-q", "-m", "add a lesson")
    return tmp_path


def names(root: Path) -> set[str]:
    return {p.name for p in canonical_lessons(root / "lessons")}


def test_an_untracked_lesson_does_not_enter_the_index(repository: Path):
    """The bug: a file on disk that git does not track is not part of the corpus."""
    (repository / "lessons" / "contrib" / "stray-draft.md").write_text(LESSON, encoding="utf-8")
    assert names(repository) == {"tracked.md"}, (
        "an untracked lesson entered the index; CI and the hosted worker would never have it")


def test_the_git_reading_and_the_walk_agree_on_a_clean_checkout(repository: Path):
    """The change is a filter, not a different corpus: on a clean tree both readings coincide."""
    walked = {p.name for p in (repository / "lessons").rglob("*.md")
              if p.name not in EXCLUDED_LESSON_FILES}
    assert names(repository) == walked == {"tracked.md"}


def test_a_checkout_without_git_still_walks(tmp_path: Path):
    """An installed package or an exported tarball has no .git — the old behaviour has to survive."""
    contrib = tmp_path / "lessons" / "contrib"
    contrib.mkdir(parents=True)
    (contrib / "only-on-disk.md").write_text(LESSON, encoding="utf-8")
    assert names(tmp_path) == {"only-on-disk.md"}


def test_a_non_ascii_filename_is_not_octal_escaped(repository: Path):
    """`core.quotepath=false` is load-bearing: without it this lesson disappears from the index.

    Git quotes and octal-escapes non-ASCII paths by default, so the returned line is not a path that
    exists — and `canonical_lessons` would quietly drop the file instead of failing.
    """
    cjk = repository / "lessons" / "contrib" / "中文课程.md"
    cjk.write_text(LESSON, encoding="utf-8")
    git(repository, "add", "lessons")
    git(repository, "commit", "-q", "-m", "add a CJK lesson")
    assert names(repository) == {"tracked.md", "中文课程.md"}, (
        "a non-ASCII lesson name was escaped into a path that does not exist")


def test_a_stubbed_subprocess_does_not_empty_the_index(monkeypatch):
    """The failure CI found on this change, pinned.

    `subprocess` is a shared module object, so a test that stubs `subprocess.run` — as
    `tests/test_no_test_writes_repo_data.py` legitimately does for `git push` — also intercepts the
    `git ls-files` here. A stub that reports success with no output made this function return an empty
    list, the index generator enumerated no lessons and wrote an empty index, and every CI leg failed
    with "the redirected index … was never written, so the rebuild did not run".

    "Git answered with nothing" is not an answer to act on, so it now falls back to the walk.
    """
    real_run = subprocess.run

    class Done:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: Done() if a and a[0] and a[0][0] == "git" else real_run(*a, **k))
    from misakanet.lesson_index import canonical_lessons
    lesson_files = canonical_lessons(REPO_ROOT / "lessons")
    assert len(lesson_files) > 400, (
        f"a stubbed subprocess emptied the corpus ({len(lesson_files)} lessons); the walk must take "
        "over when git cannot answer")
