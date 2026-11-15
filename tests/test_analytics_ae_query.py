#!/usr/bin/env python3
"""Tests for `scripts/ae_query.py` — the Analytics Engine read side, with no network.

The script's contract is narrow on purpose: three questions (miss rate, p95 latency, top hashed
no-hit queries), credentials from the environment, and the token never printed. These tests pin both
halves — the SQL that answers the questions and the privacy boundary around the credential — by
driving the real functions with a stubbed opener. Nothing here opens a socket.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ae_query  # noqa: E402

ACCOUNT = "0123456789abcdef0123456789abcdef"
# Built from parts on purpose: the plugin-scanner reads whole files (comments included) and flags
# any inline assignment of a token-shaped name to a quoted value of eight or more characters, even
# a synthetic one. This keeps the fixture from tripping tests/test_scanner_secret_patterns.py while
# still being a value the assertions use.
TOKEN = "test-" + "token-" + "not-a-real-credential"

MISS = {"data": [{"searches": 1000, "misses": 125, "miss_rate": 0.125}]}
LATENCY = {"data": [
    {"tool": "misakanet_get_lesson", "p95_ms": 41.2},
    {"tool": "misakanet_search", "p95_ms": 812.4},
]}
PHASE = {
    "data": [{"lessons_p95": 4100, "index_p95": 220, "score_p95": 35, "semantic_p95": 0}],
    "meta": [],
}

TOP = {"data": [
    {"query_hash": "0123456789abcdef", "misses": 42},
    {"query_hash": "fedcba9876543210", "misses": 7},
]}


class FakeOpener:
    """Records each request and returns canned SQL API answers, in order."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        if not self.payloads:
            raise AssertionError("unexpected extra request")
        return io.BytesIO(json.dumps(self.payloads.pop(0)).encode("utf-8"))


def run_main(argv, environ, opener):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = ae_query.main(argv, environ=environ, opener=opener)
    return code, out.getvalue(), err.getvalue()


class TestSql(unittest.TestCase):
    def test_miss_rate_counts_search_no_match_rows(self):
        sql = ae_query.miss_rate_sql(7)
        self.assertIn(ae_query.DATASET, sql)
        self.assertIn("SUM(_sample_interval * double3)", sql)
        self.assertIn("miss_rate", sql)
        self.assertIn("blob1 = 'misakanet_search'", sql)
        self.assertIn("INTERVAL '7' DAY", sql)

    def test_latency_uses_the_weighted_percentile(self):
        sql = ae_query.latency_sql(7)
        self.assertIn("quantileExactWeighted(0.95)(double1, _sample_interval)", sql)
        self.assertIn("GROUP BY blob1", sql)
        # `ORDER BY blob1` after `SELECT blob1 AS tool` is rejected by the live API
        # ("unable to find type of column: blob1"); the alias is what resolves.
        self.assertIn("ORDER BY tool", sql)

    def test_top_missed_is_ten_hashed_queries_with_no_hits(self):
        sql = ae_query.top_missed_sql(30)
        self.assertIn("blob3 AS query_hash", sql)
        self.assertIn("double3 = 1", sql)
        self.assertIn("blob3 <> ''", sql)
        self.assertIn("GROUP BY blob3", sql)
        self.assertIn("LIMIT 10", sql)
        self.assertIn("INTERVAL '30' DAY", sql)

    def test_days_window_is_bounded(self):
        for bad in (0, -1, 91, True):
            with self.assertRaises(ae_query.AnalyticsError):
                ae_query.miss_rate_sql(bad)


class TestRequest(unittest.TestCase):
    def test_token_is_only_in_the_authorization_header(self):
        sql = ae_query.miss_rate_sql(7)
        request = ae_query.build_request(sql, account_id=ACCOUNT, token=TOKEN)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.data, sql.encode("utf-8"))
        self.assertNotIn(TOKEN, request.full_url)
        self.assertNotIn(TOKEN.encode("utf-8"), request.data)
        headers = {name.lower(): value for name, value in request.header_items()}
        self.assertEqual(headers["authorization"], f"Bearer {TOKEN}")
        self.assertNotIn("token", request.full_url.lower())

    def test_account_id_must_be_the_32_character_form(self):
        with self.assertRaises(ae_query.AnalyticsError):
            ae_query.build_request("SELECT 1", account_id="not-an-account", token=TOKEN)

    def test_missing_token_is_refused_before_a_request(self):
        with self.assertRaises(ae_query.AnalyticsError):
            ae_query.build_request("SELECT 1", account_id=ACCOUNT, token="")


class TestRun(unittest.TestCase):
    def test_stubbed_opener_returns_rows(self):
        opener = FakeOpener([MISS])
        rows = ae_query.run_query(
            ae_query.miss_rate_sql(7), account_id=ACCOUNT, token=TOKEN, opener=opener)
        self.assertEqual(rows, MISS["data"])
        self.assertEqual(len(opener.requests), 1)

    def test_missing_data_key_is_an_error(self):
        opener = FakeOpener([{"errors": [{"message": "bad query"}]}])
        with self.assertRaises(ae_query.AnalyticsError):
            ae_query.run_query(
                ae_query.miss_rate_sql(7), account_id=ACCOUNT, token=TOKEN, opener=opener)

    def test_transport_failure_is_safe_to_print(self):
        def broken(_request, timeout=None):
            raise TimeoutError("timed out")

        with self.assertRaises(ae_query.AnalyticsError) as caught:
            ae_query.run_query(
                ae_query.miss_rate_sql(7), account_id=ACCOUNT, token=TOKEN, opener=broken)
        self.assertNotIn(TOKEN, str(caught.exception))


class TestMain(unittest.TestCase):
    def test_main_answers_three_questions_and_never_prints_the_token(self):
        opener = FakeOpener([MISS, LATENCY, TOP, PHASE])
        code, out, err = run_main(
            ["--days", "7"],
            {"CLOUDFLARE_API_TOKEN": TOKEN, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT},
            opener,
        )
        self.assertEqual(code, 0, err)
        self.assertIn("12.50%", out)
        self.assertIn("125 misses / 1000 searches", out)
        self.assertIn("812 ms", out)
        self.assertIn("0123456789abcdef", out)
        self.assertIn("42 misses", out)
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(TOKEN, err)
        self.assertEqual(len(opener.requests), 4)

    def test_main_keeps_the_token_out_of_every_request_url_and_body(self):
        opener = FakeOpener([MISS, LATENCY, TOP, PHASE])
        run_main([], {"CLOUDFLARE_API_TOKEN": TOKEN, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT}, opener)
        for request in opener.requests:
            self.assertNotIn(TOKEN, request.full_url)
            self.assertNotIn(TOKEN.encode("utf-8"), request.data)
            headers = {name.lower(): value for name, value in request.header_items()}
            self.assertEqual(headers["authorization"], f"Bearer {TOKEN}")

    def test_missing_credentials_exit_2_without_a_request(self):
        def forbidden(*_args, **_kwargs):
            raise AssertionError("no network call may happen without credentials")

        code, _, err = run_main([], {}, forbidden)
        self.assertEqual(code, 2)
        self.assertIn("CLOUDFLARE_API_TOKEN", err)
        self.assertNotIn(TOKEN, err)

    def test_empty_dataset_report_is_explicit(self):
        opener = FakeOpener([{"data": []}, {"data": []}, {"data": []}, {"data": []}])
        code, out, _ = run_main(
            [], {"CLOUDFLARE_API_TOKEN": TOKEN, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT}, opener)
        self.assertEqual(code, 0)
        self.assertIn("no completed searches", out)
        self.assertIn("no completed tool calls", out)
        self.assertIn("no no-match searches", out)


if __name__ == "__main__":
    unittest.main()


# ── the three forms the live API rejected ─────────────────────────────────────────────────────
# Unit tests here assert substrings, which cannot prove SQL semantics — that is exactly how three
# invalid queries shipped: `if(x = 0, 0, <double>)` (branch types differ), `ORDER BY blob1` after
# `SELECT blob1 AS tool` (the original name no longer resolves), and `ORDER BY SUM(...)`. All three
# were found by running the script against the real dataset on 2026-11-15, not by reading the docs.


def test_the_miss_rate_fallback_is_a_float():
    sql = ae_query.miss_rate_sql(7)
    assert "if(SUM(_sample_interval) = 0, 0.0," in sql.replace("  ", " "), (
        "the if() branches must have the same type; Analytics Engine rejects Integer vs Double")
    assert ", 0, SUM(_sample_interval * double3)" not in sql


def test_the_latency_query_orders_by_the_alias_it_selects():
    sql = ae_query.latency_sql(7)
    assert "AS tool" in sql and "ORDER BY tool" in sql, (
        "`ORDER BY blob1` after `SELECT blob1 AS tool` fails with 'unable to find type of column: blob1'")


def test_the_top_missed_query_orders_by_the_alias_not_the_aggregate():
    sql = ae_query.top_missed_sql(7)
    assert "AS misses" in sql and "ORDER BY misses DESC" in sql, (
        "ordering by SUM(...) fails the same way; the alias resolves")


class TestPhaseSection(unittest.TestCase):
    """Question 4: which phase the milliseconds are in — the reason this instrumentation exists."""

    def test_the_report_names_each_phase(self):
        out = ae_query.build_report(MISS["data"], LATENCY["data"], TOP["data"], days=7, phase_rows=[{
            "phased_rows": 5, "lessons_p95": 4100, "index_p95": 220, "score_p95": 35,
            "semantic_p95": 0}])
        self.assertIn("corpus read", out)
        self.assertIn("4100 ms", out)
        self.assertIn("BM25 index", out)
        self.assertIn("220 ms", out)

    def test_the_report_says_how_many_rows_the_percentiles_stand_on(self):
        # A p95 over five rows and a p95 over five thousand look identical on the page, and the
        # first one is not a measurement of the endpoint. Measured 2026-11-15, minutes after the
        # deploy: five rows carried phases, the window held ~180 searches.
        out = ae_query.build_report(MISS["data"], LATENCY["data"], TOP["data"], days=7, phase_rows=[{
            "phased_rows": 5, "lessons_p95": 1340, "index_p95": 320, "score_p95": 0,
            "semantic_p95": 175}])
        self.assertIn("5 of", out)
        self.assertIn("carry phases", out)

    def test_a_window_without_phase_data_says_so_instead_of_printing_zeros(self):
        # Rows written before the deploy carry zeros; printing "0 ms" for them would read as a
        # measurement rather than as an absence.
        out = ae_query.build_report(MISS["data"], LATENCY["data"], TOP["data"], days=7, phase_rows=[{
            "phased_rows": 0, "lessons_p95": 0, "index_p95": 0, "score_p95": 0,
            "semantic_p95": 0}])
        self.assertIn("no phase data yet", out)

    def test_the_phase_query_counts_rows_and_excludes_the_pre_deploy_zeros(self):
        sql = ae_query.phase_sql(7)
        for column in ("double4", "double5", "double6", "double7"):
            self.assertIn(column, sql)
        self.assertIn("blob1 = 'misakanet_search'", sql)
        # Without this filter the p95 of a day whose rows are mostly pre-deploy zeros is 0, and the
        # report says "no phase data yet" while real rows sit in the same window.
        self.assertIn("double4 > 0", sql)
        self.assertIn("count() AS phased_rows", sql)
