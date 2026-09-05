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
