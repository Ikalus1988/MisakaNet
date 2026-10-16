#!/usr/bin/env python3
"""A contributed lesson must land where the corpus reads (2026-10-17).

`contribute()` wrote the lesson to `lessons/<slug>.md` — the root of `lessons/`, which is outside
every directory the corpus reads. `lesson_gate.ACTIVE_LESSON_SUBDIRS` owns that rule and
`validate_location` enforces it ("Nothing reads a markdown file outside those directories"), while
`update_lessons_json.py` only walks `INDEXED_DIRS = ("core", "contrib")`. So the pull request could
look complete and the lesson would never appear in search — the same "the artifact lost its
content and nothing went red" shape as the silent truncation in `scripts/intake_pipeline.py`
(intake #2760).

The fix reuses the gate's own rule rather than restating it, so this file drives the real
`contribute()` with a stubbed `_api` and then asks `lesson_gate.validate_location` about the path
that was actually committed. The second test is the guard on the guard: it pins that the reused
rule still rejects a root-level file, so a change that made `validate_location` permissive could
not make the first test pass for the wrong reason.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import contribute  # noqa: E402
import lesson_gate  # noqa: E402


def _committed_paths(monkeypatch, tmp_path: Path) -> list[str]:
    """Drive the real `contribute()` with a stubbed GitHub API; return the tree paths it wrote."""
    calls: list[tuple[str, dict | None]] = []

    def fake_api(path, data=None, method="POST"):
        calls.append((path, data))
        return {
            "git/ref/heads/main": {"object": {"sha": "base-sha"}},
            "git/refs": {"ref": "refs/heads/contribute/x"},
            "git/blobs": {"sha": "blob-sha"},
            "git/trees": {"sha": "tree-sha"},
            "git/commits": {"sha": "commit-sha"},
            "pulls": {"html_url": "https://example.invalid/pr/1", "title": "t"},
        }.get(path, {"ref": path})

    lesson = tmp_path / "lesson.md"
    lesson.write_text("irrelevant: the loader is stubbed below\n", encoding="utf-8")

    monkeypatch.setattr(contribute, "_api", fake_api)
    monkeypatch.setattr(contribute, "_get_token", lambda: "token")
    monkeypatch.setattr(contribute, "_read_lesson", lambda path: defaultdict(str, {
        "title": "A contributed lesson", "domain": "python", "tags": ["test"],
        "content": "## Problem\nsomething broke\n", "filename": "x.md",
    }))
    assert contribute.contribute(str(lesson)) is True, "the stubbed run did not reach the PR"
    return [data["tree"][0]["path"] for path, data in calls if path == "git/trees"]


def test_a_contribution_is_committed_where_the_corpus_reads(monkeypatch, tmp_path: Path):
    paths = _committed_paths(monkeypatch, tmp_path)
    assert paths == [f"lessons/{contribute.NEW_LESSON_SUBDIR}/a-contributed-lesson.md"], paths
    relative = paths[0]
    assert lesson_gate.validate_location(REPO / relative, REPO) == [], (
        "contribute() committed a lesson the repository's own location rule rejects, so nothing "
        "would ever read it"
    )
    assert relative.split("/")[1] in lesson_gate.ACTIVE_LESSON_SUBDIRS, (
        "the committed path is outside ACTIVE_LESSON_SUBDIRS — every discovery path filters on it"
    )


def test_the_reused_location_rule_still_rejects_the_old_target():
    """Guard the guard: the assertion above only means something while the rule can say no."""
    assert lesson_gate.validate_location(REPO / "lessons" / "a-contributed-lesson.md", REPO), (
        "a lesson at the root of lessons/ is no longer rejected — the check above proves nothing"
    )
    assert lesson_gate.validate_location(REPO / "lessons" / "not-a-lesson-dir" / "x.md", REPO)
    assert contribute.NEW_LESSON_SUBDIR in lesson_gate.ACTIVE_LESSON_SUBDIRS
