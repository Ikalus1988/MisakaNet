#!/usr/bin/env python3
"""Audit 2026-09-05 T2.2: lesson-directory auto-discovery ("library" policy).

Maintainer decision: the index is a library — every lessons/ subdirectory
with real lesson content is visible (core/contrib + locale dirs like en/ +
lifecycle dirs), only scaffolding (templates/, _archive/) and per-directory
index/README files are excluded. Adding a new published directory must need
no engine code change.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from misakanet.lesson_index import (  # noqa: E402
    EXCLUDED_LESSON_DIRS,
    EXCLUDED_LESSON_FILES,
    discover_lesson_dirs,
)

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"


def test_discovery_includes_all_content_dirs():
    dirs = {d.name for d in discover_lesson_dirs(LESSONS)}
    # Real content lives in all of these today
    assert {"core", "contrib", "en", "user-rescue"} <= dirs
    # Scaffolding / retired dirs are never discovered
    assert not (dirs & set(EXCLUDED_LESSON_DIRS))
    # Every discovered dir really contains at least one non-index lesson file
    for d in discover_lesson_dirs(LESSONS):
        assert any(
            f.name not in EXCLUDED_LESSON_FILES and f.suffix == ".md"
            for f in d.rglob("*.md")
        ), f"{d} discovered but has no lesson files"


def test_new_published_dir_needs_no_code_change(tmp_path):
    """A brand-new dir (simulating lessons/verified/) is picked up as-is."""
    root = tmp_path / "lessons"
    (root / "core").mkdir(parents=True)
    (root / "core" / "pip-timeout.md").write_text("---\ntitle: pip timeout\n---\nbody\n")
    (root / "templates").mkdir()
    (root / "templates" / "x.md").write_text("placeholder\n")
    (root / "_archive").mkdir()
    (root / "_archive" / "old.md").write_text("old\n")
    (root / "verified").mkdir()
    (root / "verified" / "my-verified-lesson.md").write_text(
        "---\ntitle: verified fix\n---\nbody\n"
    )

    found = {d.name for d in discover_lesson_dirs(root)}
    assert found == {"core", "verified"}


def test_engine_loader_uses_discovery(tmp_path):
    """misakanet.search.engine loads docs from discovered dirs (en/ included)
    and never from excluded ones or README/index files."""
    import sys as _sys

    _sys.path.insert(0, str(REPO))
    from misakanet.search.engine import LESSONS, _load_docs_cached  # noqa: E402

    docs = _load_docs_cached(LESSONS, is_lesson=True)
    paths = [str(d.filepath.relative_to(REPO)) for d in docs]

    assert any(p.startswith("lessons/en/") for p in paths), "en lessons missing"
    assert any(p.startswith("lessons/user-rescue/") for p in paths), "user-rescue missing"
    assert not any(p.startswith("lessons/templates/") for p in paths), "templates leaked"
    assert not any(p.startswith("lessons/_archive/") for p in paths), "_archive leaked"
    assert not any(p.endswith("/README.md") for p in paths), "README.md leaked"
