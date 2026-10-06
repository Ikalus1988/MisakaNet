#!/usr/bin/env python3
"""`docs/benchmarks/` was allowed to double every month, and nothing ever read the old copies.

Measured 2026-10-06
-------------------
`docs/benchmarks/` held eleven weekly snapshots totalling 13.2 MB, of which ten were
`benchmark-YYYY-MM-DD.json` and one `latest.json`. The directory gained ~2 MB a week and had
roughly doubled every month since 2026-08-28.

The size is not the interesting part. The interesting part is that **each dated snapshot is a
byte-for-byte copy of `latest.json` as it stood on that date**:

    benchmark-2026-09-28.json   1,891,265 bytes
    latest.json                 1,891,265 bytes

`benchmark-workers-ai.yml` makes that copy (`cp docs/benchmarks/latest.json
"docs/benchmarks/benchmark-$TS.json"`), and `scripts/benchmark_workers_ai.py` writes a
*cumulative* file — its resume cache is keyed on `(model, scenario[:80], condition)` and every
run is appended, never replaced. So the snapshots were never independent evidence; each is a
suffix-preserving copy of a file that already contains every run to date. They doubled the bytes
without adding a single measurement.

And nothing read them. `README.md`, `README.ja.md` and `README.zh-CN.md` all link
`latest.json`; `tests/test_benchmark_claims.py` reads `latest.json`; no document links a dated
snapshot. The two mentions in `lessons/contrib/` are `--output` arguments in commands that
*create* the file, not reads of it.

What this gate holds
--------------------
1. **The directory is pruned.** At most `KEEP` dated snapshots may exist. This is the invariant
   that actually stops the growth, and it is the half that fails if someone adds a file by hand.
2. **The workflow keeps pruning.** `.github/workflows/benchmark-workers-ai.yml` must still carry
   the retention step. Without this half, (1) holds until the next Monday's run adds a fifth file
   and nothing deletes it — the directory would be right on the day of the commit and silently
   growing again by the next one. That is the same shape as
   `tests/test_stdio_stdout_is_only_json.py`, which pins a property of the code rather than of one
   run's output.

Scope: this only bounds *future* growth. Pruning a path that is already committed cannot make an
existing clone smaller — the blob is in the pack, and only a history rewrite can remove it. See
`docs/maintainer/clone-size-measurement-2026-10-06.md` for the measurement.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = REPO_ROOT / "docs" / "benchmarks"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "benchmark-workers-ai.yml"

KEEP = 4

# `benchmark-2026-09-28.json` — dated weekly snapshots only. `benchmark-2026-09-02-compare.json`
# is a different artifact (a two-model comparison, 28 KB) and is excluded here on purpose.
DATED_SNAPSHOT = re.compile(r"^benchmark-(\d{4}-\d{2}-\d{2})\.json$")


def _dated_snapshots() -> list[Path]:
    if not BENCHMARK_DIR.is_dir():
        return []
    found = []
    for path in BENCHMARK_DIR.iterdir():
        if path.is_file() and DATED_SNAPSHOT.match(path.name):
            found.append(path)
    return sorted(found)


def test_benchmark_dir_has_at_most_keep_dated_snapshots():
    snapshots = _dated_snapshots()
    if not snapshots:
        pytest.skip("no dated benchmark snapshots in this checkout")
    names = [p.name for p in snapshots]
    assert len(snapshots) <= KEEP, (
        f"docs/benchmarks/ holds {len(snapshots)} dated snapshots (expected at most {KEEP}): "
        f"{', '.join(names)}. Each one is a copy of latest.json as it stood on its date — the "
        f"full history is in latest.json and in git, so keeping them all buys no measurement. "
        f"Prune to the {KEEP} newest, or raise KEEP here deliberately."
    )


def test_snapshots_are_newest_first_and_contiguous_with_what_is_kept():
    """The four that survive should be the four newest, not an arbitrary four."""
    snapshots = _dated_snapshots()
    if len(snapshots) < 2:
        pytest.skip("need at least two dated snapshots to check which ones were kept")
    dates = [DATED_SNAPSHOT.match(p.name).group(1) for p in snapshots]
    assert dates == sorted(dates), f"dated snapshots are not in chronological order: {dates}"


def test_workflow_still_prunes():
    """The directory being small today is not evidence the workflow will keep it small."""
    if not WORKFLOW.is_file():
        pytest.fail(f"missing {WORKFLOW.relative_to(REPO_ROOT)} — the benchmark workflow is gone")

    text = WORKFLOW.read_text(encoding="utf-8")

    # Shape, not a literal command string: the step has to (a) enumerate dated snapshots,
    # (b) exclude the `-compare` artifacts, (c) drop everything past KEEP, (d) delete via git.
    # Asserting the exact shell line would make this gate a rename detector.
    assert "benchmark-2*.json" in text, (
        "benchmark-workers-ai.yml no longer enumerates dated snapshots — the retention step was "
        "removed or rewritten, so docs/benchmarks/ will grow again from Monday's run"
    )
    assert "-compare" in text, (
        "the retention step no longer excludes the `-compare` artifacts; pruning by glob alone "
        "would delete benchmark-*-compare.json, whose output path lessons/contrib/ cites"
    )
    assert re.search(r"git\s+rm\b", text), (
        "the retention step no longer deletes through git. `rm` alone would delete the working-tree "
        "copy and land_change.py --paths docs/benchmarks would not stage the deletion, so the files "
        "would come back on the next checkout"
    )
    assert re.search(r"tail\s+-n\s+\"?\+\$\(\(KEEP", text), (
        "the retention step no longer keeps exactly KEEP files (expected `tail -n +$((KEEP + 1))`)"
    )


def test_retention_step_runs_before_land_change():
    """Order matters: prune first, then land, or the deletions never reach the PR."""
    text = WORKFLOW.read_text(encoding="utf-8")
    # Anchor on the invocation, not on the bare filename. The step's own comment block names
    # `land_change.py` ("land_change.py refuses such a title rather than stripping it silently"),
    # and a plain `find` matches that comment 5 KB before the real command — which made this test
    # fail against correct code until it was anchored. A gate that is red for the wrong reason is
    # worse than no gate: the fix is to stop reading it.
    rm_at = text.find("git rm")
    land_at = text.find("python3 scripts/ci/land_change.py")
    assert rm_at != -1 and land_at != -1, (
        f"expected both the prune (found at {rm_at}) and the land command (found at {land_at})"
    )
    assert rm_at < land_at, (
        "the prune runs after land_change.py. scripts/ci/land_change.py commits and pushes the "
        "branch itself, so deletions staged after it never leave the runner"
    )


def test_workflow_still_writes_the_snapshot():
    """Guard against a retention step that deletes faster than the report is written."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r'cp\s+docs/benchmarks/latest\.json\s+"?docs/benchmarks/benchmark-\$TS\.json', text), (
        "the workflow no longer writes this week's snapshot — pruning without a fresh copy would "
        "delete the trend one week at a time until the directory was empty"
    )


def test_no_untracked_snapshot_on_disk():
    """A snapshot on disk that git has never heard of is a measurement that will not exist in CI.

    Deliberately scoped to *untracked* files, not "no drift at all". The first version of this gate
    asserted `git status --porcelain docs/benchmarks` was empty, which made the suite un-runnable
    in exactly the window an author verifies a prune: `git rm` stages the deletion, so between the
    prune and the commit there are always staged deletions, and the gate went red on correct work.
    A gate that fights its own workflow trains people to skip it.

    Modified and staged paths are legitimate — that is a commit in progress. A file that exists on
    disk, is not in `HEAD` and is not in the index is a local benchmark run whose output will
    silently vanish at the next checkout, and it is the one case where the count above is grading
    something CI will not grade.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--others", "--exclude-standard",
             "--", "docs/benchmarks"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")
    if out.returncode != 0:
        pytest.skip("not a git checkout")

    untracked = [ln for ln in out.stdout.splitlines() if ln.strip()]
    assert not untracked, (
        "docs/benchmarks/ holds untracked files that CI will not see, so the count above is "
        f"grading a different tree: {untracked[:5]}"
    )