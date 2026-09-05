"""Single source of truth for which lesson directories form the index.

Policy (maintainer decision 2026-09-05, audit T2.2): the lesson index is a
LIBRARY — every subdirectory under ``lessons/`` that contains real lesson
files is visible, including locale dirs (``en/``, …), lifecycle dirs
(``draft*``/``user-rescue/``) and future curated dirs such as ``verified/``.
Only pure scaffolding is excluded:

* ``templates/`` — placeholder skeletons (``title: <Domain Lesson Title>``)
* ``_archive/``   — retired lessons deliberately out of rotation (marked
  ARCHIVED / "CONTEXT COMPACTION" half-imports), not merely outdated

Per-directory index/README/TEMPLATE files are excluded at file level
(``EXCLUDED_LESSON_FILES``). Outdated or wrong *active* lessons are kept
visible on purpose: users hit them, trial-and-error, and submit corrections
(the MisakaNet feedback path) — same as a library shelf.
"""
from __future__ import annotations

from pathlib import Path

# Directory names that never index (scaffolding / retired).
EXCLUDED_LESSON_DIRS = frozenset({"templates", "_archive"})

# Non-lesson markdown that must never be indexed, regardless of directory.
EXCLUDED_LESSON_FILES = frozenset({"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"})

# Canonical-precedence for duplicate stems (see canonical_lessons): reviewed
# core/contrib originals win over mirror/translation dirs.
_DIR_PRIORITY = {"core": 0, "contrib": 1}


def discover_lesson_dirs(lessons_root: Path) -> list[Path]:
    """Sorted subdirectories of ``lessons_root`` that contain real lessons.

    A directory counts when at least one ``*.md`` file under it (recursively)
    is not an excluded index/README/TEMPLATE file. Adding a new published
    directory (e.g. ``lessons/verified/``) therefore needs **no code change**
    — it is discovered automatically.
    """
    dirs: list[Path] = []
    if not lessons_root.is_dir():
        return dirs
    for child in sorted(lessons_root.iterdir()):
        if not child.is_dir() or child.name in EXCLUDED_LESSON_DIRS:
            continue
        if any(
            f.name not in EXCLUDED_LESSON_FILES and f.suffix == ".md"
            for f in child.rglob("*.md")
        ):
            dirs.append(child)
    return dirs


def canonical_lessons(lessons_root: Path) -> list[Path]:
    """One lesson per stem across all discovered dirs (duplicate-free index).

    Community mirror/translation dirs (e.g. ``en/``) carry copies of the same
    lesson under the same stem; indexing both would return duplicates to
    users. Resolution: keep the highest-precedence copy — ``core/`` then
    ``contrib/`` then every other dir alphabetically — and drop the rest.
    The dropped files stay in the repo and remain fetchable by path; they are
    simply not part of the visible index/search corpus.

    Returns files in canonical (dir-major, insertion) order, which keeps the
    historic core/contrib prefix ordering stable.
    """
    seen: dict[str, Path] = {}
    dirs = sorted(
        discover_lesson_dirs(lessons_root),
        key=lambda d: (_DIR_PRIORITY.get(d.name, 2), d.name),
    )
    for d in dirs:
        for f in sorted(d.rglob("*.md")):
            if f.name.startswith(".") or f.name in EXCLUDED_LESSON_FILES:
                continue
            seen.setdefault(f.stem, f)
    return list(seen.values())
