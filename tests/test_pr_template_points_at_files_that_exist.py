#!/usr/bin/env python3
"""The pull-request template's links must land on files this repository has.

Why this exists (2026-11-15)
---------------------------
Two of the five `lessons/…` links in `.github/PULL_REQUEST_TEMPLATE.md` were dead: both named
`lessons/core/…` for lessons that live in `lessons/contrib/`. The template is the first page a
contributor reads and the last thing anyone re-reads, so a 404 there costs a newcomer a click and
costs nobody an alarm — nothing in this repository ever opened it.

The checklist had a matching defect in the other direction: it told contributors **not** to touch the
generated files, while the `gate` job fails a lesson pull request that has not re-run them

    A lesson was added or changed without re-running the generators that write the files `main` keeps.

So the template is checked, not trusted: every `blob/main/<path>` it names must exist, and the
generated-files line must name the four generators the gate actually runs.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / ".github" / "PULL_REQUEST_TEMPLATE.md"


def text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_every_linked_repository_path_exists():
    dead = [path for path in re.findall(r"blob/main/([^)\s]+)", text())
            if not (REPO / path).exists()]
    assert not dead, (
        "the pull-request template links to files this repository does not have — a contributor "
        f"clicking those gets a 404, and nothing else here would ever notice: {dead}")


def test_the_generated_files_item_names_the_generators_the_gate_runs():
    """The checklist and the `gate` job must ask for the same thing.

    `lesson-gate.yml`'s "Main-side generated files must match the corpus" step runs exactly these
    four and fails on any diff. A checklist that says the opposite ("do not modify generated files,
    the maintainer will regenerate after merge") is a rule that guarantees a red build for anyone
    who follows it.
    """
    body = text()
    # `build_lesson_pages.py` is the one that bit: the gate step runs four generators and stays green,
    # while nine `test` jobs go red on pages, sitemap, redirects, topic counts, the vocabulary and the
    # ranking fixture. A checklist that names only the gate's four is a checklist that reports success
    # too early.
    for script in ("update_lessons_json.py", "build_lesson_pages.py", "sync_lesson_count.py",
                   "export_okf.py", "rebuild_lessons_index.py", "export_public_vocabulary.py",
                   "gen_ranking_snapshot.py"):
        assert script in body, f"the checklist does not name {script}"
    assert "repo-operations.md" in body, "the checklist must point at the list it summarises"
    assert "maintainer will regenerate after merge" not in body, (
        "that line contradicts the gate: a lesson pull request without the regenerated files fails")
