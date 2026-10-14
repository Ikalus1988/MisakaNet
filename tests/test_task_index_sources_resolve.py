#!/usr/bin/env python3
"""Every `tasks/index.json` row must name a lesson that is actually there.

The defect this exists for
--------------------------
`tasks/` is a benchmark snapshot written by `scripts/extract_tasks.py`, and nothing runs that
script in CI — `grep -rn "extract_tasks" .github/ Makefile` returns nothing. So the snapshot is
only ever as fresh as the last time a maintainer remembered to run it. Measured 2026-10-14 on
`main` (`2fe56022`): **50 of 98 rows pointed at a `source` that no longer existed**, in two shapes:

* **43 orphaned** — the lesson was deleted from the corpus, but `extract_tasks.py` never prunes,
  so both the task JSON and its index row stayed behind. 43 of the 50 were under
  `lessons/contrib/`.
* **7 relocated** — the lesson moved (`lessons/auto-merge-ci-pipeline.md` →
  `lessons/core/auto-merge-ci-pipeline.md`; three into `lessons/en/`). The task survived, its
  `source` did not.

Neither shape raises anything. `scripts/misaka_verify.py:56` returns `SKIP` when the source is
missing, so **4 of the 10 tasks that carry a `test_cmd` silently skipped their verification**
instead of failing — a benchmark set that quietly verifies less than it appears to.

Why this gate is narrow
-----------------------
It is deliberately *not* "regenerate and assert freshness". Measured the same day, a regeneration
would produce **415 files from 98** (441 extractions, 26 of which collide on `task_id` between
`lessons/contrib/X.md` and its `lessons/en/X.md` twin, so only the alphabetically-later one
survives). Whether this benchmark set should be 98 or 415 is a scope decision, not a truth
question, and the collision would silently substitute English lessons for Chinese ones. So this
gate asserts only the invariant with **no legitimate exception**: a row that claims to come from
a file has to point at that file. Exactly the reasoning in `test_cited_lesson_paths_exist.py`,
narrowed to the one directory that has no "historical record" excuse.

`tasks/reuse/` is out of scope: it uses a different schema (`{name, pair, phase, ...}`) and
`tests/test_reuse_benchmark_status.py` already records that nothing reads it.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TASKS = REPO / "tasks"
INDEX = TASKS / "index.json"


def unresolved(rows: list[dict], repo: Path = REPO) -> list[str]:
    """`rows` whose `source` is not a file under `repo`. The one predicate both tests below use."""
    out = []
    for row in rows:
        source = row.get("source")
        if not source or not (repo / source).is_file():
            out.append(f"{row.get('task_id')} -> {source}")
    return out


def test_every_index_row_names_a_lesson_that_exists():
    rows = json.loads(INDEX.read_text(encoding="utf-8"))
    assert rows, "tasks/index.json parsed as an empty list — that is a failure, not a pass"
    dead = unresolved(rows)
    assert not dead, (
        f"{len(dead)} of {len(rows)} tasks/index.json rows name a source that does not exist:\n  "
        + "\n  ".join(dead[:10])
        + "\nRe-run `python3 scripts/extract_tasks.py` to repoint them, or delete the rows whose "
        "lesson is gone from the corpus. A task whose source is missing is skipped silently by "
        "scripts/misaka_verify.py, so this is not loud."
    )


def test_no_task_file_on_disk_is_missing_from_the_index():
    """The other direction: rot that is on disk but unindexed is invisible to the test above.

    `extract_tasks.py` writes one file per task and rewrites the index, so the two can only drift
    if a file is added or removed by hand — which is exactly how the 43 orphans accumulated.
    """
    rows = json.loads(INDEX.read_text(encoding="utf-8"))
    indexed = {row["task_id"] for row in rows}
    on_disk = {p.stem for p in TASKS.glob("lesson-*.json")}
    assert not (on_disk - indexed), (
        f"{len(on_disk - indexed)} file(s) in tasks/ are not in tasks/index.json:\n  "
        + "\n  ".join(sorted(on_disk - indexed)[:10])
    )


def test_the_predicate_itself_catches_a_dead_source(tmp_path):
    """The self-test: this file is evidence only if it fails on the shape it was added for.

    Without this, a predicate that returned `[]` for everything would make both tests above pass
    unconditionally — the "a gate that cannot fail" shape this repository has hit before
    (`test_no_branch_of_run_verification_returns_something_other_than_a_pair` exists for the same
    reason). Asserting `== []` on a real list proves the gate is wired up; it does not prove the
    predicate bites.

    Both halves are checked against `tmp_path` rather than against real index rows, so neither
    depends on which task happens to sort first. An earlier draft read `index[0]` for the live
    half, and under mutation it failed for the wrong reason — it had picked a genuinely dead row
    and flagged it, which looks like a pass of the *gate* but is an accident of ordering.
    """
    (tmp_path / "live.md").write_text("x", encoding="utf-8")
    assert unresolved([{"task_id": "gone", "source": "not-there.md"}], tmp_path)
    # …and a row whose source exists must not trip it, or the gate is vacuous the other way.
    assert not unresolved([{"task_id": "live", "source": "live.md"}], tmp_path)
    # A row with no `source` at all is also unresolved — it cannot be resolved by definition.
    assert unresolved([{"task_id": "bare"}], tmp_path)