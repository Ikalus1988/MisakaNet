#!/usr/bin/env python3
"""`scripts/decision_queue.py` — who is waiting, how long, and who is not.

Why a test for a digest
-----------------------
The digest's only job is to be *right about which issues are stuck*, and every way it can be wrong is
quiet:

* an issue with a comment is not stuck — counting it inflates the queue until nobody reads it;
* an issue labelled `product-design` but not `decision` is still a decision (the first live run found
  the four stuck ones under `decision` and the open product reviews under `product-design`; a filter
  that only knew one label would have reported half the problem);
* the age is what makes the list actionable — "27 days" is a different message from "yesterday".

So the tests pin the selection rule, the sort order (oldest first — the cost of avoidance grows), and
the empty case, which must read as a fact rather than as a failure.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import decision_queue as queue  # noqa: E402

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def issue(number, days_old, labels, comments=0, title="t", assignees=()):
    created = (NOW - timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"number": number, "title": title, "url": f"https://example/{number}",
            "createdAt": created, "comments": [{}] * comments,
            "labels": [{"name": n} for n in labels],
            "assignees": [{"login": a} for a in assignees]}


def test_a_decision_with_no_comment_and_no_age_is_still_waiting():
    rows = queue.select([issue(1, 1, ["decision"])], NOW, min_age_days=0)
    assert [r["number"] for r in rows] == [1]


def test_an_issue_somebody_commented_on_is_not_waiting():
    # A comment is the exit condition: a decision, a deferral or a rejection all look like this.
    rows = queue.select([issue(1, 30, ["decision"], comments=2)], NOW)
    assert rows == []


def test_product_design_counts_as_a_decision():
    rows = queue.select([issue(2, 20, ["product-design"])], NOW)
    assert [r["number"] for r in rows] == [2]


def test_an_issue_that_is_not_decision_shaped_is_ignored_even_if_old_and_silent():
    rows = queue.select([issue(3, 90, ["enhancement", "area:core"])], NOW)
    assert rows == []


def test_the_threshold_is_respected():
    assert queue.select([issue(4, 10, ["decision"])], NOW, min_age_days=14) == []
    assert [r["number"] for r in queue.select([issue(4, 15, ["decision"])], NOW, min_age_days=14)] == [4]


def test_the_oldest_comes_first():
    rows = queue.select([issue(5, 3, ["decision"]), issue(6, 90, ["decision"]),
                         issue(7, 30, ["decision"])], NOW, min_age_days=0)
    assert [r["number"] for r in rows] == [6, 7, 5]
    assert [r["age_days"] for r in rows] == [90, 30, 3]


def test_the_age_is_derived_not_carried():
    rows = queue.select([issue(8, 27, ["decision"])], NOW)
    assert rows[0]["age_days"] == 27


def test_an_assigned_issue_says_who_owns_it():
    text = queue.render(queue.select([issue(9, 20, ["decision"], assignees=["someone"])], NOW),
                        "o/r", NOW, 14)
    assert "assigned: someone" in text


def test_a_pipe_in_a_title_does_not_break_the_table():
    text = queue.render(queue.select([issue(10, 20, ["decision"], title="a | b")], NOW),
                        "o/r", NOW, 14)
    row = [line for line in text.splitlines() if line.startswith("| [#10]")][0]
    assert "\\|" in row, "the pipe in the title is escaped"
    # Four column separators survive: the escaped one is inside a cell, not between cells.
    assert row.replace("\\|", "").count("|") == 5


def test_an_empty_queue_reads_as_a_fact_not_a_failure():
    text = queue.render([], "o/r", NOW, 14)
    assert text.startswith("No decision has been waiting")
    assert "Checked 0 matching issue(s)" in text


def test_the_rendered_digest_names_the_rule_and_the_exit_condition():
    text = queue.render(queue.select([issue(11, 20, ["decision"])], NOW), "o/r", NOW, 14)
    assert "Nothing here is closed automatically" in text
    assert "A row leaves this list when somebody comments" in text
