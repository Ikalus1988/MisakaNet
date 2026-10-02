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

import subprocess

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


def tracked_lesson_files(lessons_root: Path) -> list[Path] | None:
    """The lesson files git tracks under ``lessons_root``, or ``None`` when git cannot answer.

    The index used to be built from the filesystem (``rglob``), so anything a local tool left behind —
    an editor scratch file, a draft, a stray ``.md`` — entered the search corpus here while CI and the
    hosted worker never saw it. That is the audit's P7: the mechanism is real, and the reason a dirty
    tree reported two more files than a clean one is that the walk cannot tell "in the repository"
    from "on this disk".

    Files are the index's subject, so git is the authority whenever it can answer. A checkout without
    git (an installed package, an exported tarball, a test fixture that is not a repository) gets the
    walk instead, which is exactly the old behaviour.

    ``-c core.quotepath=false`` is load-bearing: without it git escapes non-ASCII paths as octal
    inside quotes, and this repository has CJK lesson filenames. `scripts/push_preflight.py` records
    the same lesson, learned the same way.
    """
    if not lessons_root.is_dir():
        return None
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "--", "."],
            cwd=lessons_root, capture_output=True, text=True, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):  # git missing, or not a repository
        return None
    if proc.returncode != 0:
        return None
    found = [lessons_root / line for line in proc.stdout.splitlines() if line.endswith(".md")]
    found = [path for path in found if path.is_file()]
    if not found:
        # "Git says there are no lessons here" is not an answer this can act on. It is either a tree
        # that genuinely has none (in which case the walk below also finds none, and nothing changes)
        # or a `subprocess.run` that no longer reaches git — which is a real shape in this repository:
        # tests stub `subprocess.run` globally (the module object is shared), and a stub returning
        # success with no output turned the rebuilt index **empty**. Measured on 2026-10-02: PR #2708's
        # CI legs all failed in `test_no_test_writes_repo_data.py` with "the redirected index … was
        # never written, so the rebuild did not run", because the generator had enumerated nothing.
        # A caller who wants untracked files excluded still gets that: git answers with paths whenever
        # it can, and this branch is only reached when it answers with none.
        return None
    return found


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
    tracked = tracked_lesson_files(lessons_root)
    for d in dirs:
        candidates = ([p for p in tracked if p.is_relative_to(d)] if tracked is not None
                      else list(d.rglob("*.md")))
        for f in sorted(candidates):
            if f.name.startswith(".") or f.name in EXCLUDED_LESSON_FILES:
                continue
            seen.setdefault(f.stem, f)
    return list(seen.values())
