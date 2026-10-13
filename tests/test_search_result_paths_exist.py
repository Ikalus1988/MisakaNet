#!/usr/bin/env python3
"""The path the search output prints must be one a reader can open.

`_format_output` printed `f"lessons/{doc.filename}"` — a **hardcoded** directory plus a
*base*name — and `_get_related_lessons` handed back basenames. Only three lessons sit
directly in `lessons/`; the other 521 are in a subdirectory (`contrib/` 432, `en/` 64,
`core/` 14, …). So for **99% of the corpus** the one line a reader follows to open the
answer it just found named a file that does not exist, and a `reference/` document was
relabelled into `reference/<basename>` the same way.

The load-bearing assertion is therefore not "the format looks right" but "the path
resolves". Both directions are pinned, because an existence check over an empty set is
green for the wrong reason: something must have been printed, and every printed path must
be a real file.
"""
from __future__ import annotations

import functools
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "search_knowledge.py"
PRINTED_PATH = re.compile(r"📄\s+((?:lessons|reference)/\S+\.md)")

# Two queries, one cached run each: the CLI loads the whole index, so re-running per test
# would add ~10s per assertion for no extra coverage.
QUERIES = (
    "log not found zero jobs failure run",
    "docker compose port already allocated",
)


@functools.lru_cache(maxsize=None)
def _search(query: str) -> str:
    proc = subprocess.run([sys.executable, str(CLI), query],
                          cwd=REPO, capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, f"search failed:\n{proc.stdout}\n{proc.stderr}"
    return proc.stdout


@functools.lru_cache(maxsize=1)
def _printed_paths() -> tuple[str, ...]:
    found: set[str] = set()
    for query in QUERIES:
        found |= set(PRINTED_PATH.findall(_search(query)))
    return tuple(sorted(found))


def test_the_parser_sees_paths_at_all():
    """Guards the guard: `test_every_printed_path_exists` is vacuously green over an empty set,
    so a change to the output format or to the regex would silently retire the check."""
    assert _printed_paths(), (
        "no `📄 path` was printed — the output format or PRINTED_PATH changed, and "
        "test_every_printed_path_exists would now pass without checking anything")


def test_every_printed_path_exists():
    missing = [p for p in _printed_paths() if not (REPO / p).exists()]
    assert not missing, (
        "the search output pointed at paths that do not exist, so a reader cannot open the "
        "answer it found:\n" + "\n".join(f"  {p}" for p in missing))


def test_a_subdirectory_lesson_keeps_its_directory():
    """The specific regression: `core/`, `contrib/` and `en/` were all silently dropped."""
    from misakanet.search.engine import CachedDoc, _display_path

    target = next(iter(sorted((REPO / "lessons").glob("*/*.md"))), None)
    assert target is not None, "no lesson sits in a subdirectory — the corpus layout changed"
    shown = _display_path(CachedDoc(filename=target.name, filepath=target, content=""))
    assert shown == target.relative_to(REPO).as_posix()
    assert (REPO / shown).exists()
    assert shown != f"lessons/{target.name}", (
        "the basename form is exactly what pointed 99% of the corpus at a missing file")


def test_related_lessons_are_named_by_path_and_not_by_basename():
    """The 🔗 line was unopenable too, and its self-skip compared basenames: `contrib/x.md`
    and `en/x.md` are two different lessons, and the old test merged them into one."""
    from misakanet.search.engine import CachedDoc, _get_related_lessons

    doc = CachedDoc(filename="x.md", filepath=REPO / "lessons" / "contrib" / "x.md",
                    content="", tags=["network"])
    twin = CachedDoc(filename="x.md", filepath=REPO / "lessons" / "en" / "x.md",
                     content="", tags=["network"])
    related = _get_related_lessons(doc, [doc, twin])
    assert related == [("", "lessons/en/x.md")], (
        f"expected the sibling named by full path, got {related!r} — an empty list means the "
        f"basename comparison treated contrib/x.md and en/x.md as the same document")


def test_a_document_outside_the_repo_is_shown_absolute_rather_than_broken():
    """`_display_path` must not raise on a path outside `REPO`; the caller has no fallback."""
    from misakanet.search.engine import CachedDoc, _display_path

    outside = Path("/tmp") / "not-in-the-repo.md"
    assert _display_path(CachedDoc(filename=outside.name, filepath=outside, content="")) == str(outside)
