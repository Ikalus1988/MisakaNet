"""`scripts/d1_cost_report.py`: rows *per call* is the number, and "new" needs a comparison window.

The bug this exists for was invisible for a month: one statement read 19,561,754,663 rows at 10.4M
rows per call, with correct answers and ordinary latency. A total would not have distinguished it from
a busy query — five thousand cheap calls and one catastrophic one land in the same place — so the
classification (rows/call) is the thing worth pinning.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import d1_cost_report as report  # noqa: E402


def entry(query: str, rows: int, calls: int) -> dict:
    return {"query": query, "rows_read": rows, "rows_written": 0, "calls": calls}


def test_a_bad_shape_is_separated_from_a_busy_query():
    entries = [
        entry("SELECT … JOIN lesson_authors la ON …", 19_561_754_663, 1_873),   # 10.4M/call
        entry("SELECT … FROM counters WHERE …", 645_704, 334_999),              # 2/call
    ]
    marked = report.classify(entries, 100_000)
    assert [m["verdict"] for m in marked] == ["shape", "busy"]
    assert marked[0]["rows_per_call"] > 10_000_000


def test_the_threshold_is_inclusive_of_the_boundary():
    marked = report.classify([entry("q", 100_001, 1), entry("q2", 100_000, 1)], 100_000)
    assert marked[0]["verdict"] == "shape"
    assert marked[1]["verdict"] == "busy"


def test_new_means_absent_from_the_previous_window():
    previous = report.classify([entry("chronic", 5_000_000, 10)], 100_000)
    current = report.classify([entry("chronic", 5_000_000, 10), entry("fresh", 900_000, 2)], 100_000)
    fresh = report.new_since(current, previous)
    assert [row["query"] for row in fresh] == ["fresh"]


def test_a_zero_call_entry_does_not_divide_by_zero():
    assert report.rows_per_call(1234, 0) == 0.0


def test_queries_are_normalised_to_one_line():
    text = "SELECT a,\n       b\n  FROM t WHERE x = 1"
    assert report.normalise(text) == "SELECT a, b FROM t WHERE x = 1"
    assert len(report.normalise("x" * 500)) == 200


def test_the_account_id_is_read_only_from_a_hex_id():
    assert report.account_id_from("") == ""
    assert report.account_id_from("not-an-id") == ""
    assert report.account_id_from("", "6b92325b505f2b76aec49e9fe4195d31") == \
        "6b92325b505f2b76aec49e9fe4195d31"


def test_the_report_names_the_offender_and_its_shape():
    entries = report.classify([entry("SELECT … JOIN …", 298_727_040, 20)], 100_000)
    markdown = report.render_markdown({
        "window": {"from": "2026-11-24", "to": "2026-11-24", "days": 1},
        "threshold": 100_000, "entries": entries, "new": [], "totals": [],
    })
    assert "14,936,352" in markdown, markdown
    assert "SELECT … JOIN …" in markdown


def test_a_clean_day_says_so_instead_of_printing_an_empty_table():
    markdown = report.render_markdown({
        "window": {"from": "2026-11-25", "to": "2026-11-25", "days": 1},
        "threshold": 100_000, "entries": [], "new": [], "totals": [],
    })
    assert "No statement is over the threshold" in markdown


def test_no_token_is_exit_2_not_exit_0():
    """A report that cannot read must not look like a quiet day."""
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "d1_cost_report.py")],
                            capture_output=True, text=True, cwd=REPO,
                            env={"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"})
    assert result.returncode == 2, result.stdout + result.stderr
    assert "CF_ANALYTICS_TOKEN" in (result.stdout + result.stderr)


def test_the_workflow_wires_the_token_and_says_why_wrangler_is_absent():
    workflow = (REPO / ".github" / "workflows" / "d1-cost.yml").read_text(encoding="utf-8")
    assert "CF_ANALYTICS_TOKEN" in workflow, "the job needs the analytics credential"
    assert "Account Analytics: Read" in workflow, "and it should say which permission, not just 'a token'"
    assert "not" in workflow and "deploy-capable" in workflow, (
        "the file should keep the reason it does not use a deploy credential")
    # The report is one issue: enumerated failure paths must not create a new one per run.
    assert "gh issue list" in workflow and "gh issue reopen" in workflow


def test_the_issue_writer_uses_the_token_that_can_actually_write_issues():
    """`SHELDON_PAT` cannot comment on an issue — and that failure is silent in the green case.

    Measured 2026-11-26: `d1-cost.yml` failed on 11-25 and 11-26 with

        GraphQL: Resource not accessible by personal access token (addComment)

    while the *read* step succeeded both times. So the watch measured a problem and could not report
    it — the exact "goes quiet" failure this workflow exists to prevent, arriving through the
    credential instead of the query. `update-lessons.yml` lost 313 receipts over three green days the
    same way (#1528).

    The assertion is on the whole file rather than the one `env:` line, because a second
    `GH_TOKEN: ${{ secrets.SHELDON_PAT }}` anywhere in the job reintroduces it.
    """
    workflow = (REPO / ".github" / "workflows" / "d1-cost.yml").read_text(encoding="utf-8")
    wired = [line.strip() for line in workflow.splitlines()
             if line.strip().startswith(("GH_TOKEN:", "GH_TOKEN :"))]
    assert wired, "the job declares no GH_TOKEN at all"
    assert wired == ["GH_TOKEN: ${{ github.token }}"], (
        f"d1-cost.yml wires {wired} — the PAT cannot comment on issues (two-day outage, "
        "11-25 and 11-26); `github.token` plus the job's `issues: write` can")
    assert "issues: write" in workflow, "and it still needs the permission that makes github.token enough"
