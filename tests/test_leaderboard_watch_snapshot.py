#!/usr/bin/env python3
"""The leaderboard snapshot is written only when the leaderboard actually changes.

`leaderboard-watch.yml` runs on **every push to main**, recomputes the leaderboard, compares it with the
committed snapshot, opens an issue when #1 changes, and commits the new snapshot.

The defect these tests pin: it wrote the snapshot **unconditionally**, and stamped a fresh `updated_at` into
`data/leaderboard_meta.json` every run. So the workflow's own `git diff --cached --quiet` guard could never
fire — the diff was never empty — and every push produced a commit whose only change was a timestamp:

* **1,026 commits** in the repository history (25% of all 4,033) carry the message
  `chore: update leaderboard snapshot [skip ci]`;
* 955 of them touch `data/leaderboard.json`, 494 touch `data/leaderboard_meta.json`, and nothing reads
  either file (the site 404s them, only `data/pr-genius-stats.json` is fetched anywhere, and the live
  leaderboard comes from the Worker's `/api/insights/reputation-leaderboard`);
* and on 2026-09-20 that churn broke a release: the npm publish job's record step was rejected as a
  non-fast-forward (`! [rejected] HEAD -> main (fetch first)`) because main had moved under it.

The fix is one condition — write the state only when the state changed — which restores the guard that was
always there. The tests use the real `main()` against a scratch directory, with only the two things that need
the network patched out, so the assertion is about the script's behaviour rather than about its source text.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "leaderboard_watch.py"


@pytest.fixture()
def watcher(tmp_path, monkeypatch):
    """The real module, pointed at a scratch repository and with the network calls patched out."""
    spec = importlib.util.spec_from_file_location("leaderboard_watch_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    # The bench leaderboard file has to exist, and this is not cosmetic: `bench_top` drives whether
    # `save_meta` runs at all, so without it `leaderboard_meta.json` is never written and a test that
    # forgets it cannot see the `updated_at` stamp that caused the commit-per-push in the first place.
    # (The first version of this file forgot it, and the mutation check below passed — a test that
    # cannot fail.)
    (tmp_path / "data" / "bench_leaderboard.json").write_text(
        json.dumps({"leaderboard": [{"agent": "minimax", "passed": 14}]}), encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "LEADERBOARD_FILE", tmp_path / "data" / "leaderboard.json")
    monkeypatch.setattr(module, "META_FILE", tmp_path / "data" / "leaderboard_meta.json")
    monkeypatch.setattr(module, "TOKEN", "test-token")          # main() refuses to run without one
    monkeypatch.setattr(module, "DRY_RUN", False)

    issued: list[dict] = []
    monkeypatch.setattr(module, "create_notification_issue",
                        lambda new_top, old_top, changed: issued.append(new_top) or True)

    def with_leaderboard(rows):
        monkeypatch.setattr(module, "compute_leaderboard", lambda: rows)

    module.with_leaderboard = with_leaderboard          # type: ignore[attr-defined]
    module.issued = issued                              # type: ignore[attr-defined]
    return module


def _snapshot(path: Path):
    return path.read_bytes() if path.exists() else None


def test_a_run_without_a_material_change_writes_nothing(watcher, tmp_path):
    """The churn case: same #1, same score → no write → no commit (the guard can finally fire)."""
    rows = [{"login": "zsxh1990", "score": 94.83}, {"login": "2lll5", "score": 2.94}]

    watcher.with_leaderboard(rows)
    watcher.main()
    first_leaderboard = _snapshot(tmp_path / "data" / "leaderboard.json")
    first_meta = _snapshot(tmp_path / "data" / "leaderboard_meta.json")
    assert first_leaderboard, "the first run has no previous snapshot, so it must write one"

    watcher.with_leaderboard([dict(row) for row in rows])       # same values, new objects
    watcher.main()

    assert _snapshot(tmp_path / "data" / "leaderboard.json") == first_leaderboard, (
        "an unchanged leaderboard must not rewrite the snapshot: rewriting it is what produced a commit "
        "per push (1,026 of them, 25% of the repository's history)")
    assert _snapshot(tmp_path / "data" / "leaderboard_meta.json") == first_meta, (
        "meta must not be rewritten either - a fresh `updated_at` alone was enough to make every run look "
        "like a change")


def test_a_material_change_still_writes_and_notifies(watcher, tmp_path):
    """The other direction: the rule must not silence the thing the workflow exists for."""
    watcher.with_leaderboard([{"login": "zsxh1990", "score": 94.83}, {"login": "2lll5", "score": 2.94}])
    watcher.main()
    before = _snapshot(tmp_path / "data" / "leaderboard.json")

    watcher.with_leaderboard([{"login": "someone-else", "score": 120.0}, {"login": "zsxh1990", "score": 94.83}])
    watcher.main()

    assert _snapshot(tmp_path / "data" / "leaderboard.json") != before, "a new #1 must be recorded"
    assert watcher.issued, "a new #1 must still open the notification issue"
