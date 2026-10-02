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
`scripts/push_preflight.py` records the same lesson. (This repository has no non-ASCII tracked path
today — an independent review counted 0 of 2511 — so the rule is insurance, not a present defect.)

And `errors="surrogateescape"`: `git ls-files` emits raw bytes, and a `text=True` decode without it
raises `UnicodeDecodeError`, which is neither `OSError` nor `SubprocessError` — the previous walk coped
with such names, this function crashed on them until the review found it.
"""
from __future__ import annotations

import errno
import os
import subprocess
import types
from pathlib import Path

import pytest

from misakanet import lesson_index
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


def test_a_non_utf8_filename_does_not_crash_the_lookup(tmp_path: Path):
    """An independent review's counterexample: `git ls-files` writes raw bytes.

    `subprocess.run(..., text=True)` decodes with the locale codec, and `UnicodeDecodeError` is not an
    `OSError` or a `SubprocessError`, so it slipped past the `except` clause that exists for "git is
    missing" and `canonical_lessons` raised — while the `rglob` walk it replaced handled the same name
    through `surrogateescape`. One byte in the wrong place turned the corpus lookup into a crash.
    """
    repo = tmp_path / "repo"
    contrib = repo / "lessons" / "contrib"
    contrib.mkdir(parents=True)
    (contrib / "ok.md").write_text(LESSON, encoding="utf-8")
    raw = os.fsencode(contrib) + b"/\xff\xfe-bad.md"
    try:
        with open(raw, "wb") as handle:
            handle.write(LESSON.encode("utf-8"))
    except (OSError, UnicodeError) as exc:
        # Every way an operating system says "I cannot hold that name", measured on all three of CI's
        # platforms:
        #
        #   * APFS refuses it with EILSEQ (92 there), Linux with EILSEQ (84) — the constants are compared,
        #     never the number — plus EINVAL and ENOTSUP for filesystems that answer differently;
        #   * Windows fails **before any syscall**: decoding the bytes path to pass it along raises
        #     `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff` (measured 2026-10-02 on
        #     windows-latest, 3.13), which is a `UnicodeError` and so never reached the old `except
        #     OSError` — the first version of this fix broke that leg too;
        #   * WinError 123 can arrive with `errno is None`, which is only tolerated on Windows.
        #
        # Anything else — EACCES, ENOSPC, a missing directory — is a real problem and is re-raised. The
        # first version caught bare `OSError`, and an independent review shimmed both EACCES and ENOSPC to
        # show that a permissions failure or a full disk would have been reported as "this filesystem
        # refuses non-UTF-8 filenames" and skipped.
        name_problem = isinstance(exc, UnicodeError) or (
            exc.errno in (errno.EILSEQ, errno.EINVAL, errno.ENOTSUP)
            or (exc.errno is None and os.name == "nt"))
        if not name_problem:
            raise
        pytest.skip(f"this filesystem refuses non-UTF-8 filenames: {exc}")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    got = canonical_lessons(repo / "lessons")           # must not raise

    names = [path.name for path in got]
    assert any(name == "ok.md" for name in names), "the readable lesson vanished from the index"
    # "Did not raise" is not the property that matters: `surrogateescape` round-trips the bytes, so the
    # unreadable-looking name must still be **indexed**. An independent review pointed out that the first
    # version of this test passed even if the lesson was silently dropped.
    assert any("\udcff" in name for name in names), (
        f"the non-UTF-8 lesson was dropped instead of indexed: {names!r}")


def test_the_git_reading_decodes_raw_bytes(tmp_path: Path, monkeypatch):
    """The argument that keeps a non-UTF-8 name from becoming an exception, pinned everywhere.

    The behavioural test above needs a filesystem that can hold such a name, which APFS cannot, so this
    checks the call itself: `text=True` without `errors=` decodes with the locale codec, and
    `UnicodeDecodeError` is neither an `OSError` nor a `SubprocessError`, so it escapes the `except` that
    exists for a missing git and takes `canonical_lessons` down with it.

    It asserts the **kwargs the call is made with**, not text in the source. An independent review broke
    the first version twice: equivalent rewrites (single quotes, a named constant) failed it, while
    deleting the argument but leaving a comment mentioning it inside the parentheses passed — and on
    macOS, where the behavioural test skips, that comment was the only thing standing between the corpus
    and a crash.

    `lesson_index.subprocess` is replaced rather than the shared module's `run`, so this cannot leak into
    other tests (the same shared-module trap that emptied the corpus in this pull request's first CI run).
    """
    contrib = tmp_path / "lessons" / "contrib"
    contrib.mkdir(parents=True)
    (contrib / "ok.md").write_text(LESSON, encoding="utf-8")
    seen: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stdout = "contrib/ok.md\n"

    def fake_run(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return _Completed()

    monkeypatch.setattr(lesson_index, "subprocess", types.SimpleNamespace(
        run=fake_run, SubprocessError=subprocess.SubprocessError))

    got = canonical_lessons(tmp_path / "lessons")

    kwargs = seen.get("kwargs") or {}
    assert kwargs.get("errors") == "surrogateescape", (
        "the git reading no longer decodes with surrogateescape, so a non-UTF-8 filename raises "
        f"UnicodeDecodeError (measured on ext4); the call was made with {kwargs!r}")
    assert kwargs.get("text") is True, f"without text mode the paths arrive as bytes: {kwargs!r}"
    assert [path.name for path in got] == ["ok.md"], "the fake's lesson did not come through"
