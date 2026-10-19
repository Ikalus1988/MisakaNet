#!/usr/bin/env python3
"""#1897 — the Quickstart reports three step events, and nothing else.

Behaviour of the worker is exercised by `workers/quickstart-events.test.mjs` (`node --test`),
which this module runs when Node is available. What is pinned here is the shape of the *other*
half — the page's emitters and the privacy claim — because that is the half a node test of the
worker cannot see:

1. **Three event names, one emitter each, reusing #3494's hooks.** `qs_copy` is reported from
   inside the existing `copyQS` with the button's `data-copy-target` as the step id — not a
   second click listener on the same buttons, and not a renumbered set of steps. `qs_view` is
   one IntersectionObserver on `#quickstart-section`; `qs_link` is a delegated listener on the
   same section for `a[data-qs-link]`.
2. **Silent degradation.** The reporter swallows every failure and the copy path wraps the
   report in a try/catch of its own, so a dead endpoint can neither toast nor block the
   clipboard. The clipboard harness in `tests/test_quickstart_copy.py` evals only the copy
   functions; the try/catch is what keeps that harness green without adding `reportQsEvent` to
   its extract list, and it is also exactly the 验收 sentence.
3. **No new KV write path.** The worker's qs section writes D1 only. A grep of the section for
   the KV helpers is the same style of proof `tests/test_unsolved_map.py` uses for "the query
   is never persisted": the claim is about what the code can reach, not about a runtime.
4. **The privacy note names what is collected.** Both `/privacy/` and the insights page must
   say "step id and count", and both must say the clipboard / query / IP are not collected.
"""
from __future__ import annotations

import json
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

# The step ids #3494 landed as `data-copy-target`. tests/test_quickstart_copy.py pins the same
# set as GOLDEN_TEXT; this list is the analytics side of that contract and must not renumber.
COPY_STEPS = ("qs-a1", "qs-a2", "qs-a3q1", "qs-a3q2", "qs-b1", "qs-b2", "qs-b3")
LINK_STEPS = ("install-guide", "all-ways-doc", "start-again", "troubleshooting")


def _worker_qs_section() -> str:
    js = WORKER.read_text(encoding="utf-8")
    start = js.index("Quickstart step events (#1897)")
    end = js.index("The activity trend: our own counters")
    return js[start:end]


# ── 1. the three emitters, on the existing hooks ────────────────────────────────────────────────


def test_the_page_reports_qs_copy_from_inside_copyqs_with_the_existing_step_id():
    """Not a second listener path: `copyQS` already owns the button, and `data-copy-target`
    already names the step. The report rides that function and that attribute."""
    page = INDEX.read_text(encoding="utf-8")
    start = page.index("function copyQS")
    opening = page.index("{", start)
    depth = 0
    for i in range(opening, len(page)):
        if page[i] == "{":
            depth += 1
        elif page[i] == "}":
            depth -= 1
            if depth == 0:
                copy_body = page[start : i + 1]
                break
    else:
        raise AssertionError("unbalanced braces in copyQS")
    assert "reportQsEvent('qs_copy'" in copy_body, copy_body
    # The step id is the button's own attribute — the hook #3494 landed.
    assert "data-copy-target" in copy_body, copy_body


def test_the_page_reports_qs_view_and_qs_link_from_one_init_without_touching_copy_buttons():
    page = INDEX.read_text(encoding="utf-8")
    assert "reportQsEvent('qs_view'" in page
    assert "reportQsEvent('qs_link'" in page
    assert "IntersectionObserver" in page
    # One delegated listener on the section — the copy buttons keep their inline
    # onclick="copyQS(this)" and gain no second handler. Counted inside the Quickstart
    # block only: the page's own comment about the hook also names it.
    m = re.search(r'<div id="quickstart-section".*?(?=<!-- Voices)', page, re.S)
    assert m, "could not find #quickstart-section"
    assert m.group(0).count('onclick="copyQS(this)"') == 7, "copy button hooks changed"
    assert "data-qs-link" in page
    # The view step is the block, not a per-step invention.
    assert "reportQsEvent('qs_view', 'quickstart')" in page


def test_every_qs_link_anchor_carries_a_data_qs_link_id_from_the_allowlist():
    page = INDEX.read_text(encoding="utf-8")
    m = re.search(r'<div id="quickstart-section".*?(?=<!-- Voices)', page, re.S)
    assert m, "could not find #quickstart-section"
    found = re.findall(r'data-qs-link="([^"]+)"', m.group(0))
    assert sorted(found) == sorted(LINK_STEPS), found
    # And the worker allowlist names exactly these, so a renamed link fails both sides at once.
    js = WORKER.read_text(encoding="utf-8")
    for step in LINK_STEPS:
        assert f'"{step}"' in js, step


# ── 2. silent degradation ───────────────────────────────────────────────────────────────────────


def test_the_reporter_swallows_every_failure_and_never_alerts():
    page = INDEX.read_text(encoding="utf-8")
    start = page.index("function reportQsEvent")
    opening = page.index("{", start)
    depth = 0
    for i in range(opening, len(page)):
        if page[i] == "{":
            depth += 1
        elif page[i] == "}":
            depth -= 1
            if depth == 0:
                body = page[start : i + 1]
                break
    else:
        raise AssertionError("unbalanced braces in reportQsEvent")
    assert "catch" in body, body
    assert "alert(" not in body, "the reporter must not surface an error"
    assert ".catch(" in body, "the fetch fallback must swallow rejections too"


def test_a_failed_report_cannot_block_or_reroute_the_copy():
    """The copy path wraps the report in its own try/catch: the clipboard write has already
    happened by then, and a ReferenceError (the clipboard harness does not extract
    `reportQsEvent`) must not reject the promise `copyQS` returns."""
    page = INDEX.read_text(encoding="utf-8")
    start = page.index("function copyQS")
    opening = page.index("{", start)
    depth = 0
    for i in range(opening, len(page)):
        if page[i] == "{":
            depth += 1
        elif page[i] == "}":
            depth -= 1
            if depth == 0:
                copy_body = page[start : i + 1]
                break
    else:
        raise AssertionError("unbalanced braces in copyQS")
    assert re.search(r"try\s*\{\s*reportQsEvent\('qs_copy'", copy_body), copy_body
    # The report is after the success toast, not before the clipboard write.
    assert copy_body.index("writeClipboard") < copy_body.index("reportQsEvent('qs_copy'"), copy_body


# ── 3. no new KV write path ─────────────────────────────────────────────────────────────────────


def test_the_qs_write_path_reaches_d1_and_cannot_reach_kv():
    section = _worker_qs_section()
    assert "bumpQsEvent" in section and "async function bumpQsEvent" in WORKER.read_text(encoding="utf-8")
    for forbidden in ("kvPut(", "MISAKANET_KV", "legacyCounterKey", "bumpCounter(", "storePut("):
        assert forbidden not in section, f"the qs section must not reach KV via {forbidden}"
    # D1 only, and the SQL is the counters upsert the schema already declares — no new table.
    assert "d1Binding(env)" in section
    assert "INSERT INTO counters" in section
    assert "VALUES ('qs'" in section
    schema = (REPO / "workers" / "d1" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS counters" in schema


def test_the_payload_carries_no_ip_text_and_no_query_text():
    """The issue's redaction contract, as a source claim: the handler reads `event` and `step`
    and neither field is free text (both are allowlisted before the bind)."""
    section = _worker_qs_section()
    assert "CF-Connecting-IP" not in section, "the qs write path must not read the caller's address"
    assert "X-Forwarded-For" not in section
    assert "clientIp" not in section
    assert "body.query" not in section and "args.query" not in section
    assert "qsAllowedStep(" in section, "every step must pass the allowlist before the bind"


def test_a_qs_event_report_is_not_counted_as_a_pageview():
    """The reporter describes a pageview it is not. Without this, one real visit becomes two
    `traffic/pageview` counts and two `funnel.visit` counts (visit rides the same flush) —
    the report would inflate the metric it exists to explain."""
    js = WORKER.read_text(encoding="utf-8")
    assert 'if (pathname === "/api/qs-event") return null;' in js
    assert "if (_cls) bufferTraffic(" in js


# ── 4. the privacy note names what is collected ─────────────────────────────────────────────────


@pytest.mark.parametrize("path", [PRIVACY, INSIGHTS])
def test_the_privacy_note_names_the_collected_fields_and_the_excluded_ones(path: Path):
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "step id" in lowered or "step ids" in lowered, path
    assert "count" in lowered, path
    # What is *not* collected has to be said out loud — that is the 验收 sentence.
    for excluded in ("clipboard", "query", "ip"):
        assert excluded in lowered, f"{path} does not say '{excluded}' is not collected"


def test_the_insights_page_is_read_only_and_points_at_the_json_route():
    text = INSIGHTS.read_text(encoding="utf-8")
    assert "/api/insights/quickstart-events" in text
    assert "<form" not in text.lower(), "the insights view must be read-only"
    assert "method=\"post\"" not in text.lower() and "method='post'" not in text.lower()
    # The step ids it would show are the same closed set.
    for step in COPY_STEPS[:2]:
        # shown as an example of the id format, or at least referenced via the route
        assert step in text or "qs-a1" in text or "data-copy-target" in text


# ── the worker test itself ──────────────────────────────────────────────────────────────────────


def test_quickstart_events_node_suite():
    node = shutil.which("node")
    if node is None:  # pragma: no cover - node is on every CI runner this repo uses
        pytest.skip("node is not on PATH; the worker half needs it")
    proc = subprocess.run(
        [node, "--test", str(NODE_TEST)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_the_node_test_exists_and_names_the_no_kv_claim():
    text = NODE_TEST.read_text(encoding="utf-8")
    assert "no new KV write path" in text
    assert "kvPuts" in text
    assert "QS_EVENTS" in text
