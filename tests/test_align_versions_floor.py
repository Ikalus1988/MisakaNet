#!/usr/bin/env python3
"""The npm bundle line has no floor — and that is a decision, so it is tested as one.

`align_versions.py` bounds `package.json` from **above** (R2: it may lag the release line but never run
ahead of it). On 2026-09-29 the owner decided there should be no floor, and the reasoning is the thing
worth pinning: a version number moves backwards both when someone fat-fingers an edit or publishes an
older artifact, *and* when a published version turns out to be broken and gets rolled back on purpose.
The two are indistinguishable from the number, so a hard gate would block the legitimate one exactly when
it is needed. The check therefore reports and never fails.

These tests drive the real function against scratch repositories, because a rule that reads the real
repository has no demonstrable failure mode.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import align_versions as av  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _scratch(tmp_path: Path, versions: list[str]) -> Path:
    """A repository whose `package.json` history walks through `versions` (oldest first)."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    for version in versions:
        (repo / "package.json").write_text(json.dumps({"name": "x", "version": version}), encoding="utf-8")
        _git(repo, "add", "package.json")
        # `--allow-empty`: the "unchanged" case commits the same bytes twice on purpose.
        _git(repo, "commit", "-q", "--allow-empty", "-m", f"version {version}")
    return repo


def test_a_backwards_move_is_reported(tmp_path):
    repo = _scratch(tmp_path, ["2.37.0", "2.39.0", "2.38.0"])
    status, detail = av.npm_bundle_floor(repo)
    assert status == "backwards", (status, detail)
    assert detail == "2.39.0 → 2.38.0", detail


def test_a_forward_move_and_an_unchanged_value_are_not_reported(tmp_path):
    forward = _scratch(tmp_path / "forward", ["2.38.0", "2.39.0"])
    assert av.npm_bundle_floor(forward)[0] == "ok", av.npm_bundle_floor(forward)
    # Two commits that both carry the same version: the previous *different* value is the one before.
    unchanged = _scratch(tmp_path / "same", ["2.38.0", "2.38.0"])
    assert av.npm_bundle_floor(unchanged)[0] == "ok", av.npm_bundle_floor(unchanged)


def test_no_history_says_unverified_rather_than_ok(tmp_path):
    """A check that cannot run must not report success — that is the shape this repository keeps removing."""
    empty = tmp_path / "plain"
    empty.mkdir()
    (empty / "package.json").write_text(json.dumps({"version": "2.38.0"}), encoding="utf-8")
    status, detail = av.npm_bundle_floor(empty)
    assert status == "unverified", (status, detail)
    assert "git" in detail.lower() or "history" in detail.lower(), detail

    missing = tmp_path / "missing"
    missing.mkdir()
    assert av.npm_bundle_floor(missing) == ("unverified", "package.json is missing or unreadable")


def test_the_advisory_never_changes_the_exit_code(monkeypatch):
    """The decision, mechanised: `--check` still succeeds while a backwards move is reported.

    The repository the check runs against is the real one, so every other invariant holds — which is what
    makes this a test of the advisory rather than of the repository's current version line.
    """
    assert av.check() == 0, "the real repository must satisfy every policy invariant for this test to mean anything"
    monkeypatch.setattr(av, "npm_bundle_floor", lambda *a, **k: ("backwards", "2.39.0 → 2.38.0"))
    assert av.check() == 0, (
        "a backwards npm version is an advisory the owner chose not to gate on; if it now fails, the "
        "decision in scripts/align_versions.py's docstring and the code have diverged"
    )
