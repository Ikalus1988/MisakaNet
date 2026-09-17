#!/usr/bin/env python3
"""Gate the bounty fixture harness itself (issue #1819).

`scripts/bounty_tasks.py` is what a stranger will run to produce the evidence this repo is asking
for, so it gets the same treatment as any other gate: the two directions are pinned in CI.

* order matters — `verify` must show each scorer going red on the untouched fixture *and* green on
  the minimal honest fix. A scorer that only ever says "solved" would let any submission through,
  and one that only ever says "not solved" would make the bounty unanswerable.
* `score` must exit non-zero when the task is unsolved, because the bounty instructions tell people
  to paste that command's output: a passing exit code on a failed run is the kind of thing that
  turns a log into a lie.
* `setup` must refuse to build on top of a non-empty directory — a fixture built into somebody's
  working tree would destroy their files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "bounty_tasks.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_every_scorer_moves_in_both_directions():
    result = _run("verify")
    assert result.returncode == 0, f"the fixture self-check failed:\n{result.stdout}\n{result.stderr}"
    assert "untouched=False" in result.stdout, result.stdout
    assert "solved=True" in result.stdout, result.stdout


def test_score_exits_non_zero_on_an_unsolved_task(tmp_path: Path):
    root = tmp_path / "task"
    setup = _run("setup", "--task", "encoding", "--dir", str(root))
    assert setup.returncode == 0, setup.stderr

    unsolved = _run("score", "--task", "encoding", "--dir", str(root))
    assert unsolved.returncode == 1, "an unsolved task must not exit 0 — the log is the evidence"
    assert "NOT SOLVED" in unsolved.stdout
    assert "UnicodeDecodeError" in unsolved.stdout, "the log must carry the real error text"


def test_score_logs_the_raw_evidence_a_reviewer_needs(tmp_path: Path):
    root = tmp_path / "task"
    _run("setup", "--task", "node-crypto", "--dir", str(root))
    solved = _run("score", "--task", "node-crypto", "--dir", str(root))
    assert "NOT SOLVED" in solved.stdout
    # The command it ran, and the fact that it removed the global — not just a verdict.
    assert "--import" in solved.stdout and "node18-preload.mjs" in solved.stdout
    assert "crypto is not defined" in solved.stdout, solved.stdout


def test_setup_refuses_to_write_into_a_non_empty_directory(tmp_path: Path):
    root = tmp_path / "mine"
    root.mkdir()
    (root / "important.txt").write_text("do not lose me\n", encoding="utf-8")
    result = _run("setup", "--task", "dco", "--dir", str(root))
    assert result.returncode == 2, result.stdout + result.stderr
    assert (root / "important.txt").read_text(encoding="utf-8") == "do not lose me\n"
    assert not (root / ".git").exists(), "nothing may be built on top of the user's directory"
