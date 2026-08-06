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
  <form id="registerForm"><input name="agent_type"><input name="node_name"></form>
  <div class="search-box"><input id="searchInput"></div>
  <div id="onboardingModal" class="modal">onboarding</div>
  <a href="journey/">🎮 Journey</a>
</body></html>
"""

BODIES = {
    "/": HOMEPAGE,
    "/api/health": json.dumps({"status": "ok", "hasKV": True}),
    "/api/counter": json.dumps({"current": 10061, "updated": "2026-08-05"}),
    "/api/lessons": json.dumps([{"id": "a"}, {"id": "b"}]),
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
    assert len(report["checks"]) == len(ENDPOINTS) + len(FRONTEND_CHECKS)


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


def test_frontend_entry_points_are_checked_against_the_homepage():
    ok = check_frontend(HOMEPAGE)
    assert all(check["ok"] for check in ok)

    degraded = check_frontend("<html><body>nothing here</body></html>")
    missing = {check["label"] for check in degraded if not check["ok"]}
    assert missing == {label for label, _ in FRONTEND_CHECKS}


def test_relative_journey_link_counts_as_present():
    """The homepage links journey/ relatively — an absolute-only match false-alarms."""
    checks = {c["label"]: c for c in check_frontend('<a href="journey/">Journey</a>' + HOMEPAGE)}
    assert checks["Journey link"]["ok"] is True


def test_homepage_is_fetched_once_and_reused_for_frontend_checks():
    calls = []
    base_fetch = fake_fetch()

    def counting_fetch(url, timeout=None):
        calls.append(url)
        return base_fetch(url, timeout)

    run_checks("https://example.test", fetch=counting_fetch)
    assert calls.count("https://example.test/") == 1


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
