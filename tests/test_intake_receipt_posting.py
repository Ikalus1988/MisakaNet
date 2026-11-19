#!/usr/bin/env python3
"""Posting and closing the receipt — the mechanism, not the prose (#1528's remaining half).

The prose was already tested (`test_intake_receipt*.py`). What had never been tested is the act: on
2026-09-21 four intakes sat open for days after their lessons merged, and a sweep on 2026-11-19 found
64 more in exactly that state. A receipt that is composed but never posted is a receipt the reporter
never receives, and the queue reads "still owed" for work that is done.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import intake_receipt  # noqa: E402


class FakeGh:
    """Records the writes a real run would make, in order."""

    def __init__(self, fail_on: str | None = None):
        self.calls: list[tuple[list[str], str | None]] = []
        self.fail_on = fail_on

    def __call__(self, args, body=None):
        self.calls.append((list(args), body))
        if self.fail_on and self.fail_on in " ".join(args):
            return False, "boom"
        return True, "ok"


def test_a_receipt_that_posts_alsocloses_the_intake():
    gh = FakeGh()
    ok, detail = intake_receipt.post_receipt(1234, "receipt text", opener=gh)
    assert ok, detail
    verbs = [(c[0][1], c[0][2]) for c in gh.calls]
    assert verbs == [("comment", "1234"), ("close", "1234")], verbs
    assert gh.calls[0][1] == "receipt text", "the body goes in, not a temp path"
    assert gh.calls[1][0][-2:] == ["--reason", "completed"]


def test_a_failed_comment_does_not_close():
    """Closing without a receipt is worse than neither: the reporter loses the thread and the record."""
    gh = FakeGh(fail_on="comment")
    ok, detail = intake_receipt.post_receipt(1234, "receipt text", opener=gh)
    assert not ok and "comment failed" in detail, detail
    assert [c[0][1] for c in gh.calls] == ["comment"], gh.calls


def test_a_failed_close_says_the_comment_landed():
    gh = FakeGh(fail_on="close")
    ok, detail = intake_receipt.post_receipt(1234, "receipt text", opener=gh)
    assert not ok and "close failed" in detail, detail


def test_the_sweep_finds_an_open_intake_whose_lesson_exists():
    lesson = intake_receipt.lessons_citing(1130)
    assert lesson, "the case corpus pins #1130 as converted; if this fails the shape map moved"
    assert intake_receipt.converted_but_open(open_issues=[1130, 999999]) == [1130]
