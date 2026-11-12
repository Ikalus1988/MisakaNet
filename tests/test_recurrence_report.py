#!/usr/bin/env python3
"""The recurrence report's arithmetic and its two failure shapes: a stale table and an empty one."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import recurrence_report as rr  # noqa: E402


def test_panels_compute_the_two_rates_from_one_row_each():
    result = rr.panels(
        {"distinct_queries": 828, "repeated_pairs": 55, "newest": "2026-11-11T06:04:00Z"},
        {"buckets_total": 1571, "repeated_buckets": 78, "bucket_days": 1808, "newest": "2026-11-11"},
    )
    assert result["answered_repeats"]["rate"] == 55 / 828
    assert result["unanswered_repeats"]["rate"] == 78 / 1571
    assert result["unanswered_repeats"]["bucket_days"] == 1808


def test_a_zero_denominator_is_no_rate_not_zero_percent():
    result = rr.panels({"distinct_queries": 0, "repeated_pairs": 0}, {"buckets_total": 0, "repeated_buckets": 0})
    assert result["answered_repeats"]["rate"] is None
    assert "—" in "\n".join(rr.render(result, 7))


def test_a_stale_table_says_so_instead_of_reporting_a_normal_rate():
    old = (rr.date.today().replace(year=rr.date.today().year - 1)).isoformat()
    result = rr.panels({"distinct_queries": 100, "repeated_pairs": 5, "newest": old}, None)
    out = "\n".join(rr.render(result, 7))
    assert "days old" in out
    assert "not today" in out


def test_wrangler_envelopes_and_bare_arrays_both_parse():
    rows = [{"distinct_queries": 1, "repeated_pairs": 0}]
    assert rr.result_rows('[{"results": ' + str(rows).replace("'", '"') + ', "success": true}]') == rows
    assert rr.result_rows(str(rows).replace("'", '"')) == rows


def test_both_panels_read_the_telemetry_database(monkeypatch):
    """B used to read the main database, whose `counters` stopped during 2026-10-27 (#4696)."""
    seen = []

    def fake_wrangler_json(database, sql):
        seen.append(database)
        return [{}]

    monkeypatch.setattr(rr, "wrangler_json", fake_wrangler_json)
    rr.main([])
    assert seen == ["misakanet-ops", "misakanet-ops"]
