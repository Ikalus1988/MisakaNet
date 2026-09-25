#!/usr/bin/env python3
"""`data/okf/lessons.jsonl` must keep describing the corpus it claims to describe (#2185).

The file is **tracked**, and for two and a half months nothing regenerated it: last written 2026-07-07 with
194 records while the corpus grew to 411. It looked healthy from every angle a person checks — in the
repository, valid JSONL, readable by `build_sag_index.py` — and the failure only showed up in the *relation*
between the two: `data/sag.db` is built from this file, `misakanet/server/handlers/search.py` prefers SAG over
the complete BM25 path, so following the documented setup produced an index covering 47% of the corpus and
made recall **worse** than building nothing.

The rule is therefore a relation, not a number: the export must cover the canonical corpus to within
`COVERAGE_FLOOR`. A lesson added by a pull request does not trip it (the daily `update-lessons.yml` job
regenerates the export and lands it through the self-merging pull request), but "the writer stopped" or "the
file was reverted" does — which is exactly the state that sat in `main` for ten weeks.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

EXPORT = REPO / "data" / "okf" / "lessons.jsonl"
SCRIPT = REPO / "scripts" / "export_okf.py"
WORKFLOW = REPO / ".github" / "workflows" / "update-lessons.yml"

from scripts.build_sag_index import COVERAGE_FLOOR  # noqa: E402  — one floor, not two


def tracked_records() -> list[dict]:
    return [json.loads(line) for line in EXPORT.read_text(encoding="utf-8").splitlines() if line.strip()]


def corpus_size() -> int:
    from misakanet.lesson_index import canonical_lessons

    return sum(1 for path in canonical_lessons(REPO / "lessons") if path.name != "README.md")


# ── the relation ────────────────────────────────────────────────────────────────────
def test_the_tracked_export_covers_the_corpus():
    covered, total = len(tracked_records()), corpus_size()
    assert total > 0, "no lessons found — the probe is broken, not the export"
    missing = total - covered
    assert covered >= total * COVERAGE_FLOOR, (
        f"data/okf/lessons.jsonl names {covered} of {total} lessons ({missing} missing, "
        f"{100 * missing / total:.0f}%). `data/sag.db` is built from this file and the search path prefers "
        "SAG over the complete BM25 index, so a stale export makes local search *worse* than not building an "
        "index at all (#2185). Run `python3 scripts/export_okf.py` — the daily `update-lessons.yml` job is "
        "supposed to keep it fresh, so this failing usually means that step stopped working.")


def test_every_tracked_record_is_about_a_lesson_that_still_exists():
    """A stale export does not only miss lessons; it keeps naming the ones that were deleted or renamed."""
    live = {r["path"] for r in _fresh_records()}
    ghosts = sorted({r["path"] for r in tracked_records() if r.get("path")} - live)
    assert not ghosts, f"the export names lessons that are not in the corpus any more: {ghosts[:5]}"


def _fresh_records() -> list[dict]:
    from scripts.export_okf import build_records

    return build_records()


def test_the_export_is_deterministic():
    """The file is refreshed daily by a job that commits only when something changed; a non-reproducible
    export would produce a commit every day and a diff nobody can review."""
    assert _fresh_records() == _fresh_records()


def test_the_fresh_export_matches_the_tracked_bytes():
    """Not a contributor-facing gate (a lesson PR does not have to regenerate this) — a check on the writer:
    if the tracked file disagrees with a fresh export *while covering the same corpus*, the daily job is
    writing something different from what `--check` reads."""
    from scripts.export_okf import serialise

    fresh = serialise(_fresh_records())
    tracked = EXPORT.read_text(encoding="utf-8")
    if len(fresh.splitlines()) != len(tracked.splitlines()):
        pytest.skip("coverage differs — the relation is checked above; this rule is about byte drift")
    assert fresh == tracked, (
        "the tracked export differs from a fresh export of the same corpus — check that the writer and "
        "`--check` share one implementation (`serialise`)")


# ── `--check`, the thing a person runs ──────────────────────────────────────────────
def test_check_mode_passes_on_the_current_export():
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "up to date" in proc.stdout, proc.stdout


def test_check_mode_fails_on_a_stale_copy(tmp_path):
    """Replayed on the historical state: the tracked file truncated to the 194 records it had."""
    stale = tmp_path / "okf"
    stale.mkdir()
    (stale / "lessons.jsonl").write_text(
        "\n".join(EXPORT.read_text(encoding="utf-8").splitlines()[:194]) + "\n", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", "--output", str(stale)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "STALE" in proc.stderr, proc.stderr
    assert "export_okf.py" in proc.stderr, "the message must say how to fix it"


def test_check_mode_reports_a_missing_export_as_missing(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", "--output", str(tmp_path)],
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "does not exist" in proc.stderr, proc.stderr


# ── the writer, so the relation has a mechanism rather than a habit ─────────────────
def test_the_daily_job_regenerates_the_export():
    """#2185's first ask: give the file a writer. Without one this gate would only tell the maintainer that
    the file is stale, which is what the issue was."""
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    steps = next(iter(jobs.values()))["steps"]
    runs = [str(step.get("run") or "") for step in steps]
    assert any("export_okf.py" in run for run in runs), (
        "nothing in update-lessons.yml regenerates data/okf/lessons.jsonl, so it is a tracked file with no "
        "writer again — the state #2185 describes")
    assert any("land_change.py" in run for run in runs), (
        "the regenerated export must land through the self-merging pull request like every other artifact "
        "this job produces, or the work is discarded by the ruleset on main")
    assert "lessons.jsonl" in WORKFLOW.read_text(encoding="utf-8"), (
        "the lander's note should name the file it now lands")


def test_the_floor_is_the_same_one_the_index_builder_warns_with():
    """Two floors would mean the warning and the gate disagree about what 'stale' is."""
    text = (REPO / "scripts" / "build_sag_index.py").read_text(encoding="utf-8")
    assert "COVERAGE_FLOOR" in text and "warn_if_export_is_stale" in text, text[:200]
