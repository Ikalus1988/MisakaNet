#!/usr/bin/env python3
"""The pipeline panel: the six numbers the labels cannot produce, and the read that fails loudly.

The panel exists because the daily heartbeat could say who called and what they asked, and nothing
about whether the backlog moved. Its two failure modes are the ones every counter in this repository
has had to be written against:

* **a failed read rendered as a zero.** `collect()` returns the reason, and the panel prints
  "could not be read" instead of four zeros that look like a quiet week.
* **a number that means something else.** "converted" is provenance — a lesson citing the issue, by
  `intake_receipt`'s shapes — not a keyword match, and "answered" is the label, not a claim that the
  answer helped. Both sentences are in the panel, and a test fails if the caveat is removed.
"""
from __future__ import annotations

import http.client
import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import pipeline_status as ps  # noqa: E402

TODAY = date(2026, 10, 30)
DAYS_AGO = lambda n: (TODAY - timedelta(days=n)).isoformat() + "T00:00:00Z"  # noqa: E731


def issue(number, title, *, state="open", created_days_ago=0, labels=(), comments=0,
          closed_days_ago=None):
    return {
        "number": number,
        "title": title,
        "state": state,
        "labels": [{"name": name} for name in labels],
        "comments": comments,
        "created_at": DAYS_AGO(created_days_ago),
        "closed_at": DAYS_AGO(closed_days_ago) if closed_days_ago is not None else None,
    }


def lesson(path, created: date, issues):
    return {"path": path, "created": created, "issues": set(issues)}


def test_every_kind_is_counted_and_converted_comes_from_provenance():
    issues = [
        # outside the 7-day window, still open: it owns the oldest-age and never-commented cells
        issue(1, "[Question] open ten days, never commented", created_days_ago=10),
        # outside the window too, but it carries the `answered` label (an all-time count)
        issue(2, "[Question] answered and closed", state="closed", created_days_ago=8,
              closed_days_ago=3, labels=["answered"]),
        # inside the window
        issue(3, "[Intake] rejected", created_days_ago=9, labels=["auto-rejected"]),
        issue(4, "[Intake] rejected then salvaged", state="closed", created_days_ago=5,
              closed_days_ago=2, labels=["auto-rejected"]),
        issue(5, "[Lesson] submitted", created_days_ago=4),
        issue(6, "our own issue", created_days_ago=1, comments=2),
        issue(7, "[Question] fresh", created_days_ago=2, comments=1),
    ]
    lessons = [lesson("lessons/core/a.md", TODAY, [4])]
    summary = ps.summarize(issues, lessons, TODAY)

    q, i, s, own = (summary["rows"][k] for k in ("question", "intake", "lesson-submission", "own"))
    assert q["open"] == 2 and q["oldest_open_days"] == 10
    assert q["never_commented"] == 1, "only #1 has no comments"
    assert q["created"] == 1, "only #7 was created inside the 7-day window"
    assert i["created"] == 1 and i["converted"] == 1, i  # #4 is inside the window
    assert i["open"] == 1 and i["auto_rejected_open"] == 1
    assert i["auto_rejected"] == 2 and i["auto_rejected_salvaged"] == 1
    assert s["open"] == 1 and s["created"] == 1
    assert own["open"] == 1 and own["never_commented"] == 0
    assert summary["answered_total"] == 1 and summary["questions_total"] == 3


def test_a_pull_request_is_not_an_issue():
    summary = ps.summarize([{**issue(9, "[Question] a PR", created_days_ago=1),
                             "pull_request": {"url": "x"}}], [], TODAY)
    assert summary["rows"]["question"]["created"] == 0


def test_latency_is_median_and_p90_of_converted_lessons_only():
    # Ten issues opened 20 days ago, each converted d days later (d = 1..10, all inside the 30-day
    # latency window). Median of 1..10 is the 6th value; p90 is the 10th.
    issues = [issue(n, f"[Intake] #{n}", state="closed", created_days_ago=20)
              for n in range(1, 11)]
    lessons = [lesson(f"lessons/core/{n}.md", TODAY - timedelta(days=20 - d), [n])
               for n, d in enumerate(range(1, 11), start=1)]
    summary = ps.summarize(issues, lessons, TODAY)
    latency = summary["latency"]
    assert latency["n"] == 10
    assert latency["median"] == 6, latency
    assert latency["p90"] == 10, latency


def test_a_lesson_older_than_the_window_does_not_count_as_latency():
    issues = [issue(1, "[Intake] old", state="closed", created_days_ago=90)]
    lessons = [lesson("lessons/core/old.md", TODAY - timedelta(days=60), [1])]
    assert ps.summarize(issues, lessons, TODAY)["latency"]["n"] == 0


def test_the_panel_prints_the_rows_and_the_caveat():
    issues = [issue(1, "[Question] q", created_days_ago=3),
              issue(2, "[Intake] i", created_days_ago=2),
              issue(3, "[Lesson] l", created_days_ago=1)]
    text = "\n".join(ps.render_lines(ps.summarize(issues, [], TODAY)))
    assert "## 4 · The pipeline" in text
    for label in ("`[Question]`", "`[Intake]`", "`[Lesson]`", "our own issues"):
        assert label in text, label
    assert "reads issue state, not answers" in text
    assert "provenance, not a keyword" in text


def test_an_unreadable_source_is_a_reason_not_a_zero():
    summary, reason = ps.collect(token=None, today=TODAY)
    assert summary is None
    assert "token" in reason.lower(), reason


def test_the_composer_renders_the_failure_instead_of_four_zeros():
    from scripts.heartbeat_report import render_digest

    text = render_digest(day="2026-10-29", counters=[], analytics=None, funnel=None,
                         pipeline=None, pipeline_error="URLError: host unreachable")
    assert "## 4 · The pipeline" in text
    assert "Could not be read for this run" in text
    assert "URLError: host unreachable" in text
    assert "failed read, not an empty backlog" in text


def test_the_composer_renders_the_panel_when_it_has_data():
    from scripts.heartbeat_report import render_digest

    issues = [issue(1, "[Question] q", created_days_ago=3)]
    summary = ps.summarize(issues, [], TODAY)
    text = render_digest(day="2026-10-29", counters=[], analytics=None, funnel=None,
                         pipeline=summary)
    assert "| `[Question]` | 1 |" in text
    assert "reads issue state, not answers" in text


def test_lessons_dir_parsing_reads_the_repo_shapes(tmp_path):
    """`issue:` / `intake-N` / `#N` are the citation shapes `intake_receipt` already owns."""
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "a.md").write_text(
        "---\ncreated: '2026-10-20'\nprovenance:\n  issue: '#1234'\n"
        "  source: 'MCP intake intake-5678, contributor-reported'\n---\n\nbody\n",
        encoding="utf-8")
    (tmp_path / "core" / "b.md").write_text(
        "---\ncreated: '2026-10-21'\ntitle: mentions issue 9999 in prose\n---\n\nbody\n",
        encoding="utf-8")
    records = ps.lesson_records(tmp_path)
    cited = {n for r in records for n in r["issues"]}
    assert cited == {1234, 5678}, cited
    assert "9999" not in str(cited), "a number in prose is not a citation"


# ── the search index line (2026-10-31) ──────────────────────────────────────
#
# 47 lessons were in D1, the index said 705, four title-verbatim queries returned `no_match`, and the
# answer took decoding a 1 MB gzip row out of `kv_store` by hand — while `/api/search-index` already
# knew (`behindBy: 0`). The panel carries that number now, so "the index is behind" is a line in a
# comment instead of an investigation.

def test_the_index_line_says_how_far_behind_it_is():
    index = {"available": True, "docCount": 705, "behindBy": 0, "stale": False,
             "builtAt": "2026-10-31T01:46:04.737Z"}
    line = ps.index_line(index, "", 705)
    assert "**705** docs" in line
    assert "corpus **705**" in line
    assert "behind by" not in line
    assert "stale" not in line
    assert "2026-10-31 01:46:04Z" in line


def test_the_index_line_calls_out_a_behind_index():
    index = {"available": True, "docCount": 658, "behindBy": 47, "stale": True,
             "builtAt": "2026-10-30T02:00:00.000Z"}
    line = ps.index_line(index, "", 705)
    assert "**behind by 47**" in line
    assert "**stale**" in line


def test_an_unreadable_index_is_not_a_healthy_one():
    line = ps.index_line(None, "URLError: host unreachable", 705)
    assert "could not be read" in line
    assert "URLError: host unreachable" in line
    assert "not a claim that it is healthy" in line


def test_the_panel_renders_the_index_line_when_the_summary_carries_one():
    issues = [issue(1, "[Question] q", created_days_ago=2)]
    summary = ps.summarize(issues, [], TODAY)
    summary["lessons_on_disk"] = 705
    summary["index"] = {"docCount": 705, "behindBy": 0, "stale": False,
                        "builtAt": "2026-10-31T01:46:04Z"}
    text = "\n".join(ps.render_lines(summary))
    assert "**search index**" in text
    assert "**705** docs" in text


def test_a_summary_without_index_keys_does_not_invent_a_line():
    issues = [issue(1, "[Question] q", created_days_ago=2)]
    text = "\n".join(ps.render_lines(ps.summarize(issues, [], TODAY)))
    assert "search index" not in text


def test_a_dropped_read_is_retried_once_before_the_panel_loses_its_issue_table(monkeypatch):
    """Measured 2026-10-31 on this host: a 346 KB read against a 459 KB body — `IncompleteRead`."""
    calls = {"n": 0}

    def flaky(_token, _slug, _page_size, _max_pages):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http.client.IncompleteRead(b"x" * 10, 100)
        return [issue(1, "[Question] q")]

    monkeypatch.setattr(ps, "_fetch_issues_once", flaky)
    got = ps.fetch_issues("t")
    assert calls["n"] == 2 and len(got) == 1


def test_a_transport_error_the_caller_can_read(monkeypatch):
    import http.client as hc

    def always(_token, _slug, _page_size, _max_pages):
        raise hc.IncompleteRead(b"x", 10)

    monkeypatch.setattr(ps, "_fetch_issues_once", always)
    summary, reason = ps.collect(token="t", today=TODAY)
    assert summary is None
    assert "IncompleteRead" in reason


def test_the_corpus_count_is_the_published_row_count_not_the_file_count(tmp_path):
    """Counting `lessons/**/*.md` overcounts translations (743 files vs 705 rows, 2026-10-31)."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "lessons.json").write_text(json.dumps([{"id": "a"}, {"id": "b"}]),
                                                   encoding="utf-8")
    lessons = tmp_path / "lessons"
    (lessons / "core").mkdir(parents=True)
    for name in ("a", "b", "a.pt-br"):
        (lessons / "core" / f"{name}.md").write_text("---\nid: x\n---\n", encoding="utf-8")
    assert ps.corpus_size(lessons) == 2


def test_without_a_published_index_the_count_falls_back_to_the_parseable_lessons(tmp_path):
    lessons = tmp_path / "lessons"
    (lessons / "core").mkdir(parents=True)
    (lessons / "core" / "a.md").write_text("---\nissue: '#1'\n---\n", encoding="utf-8")
    assert ps.corpus_size(lessons) is None
