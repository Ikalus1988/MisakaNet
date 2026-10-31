#!/usr/bin/env python3
"""Tests for the public site health snapshot (Issue #783).

The checker talks to the live site, so every test here injects a fake fetcher —
no network access, deterministic results.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.site_health_check import (  # noqa: E402
    ENDPOINTS,
    FRONTEND_CHECKS,
    check_frontend,
    render_markdown,
    run_checks,
)

HOMEPAGE = """
<html><body>
  <div class="search-box"><input id="searchInput"></div>
  <div id="onboardingModal" class="modal">onboarding</div>
  <a href="journey/">🎮 Journey</a>
</body></html>
"""

# The registration form lives on its own page since #3641, not in a homepage drawer.
REGISTER = """
<html><body>
  <form id="registerForm"><input name="agent_type"><input name="node_name"></form>
</body></html>
"""

BODIES = {
    "/": HOMEPAGE,
    "/register/": REGISTER,
    "/api/health": json.dumps({"status": "ok", "hasKV": True}),
    "/api/counter": json.dumps({"current": 10061, "updated": "2026-08-05"}),
    "/api/lessons": json.dumps([{"id": "a"}, {"id": "b"}]),
    "/api/search-index": json.dumps({"available": True, "docCount": 705, "behindBy": 0,
                                     "stale": False, "builtAt": "2026-10-31T01:46:04.737Z"}),
    "/search/": "<html>search</html>",
    "/journey/": "<html>journey</html>",
}


def fake_fetch(overrides=None):
    """Build a fetcher returning healthy responses, with optional per-path overrides."""
    overrides = overrides or {}

    def _fetch(url, timeout=None):
        path = url.replace("https://example.test", "") or "/"
        if path in overrides:
            return {"url": url, "bytes": 10, "elapsed_ms": 5, "error": None, **overrides[path]}
        body = BODIES[path]
        return {
            "url": url,
            "status": 200,
            "content_type": "application/json" if path.startswith("/api/") else "text/html; charset=utf-8",
            "body": body,
            "bytes": len(body),
            "elapsed_ms": 12,
            "error": None,
        }

    return _fetch


def test_healthy_site_reports_every_check_ok():
    report = run_checks("https://example.test", fetch=fake_fetch())
    assert report["healthy"] is True
    assert report["warnings"] == []
    # +1: the search-index check is semantic (it reads the payload), so it is not one of ENDPOINTS.
    assert len(report["checks"]) == len(ENDPOINTS) + len(FRONTEND_CHECKS) + 1


def test_non_200_endpoint_becomes_a_warning():
    fetch = fake_fetch({"/api/counter": {"status": 503, "content_type": "application/json", "body": ""}})
    report = run_checks("https://example.test", fetch=fetch)
    assert report["healthy"] is False
    warning = next(w for w in report["warnings"] if w["label"] == "/api/counter")
    assert "expected 200" in warning["notes"]


def test_network_error_becomes_a_warning_not_a_crash():
    fetch = fake_fetch({"/api/health": {"status": None, "content_type": "", "body": "", "error": "URLError: timed out"}})
    report = run_checks("https://example.test", fetch=fetch)
    assert any("timed out" in w["notes"] for w in report["warnings"])


def test_html_served_for_a_json_endpoint_is_caught():
    """The Worker falling through to the landing page is the failure this catches."""
    fetch = fake_fetch({"/api/lessons": {"status": 200, "content_type": "text/html", "body": "<html>oops</html>"}})
    report = run_checks("https://example.test", fetch=fetch)
    warning = next(w for w in report["warnings"] if w["label"] == "/api/lessons")
    assert "content-type" in warning["notes"]


def test_missing_json_key_is_caught():
    fetch = fake_fetch({"/api/counter": {"status": 200, "content_type": "application/json", "body": "{}"}})
    report = run_checks("https://example.test", fetch=fetch)
    assert any("missing key 'current'" in w["notes"] for w in report["warnings"])


def test_invalid_json_is_caught():
    fetch = fake_fetch({"/api/health": {"status": 200, "content_type": "application/json", "body": "{not json"}})
    report = run_checks("https://example.test", fetch=fetch)
    assert any("invalid JSON" in w["notes"] for w in report["warnings"])


def test_frontend_entry_points_are_checked_against_the_page_that_serves_them():
    ok = check_frontend({"/": HOMEPAGE, "/register/": REGISTER})
    assert all(check["ok"] for check in ok)

    degraded = check_frontend({"/": "<html><body>nothing here</body></html>", "/register/": ""})
    missing = {check["label"] for check in degraded if not check["ok"]}
    assert missing == {label for label, _path, _markers in FRONTEND_CHECKS}


def test_the_registration_check_reads_the_register_page_not_the_homepage():
    """The failure #4072 §六 recorded: the form moved to `/register/` in #3641, the check stayed on
    the homepage, and the snapshot reported `missing marker(s): node_name` every day for a form that
    was there the whole time. A warning that can never clear is a warning nobody reads."""
    # The homepage carrying the old markers must not satisfy it…
    checks = {c["label"]: c for c in check_frontend({"/": REGISTER, "/register/": HOMEPAGE})}
    assert checks["Registration"]["ok"] is False
    assert checks["Registration"]["path"] == "/register/"
    # …and the form on its own page must.
    checks = {c["label"]: c for c in check_frontend({"/": HOMEPAGE, "/register/": REGISTER})}
    assert checks["Registration"]["ok"] is True


def test_relative_journey_link_counts_as_present():
    """The homepage links journey/ relatively — an absolute-only match false-alarms."""
    checks = {c["label"]: c for c in check_frontend(
        {"/": '<a href="journey/">Journey</a>' + HOMEPAGE, "/register/": REGISTER})}
    assert checks["Journey link"]["ok"] is True


def test_homepage_is_fetched_once_and_reused_for_frontend_checks():
    calls = []
    base_fetch = fake_fetch()

    def counting_fetch(url, timeout=None):
        calls.append(url)
        return base_fetch(url, timeout)

    run_checks("https://example.test", fetch=counting_fetch)
    assert calls.count("https://example.test/") == 1
    assert calls.count("https://example.test/register/") == 1


def test_markdown_matches_the_issue_template():
    report = run_checks("https://example.test", fetch=fake_fetch())
    markdown = render_markdown(report)
    assert markdown.startswith("# Site Health Snapshot — ")
    assert "| Endpoint | Status | Notes |" in markdown
    for label, *_ in ENDPOINTS:
        assert f"| {label} |" in markdown
    assert "## Warnings" in markdown
    assert "(none)" in markdown


def test_warnings_section_lists_each_problem():
    fetch = fake_fetch({"/search/": {"status": 404, "content_type": "text/html", "body": ""}})
    markdown = render_markdown(run_checks("https://example.test", fetch=fetch))
    assert "(none)" not in markdown
    assert "**/search/**" in markdown


def test_snapshot_doc_exists_for_the_current_release():
    snapshots = sorted((Path(__file__).resolve().parent.parent / "docs" / "maintainer").glob("site-health-*.md"))
    assert snapshots, "at least one site-health-YYYY-MM-DD.md snapshot must be committed (#783)"
    text = snapshots[-1].read_text(encoding="utf-8")
    assert "| Endpoint | Status | Notes |" in text
    assert "## Warnings" in text


# ── the search index must hold the corpus, not merely exist ──────────────────
#
# 2026-10-31: 47 lessons merged; four title-verbatim queries returned `no_match`; the index was healthy
# (`docCount 705`, `behindBy 0`) and the queries had landed inside its five-minute memo window. A check
# that only asserted `available` would have passed all of it and told nobody anything — these assert
# the numbers that would have answered it.

def _index_report(payload, error=""):
    from scripts.site_health_check import check_search_index
    return check_search_index(payload, error)


def test_a_healthy_index_is_ok_and_says_how_many_docs():
    got = _index_report({"available": True, "docCount": 705, "behindBy": 0, "stale": False,
                         "builtAt": "2026-10-31T01:46:04.737Z"})
    assert got["ok"] is True
    assert "705 docs" in got["notes"]
    assert "built 2026-10-31 01:46:04Z" in got["notes"]


def test_an_index_behind_the_corpus_is_a_warning_with_both_numbers():
    got = _index_report({"available": True, "docCount": 658, "behindBy": 47, "stale": True})
    assert got["ok"] is False
    assert "behind by 47" in got["notes"]
    assert "corpus 705" in got["notes"], got["notes"]
    assert "stale" in got["notes"]


def test_an_unavailable_index_is_a_warning():
    got = _index_report({"available": False, "reason": "kv unavailable"})
    assert got["ok"] is False
    assert "not available" in got["notes"]


def test_an_empty_payload_is_a_warning_not_a_pass():
    got = _index_report({})
    assert got["ok"] is False
    assert "did not return an object" in got["notes"]


def test_the_snapshot_reads_the_index_payload_end_to_end():
    report = run_checks("https://example.test", fetch=fake_fetch())
    index = [c for c in report["checks"] if c["label"] == "Search index"]
    assert len(index) == 1 and index[0]["ok"] is True


def test_a_behind_index_makes_the_snapshot_unhealthy():
    import json as _json
    payload = _json.dumps({"available": True, "docCount": 658, "behindBy": 47, "stale": True})
    report = run_checks("https://example.test",
                        fetch=fake_fetch({"/api/search-index": {"status": 200, "content_type": "application/json",
                                                "body": payload}}))
    assert report["healthy"] is False
    assert any(c["label"] == "Search index" for c in report["warnings"])


def test_a_failed_read_is_not_reported_as_an_unhealthy_index():
    got = _index_report({}, "URLError: SSL handshake failed")
    assert got["ok"] is False
    assert "could not be read" in got["notes"]
    assert "URLError: SSL handshake failed" in got["notes"]
    assert "not a claim that the index is healthy" in got["notes"]


def test_an_http_error_on_the_index_endpoint_keeps_its_reason():
    report = run_checks("https://example.test",
                        fetch=fake_fetch({"/api/search-index": {"status": 503, "body": "",
                                                                "error": "HTTP 503"}}))
    index = [c for c in report["checks"] if c["label"] == "Search index"][0]
    assert index["ok"] is False
    assert "HTTP 503" in index["notes"]
