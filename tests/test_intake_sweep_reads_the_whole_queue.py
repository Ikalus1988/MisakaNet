#!/usr/bin/env python3
"""The sweep must read the whole queue, not the first few hundred characters of it.

`_gh` trims its result to 200 characters, because almost every caller only prints it inside an error
message. One caller parses it: `converted_but_open()` asks `gh issue list --limit 1000` and then reads
the answer as a list of numbers. A 200-character prefix of that answer is about **40** issue numbers.

Measured 2026-11-20, on the repository this was written in: 660 open issues, six of them with a lesson
already merged, and the sweep answered "no open intake is already converted" because it could only see
the newest 40. The mechanism that exists to close done-but-open intakes — and that a previous handoff
credited with clearing 64 of them — was silently looking at the top 6% of the queue.

The assertion is the contract, not the number: a list caller passes `keep=None` and gets everything.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "intake_receipt.py"

spec = importlib.util.spec_from_file_location("intake_receipt_module", SCRIPT)
receipt = importlib.util.module_from_spec(spec)
sys.modules["intake_receipt_module"] = receipt
spec.loader.exec_module(receipt)


class _Fake:
    def __init__(self, text: str) -> None:
        self.returncode = 0
        self.stdout = text
        self.stderr = ""


def test_a_list_caller_gets_every_line(monkeypatch):
    numbers = "\n".join(str(n) for n in range(1000, 1660))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Fake(numbers))
    ok, out = receipt._gh(["issue", "list"], keep=None)
    assert ok
    assert len(out.split()) == 660


def test_the_default_stays_a_short_message(monkeypatch):
    """"A failed `gh` prints its stderr into an issue" does not need the whole stderr."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Fake("x" * 5000))
    ok, out = receipt._gh(["issue", "list"])
    assert ok
    assert len(out) == 200


def test_the_sweep_asks_for_the_whole_list(monkeypatch):
    """If this call ever drops `keep=None` again, the sweep silently shrinks to one page of numbers."""
    seen = {}

    def fake(args, body=None, *, keep=200):
        seen["keep"] = keep
        return True, ""

    monkeypatch.setattr(receipt, "_gh", fake)
    assert receipt.converted_but_open(open_issues=None) == []
    assert seen["keep"] is None


def test_the_sweep_reads_each_lesson_once_per_run(tmp_path, monkeypatch):
    """The other half of the same sweep, and the one that took a run down.

    `converted_but_open()` used to ask `lessons_citing(n)` — which reads **every** lesson — once per
    open intake. Measured 2026-11-22 in `update-lessons.yml` run 45039931336: 461 open intakes ×
    1,121 lessons, the step ran 13 minutes without finishing, the job's 20-minute bound cancelled the
    run before the step that lands the regeneration, and 318 receipts that had just been posted were
    never recorded.

    A timing assertion would be flaky. The property that makes it fast is not: one read per lesson,
    whatever the queue size.
    """
    for n in range(5):
        (tmp_path / f"lesson-{n}.md").write_text(
            f'---\ntitle: "L{n}"\nprovenance:\n  issue: "#{1000 + n}"\n---\n', encoding="utf-8")

    monkeypatch.setattr(receipt, "LESSONS_DIR", tmp_path)
    reads = {"n": 0}
    original = Path.read_text

    def counting_read(self, *a, **k):
        reads["n"] += 1
        return original(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", counting_read)
    found = receipt.converted_but_open(open_issues=[1000, 1001, 1002, 1003, 1004, 9999])
    assert found == [1000, 1001, 1002, 1003, 1004]
    assert reads["n"] == 5, (
        f"the sweep read {reads['n']} files for 6 issues over 5 lessons — the corpus is being "
        "re-read per issue again")


def test_a_corpus_from_another_tree_does_not_raise(tmp_path):
    """`corpus=` and `lessons_dir` can disagree; the resolver must not raise over a path prefix."""
    tree = tmp_path / "lessons"
    (tree / "core").mkdir(parents=True)
    lesson = tree / "core" / "x.md"
    lesson.write_text('---\ntitle: "X"\nprovenance:\n  issue: "#4242"\n---\n', encoding="utf-8")

    corpus = receipt._corpus(tree)
    found = receipt.lessons_citing(4242, tmp_path / "somewhere-else", corpus=corpus)
    assert [row["path"] for row in found] == ["core/x.md"]
