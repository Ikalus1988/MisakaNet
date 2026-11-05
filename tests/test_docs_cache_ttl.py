#!/usr/bin/env python3
"""The corpus is walked once per process, not once per search — and the window is visible.

Why (2026-11-02)
----------------
`_load_docs_cached` answers "which lessons exist and what do they say" by walking the corpus and
`stat()`-ing every file. Only changed files are re-read (that part was already cached in SQLite);
the walk never was. Measured on this checkout: **18.5 s** cold and **6.6 s for a second, unchanged
load** with 765 lessons on `/mnt/c` — about 8 ms per `stat()` through the Windows interop layer.
A stdio server used to pay that on every tool call, so `misakanet_search` spent seconds before it
ranked anything.

The fix is an in-memory window (`set_docs_cache_ttl`), **off by default**, turned on by the stdio
server with a five-second staleness budget. 6489 ms per call became 0.007 ms.

These tests exist because a cache is a promise about staleness, and this repository does not accept
promises nobody can point at:

* off by default — a library user and every test keep exact fresh reads;
* the window holds a newly written lesson back, and `invalidate_docs_cache()` releases it;
* the server turns it on, at a value that can be read and overridden, and a bad value falls back
  instead of killing a server before it can say why.
"""
from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.search import engine  # noqa: E402
from misakanet.server.protocol import _enable_docs_cache  # noqa: E402

LESSON = textwrap.dedent("""\
    ---
    title: cache window probe
    domain: testing
    ---

    ## Problem

    A probe lesson written by the cache test.

    ## Fix

    Nothing; it exists to be seen or not seen.
    """)


@pytest.fixture(autouse=True)
def _restore_ttl():
    """Every test leaves the module as it found it — a leaked TTL would make other tests stale."""
    original = engine._DOCS_TTL_SECONDS
    yield
    engine.set_docs_cache_ttl(original)


def _corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A two-file probe corpus the loader will accept.

    The loader stores each path relative to `engine.REPO`, so a temporary directory outside the
    repository raises `ValueError` — the corpus is expected to be a checkout. Pointing `REPO` and
    `LESSONS` at the temporary tree keeps the real loader path intact instead of testing a stub.
    """
    root = tmp_path / "lessons"
    (root / "core").mkdir(parents=True)
    (root / "core" / "seed.md").write_text(
        LESSON.replace("cache window probe", "seed lesson"), encoding="utf-8")
    monkeypatch.setattr(engine, "REPO", tmp_path)
    monkeypatch.setattr(engine, "LESSONS", root)
    return root


def _load(root: Path) -> list:
    return engine._load_docs_cached(root, is_lesson=True)


def test_off_by_default_so_a_fresh_read_stays_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine.set_docs_cache_ttl(0)
    root = _corpus(tmp_path, monkeypatch)
    assert [d.title for d in _load(root)] == ["seed lesson"]

    (root / "core" / "added.md").write_text(
        LESSON.replace("cache window probe", "added lesson"), encoding="utf-8")
    titles = [d.title for d in _load(root)]
    assert "added lesson" in titles, (
        "with the window off a newly written lesson must appear immediately — a library user who "
        "writes a file and searches again cannot be told to wait")


def test_the_window_holds_a_new_lesson_back_until_it_is_invalidated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _corpus(tmp_path, monkeypatch)
    engine.set_docs_cache_ttl(60)
    assert len(_load(root)) == 1

    (root / "core" / "added.md").write_text(
        LESSON.replace("cache window probe", "added lesson"), encoding="utf-8")
    assert len(_load(root)) == 1, (
        "inside the window the cached list is the answer — the staleness is the point, and it has "
        "to be visible here rather than discovered in production")

    engine.invalidate_docs_cache()
    assert len(_load(root)) == 2, (
        "invalidate_docs_cache() is the escape hatch the window promises; if it does not release "
        "the list, the only way to see a new lesson is to restart the process")


def test_the_window_actually_expires(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without this, `set_docs_cache_ttl` could mean "cache forever" and every other test passes."""
    import time as _time

    root = _corpus(tmp_path, monkeypatch)
    engine.set_docs_cache_ttl(0.05)
    assert len(_load(root)) == 1

    (root / "core" / "added.md").write_text(
        LESSON.replace("cache window probe", "added lesson"), encoding="utf-8")
    assert len(_load(root)) == 1, "still inside the 50 ms window"

    _time.sleep(0.2)
    assert len(_load(root)) == 2, (
        "the window is a number of seconds; a cache that never expires would make the setting "
        "name a lie and every staleness report shorter than it should be")


def test_the_stdio_server_turns_the_window_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISAKANET_DOCS_TTL_SECONDS", raising=False)
    ttl = _enable_docs_cache()
    assert ttl == 5.0
    assert engine._DOCS_TTL_SECONDS == 5.0, (
        "the server is the one process that benefits; if this wiring is dropped, every tool call "
        "pays the 765-stat walk again and nothing else in the suite notices")


def test_the_window_can_be_turned_off_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISAKANET_DOCS_TTL_SECONDS", "0")
    assert _enable_docs_cache() == 0.0
    assert engine._DOCS_TTL_SECONDS == 0.0


def test_a_bad_window_falls_back_instead_of_killing_the_server(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("MISAKANET_DOCS_TTL_SECONDS", "five")
    assert _enable_docs_cache() == 5.0
    assert "not a number" in capsys.readouterr().err, (
        "a server that dies before printing why is the failure mode this fallback exists to "
        "avoid — the operator has to be able to read the name of the setting")


def test_the_measurement_that_justifies_the_window_is_still_a_walk() -> None:
    """If the loader ever stops walking, the window is unnecessary and this should be re-measured."""
    source = (REPO / "misakanet" / "search" / "engine.py").read_text(encoding="utf-8")
    body = source.split("def _load_docs_cached_locked", 1)[1].split("\ndef ", 1)[0]
    assert "f.stat()" in body, (
        "the window exists because the loader stats every file; if that changed, delete the cache "
        "rather than paying a staleness budget for a walk that no longer happens")


def test_a_missing_engine_does_not_kill_the_server(monkeypatch, capsys):
    """A checkout without `misakanet-core` must still start and serve degraded (install-smoke).

    The cache call imports the engine; before the guard, that import was unconditional and the
    server died before printing anything — red from 2026-11-02 to 2026-11-04.
    """
    from misakanet.server import protocol

    def boom():
        raise ModuleNotFoundError("No module named 'misakanet_core'")

    monkeypatch.setattr(protocol, "_enable_docs_cache", boom)
    assert protocol._try_enable_docs_cache() is False
    assert "docs cache disabled" in capsys.readouterr().err
