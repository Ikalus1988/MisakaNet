#!/usr/bin/env python3
"""One corpus, two copies: fail when the site copy stops carrying the same lessons.

WHY THIS EXISTS (2026-09-29)
----------------------------
The site ships the corpus twice and nothing bound the two files:

* ``data/lessons.json`` — the canonical snapshot, written by ``scripts/update_lessons_json.py``;
* ``docs/data/lessons.json`` — the copy the browser downloads, which until now was produced only by
  ``cp data/lessons.json docs/data/lessons.json`` in the three-hourly ``.github/workflows/build-feed.yml``.

Between a regeneration of the canonical index and the next feed run, the site therefore served an index
that disagreed with the repository it was built from — and no check looked at both files at once.
Measured 2026-09-29: the two copies held **426** and **418** lessons for about a day (the site was
internally inconsistent), and nothing went red. They agreed again only because the 3-hourly job happened
to have run; that is timing, not a guarantee.

What counts as "the same corpus"
--------------------------------
The parsed JSON, not the bytes: same length, same set of ``id`` values, no duplicate ids on either side,
and — when the ids match — the same entries, because a copy that kept every id but froze the fields the
browser renders (``title``/``preview``/``trust_score``/…) is stale in exactly the way that matters.
Comparing parsed data rather than bytes also keeps a reformatted but semantically identical copy green.

A file that is not a lesson index at all (not JSON, not a list, an entry with no string ``id``) is
reported as a *problem*, never as a traceback: a check that crashes on the shape it exists to catch
reads as an infrastructure failure, and the divergence it was supposed to name goes unreported.

The fixture half of this gate lives in ``tests/test_docs_data_copy.py`` — the repository always guards a
check that reads the repository itself, by breaking the artifact in a temp directory and requiring the
comparison to go red.

Usage::

    python3 scripts/check_docs_data_copy.py          # exit 0 in sync, 1 diverged
    python3 scripts/check_docs_data_copy.py --canonical a.json --published b.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# The two files the site serves. Kept as module constants so a test can point them at a temp directory
# (and so `update_lessons_json` can reuse CANONICAL as the source of the copy it writes).
CANONICAL = REPO / "data" / "lessons.json"
PUBLISHED = REPO / "docs" / "data" / "lessons.json"

# How many ids a failure message names before it stops: enough to recognize the diff, short enough to
# read in a CI log for a 400-lesson divergence.
SAMPLE = 8


class IndexShapeError(Exception):
    """A file is not a lesson index: unreadable, not JSON, not a list, or an entry with no string `id`."""


def load_index(path: Path) -> list:
    """Parse `path` as a lesson index, or raise IndexShapeError naming what is wrong with it."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise IndexShapeError(f"{path} does not exist") from exc
    except OSError as exc:
        raise IndexShapeError(f"{path} could not be read ({exc})") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IndexShapeError(f"{path} is not valid JSON ({exc})") from exc
    if not isinstance(data, list):
        raise IndexShapeError(
            f"{path} is a JSON {type(data).__name__}, not the list of lessons both copies must be")
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise IndexShapeError(
                f"{path}: entry {i} is a {type(entry).__name__}, not a lesson object")
    return data


def lesson_ids(entries: list, path: Path) -> list:
    """The `id` of every entry, in file order, or IndexShapeError naming the first entry without one."""
    path = Path(path)
    ids = []
    for i, entry in enumerate(entries):
        value = entry.get("id")
        if not isinstance(value, str) or not value:
            raise IndexShapeError(f"{path}: entry {i} has no usable string 'id' (got {value!r})")
        ids.append(value)
    return ids


def _sample(ids: list) -> str:
    """`a, b, c … (+N more)` — a bounded, deterministic rendering of an id set in a failure message."""
    head = ", ".join(sorted(ids)[:SAMPLE])
    rest = len(ids) - SAMPLE
    return f"{head} (+{rest} more)" if rest > 0 else head


def compare_index_copies(canonical: Path, published: Path) -> list:
    """Problems that make the two copies different corpora; an empty list means they agree.

    Never raises for a bad file: a shape error comes back as a problem string, so the caller reports
    "the site copy is unusable" instead of a traceback that hides which copy broke.
    """
    canonical, published = Path(canonical), Path(published)
    problems: list[str] = []
    parsed: dict[str, tuple[list, list]] = {}

    for label, path in (("canonical", canonical), ("published", published)):
        try:
            entries = load_index(path)
            ids = lesson_ids(entries, path)
        except IndexShapeError as exc:
            problems.append(f"the {label} copy is unusable: {exc}")
            continue
        parsed[label] = (entries, ids)

    # A file that is not an index makes the set comparison meaningless (and would raise on the empty
    # `parsed` entry), so report the shape failure and stop there.
    if problems:
        return problems

    c_entries, c_ids = parsed["canonical"]
    p_entries, p_ids = parsed["published"]

    # Duplicates first: they are how two files can have the same length and the same *set* of ids while
    # still describing different corpora.
    for label, ids in (("canonical", c_ids), ("published", p_ids)):
        duplicated = sorted(i for i, n in Counter(ids).items() if n > 1)
        if duplicated:
            problems.append(f"the {label} copy repeats {len(duplicated)} lesson id(s): {_sample(duplicated)}")

    if len(c_ids) != len(p_ids):
        problems.append(
            f"the copies hold a different number of lessons: canonical {canonical} has {len(c_ids)}, "
            f"published {published} has {len(p_ids)}")

    missing = set(c_ids) - set(p_ids)
    extra = set(p_ids) - set(c_ids)
    if missing:
        problems.append(
            f"{len(missing)} lesson(s) in the canonical index are missing from the site copy: {_sample(list(missing))}")
    if extra:
        problems.append(
            f"{len(extra)} lesson(s) in the site copy are not in the canonical index: {_sample(list(extra))}")

    # Same ids is not the same corpus: the site copy is what the browser renders, so a stale snapshot
    # that kept every id while freezing the fields is the same defect one level down.
    if not problems and c_entries != p_entries:
        problems.append(
            "the copies carry the same lesson ids but different lesson data — the site copy is a stale "
            "snapshot of the fields the browser renders (regenerate it, do not hand-edit it)")
    return problems


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when docs/data/lessons.json is not the same corpus as data/lessons.json.")
    parser.add_argument("--canonical", default=str(CANONICAL),
                        help=f"the canonical index (default: {CANONICAL.relative_to(REPO)})")
    parser.add_argument("--published", default=str(PUBLISHED),
                        help=f"the copy the site serves (default: {PUBLISHED.relative_to(REPO)})")
    args = parser.parse_args(argv)

    problems = compare_index_copies(Path(args.canonical), Path(args.published))
    if not problems:
        print(f"OK {args.published} carries the same {len(load_index(Path(args.canonical)))} lessons "
              f"as {args.canonical}")
        return 0
    print(f"FAIL {args.published} is not the same corpus as {args.canonical}:")
    for problem in problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
