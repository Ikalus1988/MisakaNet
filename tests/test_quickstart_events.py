#!/usr/bin/env python3
"""#1897 — the Quickstart reports three step events, and nothing else.

Worker behaviour lives in workers/quickstart-events.test.mjs. This file pins the page's
emitters, the silent-degradation contract, the "no new KV write path" source claim, and the
privacy note — the halves a node test of the worker cannot see.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
WORKER = REPO / "workers" / "register-proxy-sw.js"
PRIVACY = REPO / "docs" / "privacy" / "index.html"
INSIGHTS = REPO / "docs" / "insights" / "quickstart-events.html"
NODE_TEST = REPO / "workers" / "quickstart-events.test.mjs"

# #3494's `data-copy-target` values — the analytics side of the same contract, same set as
# GOLDEN_TEXT in tests/test_quickstart_copy.py. Do not renumber.
COPY_STEPS = ("qs-a1", "qs-a2", "qs-a3q1", "qs-a3q2", "qs-b1", "qs-b2", "qs-b3")
LINK_STEPS = ("install-guide", "all-ways-doc", "start-again", "troubleshooting")


def _fn(page: str, name: str) -> str:
    start = page.index(f"function {name}")
    depth = 0
    for i in range(page.index("{", start), len(page)):
        if page[i] == "{":
            depth += 1
        elif page[i] == "}":
            depth -= 1
            if depth == 0:
                return page[start : i + 1]
    raise AssertionError(f"unbalanced braces in {name}")


def _worker_qs_section() -> str:
    js = WORKER.read_text(encoding="utf-8")
    return js[js.index("Quickstart step events (#1897)") : js.index("The activity trend: our own counters")]


# ── 1. the three emitters, on the existing hooks ────────────────────────────────────────────────


def test_the_page_reports_qs_copy_from_inside_copyqs_with_the_existing_step_id():
    """Not a second listener path: `copyQS` owns the button and `data-copy-target` names the step."""
    copy_body = _fn(INDEX.read_text(encoding="utf-8"), "copyQS")
    assert "reportQsEvent('qs_copy'" in copy_body, copy_body
    assert "data-copy-target" in copy_body, copy_body


def test_the_page_reports_qs_view_and_qs_link_from_one_init_without_touching_copy_buttons():
    page = INDEX.read_text(encoding="utf-8")
    assert "reportQsEvent('qs_view', 'quickstart')" in page
    assert "reportQsEvent('qs_link'" in page
    assert "IntersectionObserver" in page
    # Counted inside the Quickstart block only: the page's own comment names the hook too.
    m = re.search(r'<div id="quickstart-section".*?(?=<!-- Voices)', page, re.S)
    assert m, "could not find #quickstart-section"
    assert m.group(0).count('onclick="copyQS(this)"') == 7, "copy button hooks changed"
    assert "data-qs-link" in page


def test_every_qs_link_anchor_carries_a_data_qs_link_id_from_the_allowlist():
    page = INDEX.read_text(encoding="utf-8")
    m = re.search(r'<div id="quickstart-section".*?(?=<!-- Voices)', page, re.S)
    assert m, "could not find #quickstart-section"
    found = re.findall(r'data-qs-link="([^"]+)"', m.group(0))
    assert sorted(found) == sorted(LINK_STEPS), found
    js = WORKER.read_text(encoding="utf-8")
    for step in LINK_STEPS:
        assert f'"{step}"' in js, step


# ── 2. silent degradation ───────────────────────────────────────────────────────────────────────


def test_the_reporter_swallows_every_failure_and_never_alerts():
    body = _fn(INDEX.read_text(encoding="utf-8"), "reportQsEvent")
    assert "catch" in body, body
    assert "alert(" not in body, "the reporter must not surface an error"
    # sendBeacon only: a `fetch(` here would push the homepage past the 14 request targets
    # tests/test_site_request_fanout.py asks a reviewer to hold in one list.
    assert "fetch(" not in body, body
    assert "sendBeacon" in body, body


def test_a_failed_report_cannot_block_or_reroute_the_copy():
    """The copy path wraps the report in its own try/catch: the clipboard write has already
    happened, and a missing reporter must not reject the promise `copyQS` returns."""
    copy_body = _fn(INDEX.read_text(encoding="utf-8"), "copyQS")
    assert re.search(r"try\s*\{\s*reportQsEvent\('qs_copy'", copy_body), copy_body
    assert copy_body.index("writeClipboard") < copy_body.index("reportQsEvent('qs_copy'"), copy_body


# ── 3. no new KV write path ─────────────────────────────────────────────────────────────────────


def test_the_qs_write_path_reaches_d1_and_cannot_reach_kv():
    section = _worker_qs_section()
    for forbidden in ("kvPut(", "MISAKANET_KV", "legacyCounterKey", "bumpCounter(", "storePut("):
        assert forbidden not in section, f"the qs section must not reach KV via {forbidden}"
    assert "d1Binding(env)" in section
    assert "INSERT INTO counters" in section
    assert "VALUES ('qs'" in section
    schema = (REPO / "workers" / "d1" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS counters" in schema


def test_the_payload_carries_no_ip_text_and_no_query_text():
    """The handler reads `event` and `step`, both allowlisted before the bind; it reads no address."""
    section = _worker_qs_section()
    assert "CF-Connecting-IP" not in section
    assert "X-Forwarded-For" not in section
    assert "clientIp" not in section
    assert "body.query" not in section and "args.query" not in section
    assert "qsAllowedStep(" in section


def test_a_qs_event_report_is_not_counted_as_a_pageview():
    """Without this, one real visit becomes two `traffic/pageview` and two `funnel.visit` counts."""
    js = WORKER.read_text(encoding="utf-8")
    assert 'if (pathname === "/api/qs-event") return null;' in js
    assert "if (_cls) bufferTraffic(" in js


# ── 4. the privacy note names what is collected ─────────────────────────────────────────────────


@pytest.mark.parametrize("path", [PRIVACY, INSIGHTS])
def test_the_privacy_note_names_the_collected_fields_and_the_excluded_ones(path: Path):
    text = path.read_text(encoding="utf-8").lower()
    assert "step id" in text or "step ids" in text, path
    assert "count" in text, path
    for excluded in ("clipboard", "query", "ip"):
        assert excluded in text, f"{path} does not say '{excluded}' is not collected"


def test_the_insights_page_is_read_only_and_points_at_the_json_route():
    text = INSIGHTS.read_text(encoding="utf-8")
    assert "/api/insights/quickstart-events" in text
    assert "<form" not in text.lower()
    assert "method=\"post\"" not in text.lower() and "method='post'" not in text.lower()


# ── the worker test itself ──────────────────────────────────────────────────────────────────────


def test_quickstart_events_node_suite():
    node = shutil.which("node")
    if node is None:  # pragma: no cover
        pytest.skip("node is not on PATH; the worker half needs it")
    proc = subprocess.run(
        [node, "--test", str(NODE_TEST)], cwd=str(REPO), capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_the_node_test_exists_and_names_the_no_kv_claim():
    text = NODE_TEST.read_text(encoding="utf-8")
    assert "no new KV write path" in text
    assert "kvPuts" in text
    assert "QS_EVENTS" in text
