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
