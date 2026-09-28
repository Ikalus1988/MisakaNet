#!/usr/bin/env python3
"""LessonReuseBench is a stub, and three public pages said it was a runnable benchmark.

Measured 2026-09-25, by running it:

```
$ python3 scripts/lesson_reuse_bench.py --dry-run
ModuleNotFoundError: No module named 'agents'
```

`scripts/lesson_reuse_bench.py:4` imports `agents.YourAgent`, which does not exist; `calculate_score` is a
literal placeholder (*"Placeholder for actual score calculation"*, `return 1.0 if result == "success" else
0.0`); the three pairs are hardcoded in the script while the real pair files in `tasks/reuse/` (10 of them) are
read by nothing; and the `--tasks` flag the design doc documents does not exist. `docs/articles/
can-agents-learn-from-failures.md` nonetheless reported **four results** "from our initial dry-run
validation", including "the scoring correctly rewards agents that retrieve and adapt lessons"; the design doc
published an example output with `total_score: 0.92 / delta_vs_no_lesson: 0.35`; and the challenge page invited
people to run it and submit results.

The internal audits had both facts already
(`docs/maintainer/capability-inventory-new-user-2026-09-18.md:52`, `docs/maintainer/strategic-assessment-2026-09-18.md:64`)
— this is the second benchmark in a row whose public surface outran its implementation.

The rules below keep the *status* and the *code* in step: while the stub markers are present, the public pages
must carry the status note; if someone implements the harness, the markers have to go and the note with them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "lesson_reuse_bench.py"
DESIGN = REPO / "docs" / "lesson-reuse-benchmark.md"
CHALLENGE = REPO / "docs" / "benchmark-challenge.md"
ARTICLE = REPO / "docs" / "articles" / "can-agents-learn-from-failures.md"
PAGES = (DESIGN, CHALLENGE, ARTICLE)

# The markers that make it a stub. They are checked as a set: implementing the harness means removing them.
STUB_MARKERS = (
    "from agents import YourAgent",
    "Placeholder for actual score calculation",
)
# The one place the status lives, referenced by every page that used to present the harness as runnable.
STATUS_POINTER = "issues/2221"


def stub_markers_present() -> list[str]:
    code = SCRIPT.read_text(encoding="utf-8")
    return [marker for marker in STUB_MARKERS if marker in code]


def test_the_public_pages_state_that_the_harness_cannot_run():
    markers = stub_markers_present()
    if not markers:
        pytest.skip("the harness has been implemented — the status notes should have been removed with it")
    missing = [p.relative_to(REPO).as_posix() for p in PAGES if "cannot run" not in p.read_text(encoding="utf-8")
               and "not open yet" not in p.read_text(encoding="utf-8")
               and "is a stub" not in p.read_text(encoding="utf-8")]
    assert not missing, (
        "these pages present LessonReuseBench as runnable while its script is still a stub "
        f"({markers}):\n  - " + "\n  - ".join(missing))


def test_every_page_that_names_the_script_points_at_the_status():
    """A reader who lands on the run command must be able to find out that it fails today."""
    offenders = []
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        if "lesson_reuse_bench.py" in text and STATUS_POINTER not in text:
            offenders.append(page.relative_to(REPO).as_posix())
    assert not offenders, (
        "these pages tell the reader to run the harness without pointing at its status:\n  - "
        + "\n  - ".join(offenders))


FABRICATED = (
    "All 3 task pairs are structurally valid",
    "The scoring correctly rewards agents that retrieve and adapt lessons",
    "Task B always has a relevant lesson available in the pool",
    "The biggest differentiator is whether the agent *searches* before *debugging*",
)


def test_the_fabricated_results_are_gone():
    """The four bullets described a dry run that exits at import.

    They may appear **inside** the correction table (that is what a retraction looks like) and nowhere else —
    the first version of this rule accepted "the claim is somewhere in the file next to the table", which
    passed while the claim was restored as a bullet outside it. A rule with that escape hatch is decoration.
    """
    lines = ARTICLE.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().startswith("| then | now |")), None)
    assert start is not None, (
        "the correction table is gone — these four claims were never measured, so the retraction has to stay")
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip().startswith("|")), len(lines))
    outside = "\n".join(lines[:start] + lines[end:])
    for claim in FABRICATED:
        assert claim not in outside, (
            f"{claim!r} is asserted outside the correction table; nothing ever measured it")


def test_the_example_output_is_labelled_as_an_illustration():
    text = DESIGN.read_text(encoding="utf-8")
    assert "illustration, not a measurement" in text, (
        "the design doc prints a `total_score`/`delta_vs_no_lesson` example; it must say it is not measured")


def test_the_rule_notices_a_page_that_promises_a_runnable_benchmark(tmp_path):
    """Guard the guard: the challenge page's original sentence is what this rule was written against."""
    page = tmp_path / "x.md"
    page.write_text("We're inviting agent developers to run LessonReuseBench and share results.\n",
                    encoding="utf-8")
    text = page.read_text(encoding="utf-8")
    assert "cannot run" not in text and "is a stub" not in text and "not open yet" not in text
    assert stub_markers_present(), "the script is no longer a stub — revisit this file's premise"
