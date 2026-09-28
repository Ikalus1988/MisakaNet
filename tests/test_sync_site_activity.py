#!/usr/bin/env python3
"""The homepage's activity panel must not be able to show a lie, so the snapshot is gated.

`docs/data/activity.json` exists because `/api/analytics/traffic` is correct and unusable from a
browser: measured 2026-09-24 in five consecutive requests, it answered in 0.66–0.75s from cache and
**17.4s** when it recomputed. Putting that on a homepage is how #2151's ~2,700 504s were made.

A snapshot introduces the failure mode a live endpoint does not have: **the file can be wrong and
still look like data**. `{"total": 0}` renders as "no calls today" — a perfectly plausible sentence
about a site doing 9,000 calls a day — and it is exactly what a failed fetch, a truncated body or a
schema change upstream produces. So the interesting tests here are the refusals:

* a failed fetch leaves the previous file **byte-for-byte** as it was (never a zero);
* `total == sum(breakdown)` is enforced, because that is what a truncated response breaks;
* a class the schema does not know is a hard error rather than a silently dropped number;
* a material change is what earns a commit — the timestamp alone is not one.

The page's side of the contract — that it renders exactly these classes, in both languages, from
this file and never from the live endpoint — lives in `tests/test_site_activity_panel.py`, next to the
markup it describes.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "sync_site_activity.py"

GOOD = {"date": "2026-09-24", "breakdown": {"mcp": 9053, "agent": 27, "crawler": 71, "pageview": 530},
        "total": 9681}


class StubTraffic(BaseHTTPRequestHandler):
    """The traffic endpoint, with the response under test's control."""

    status = 200
    body: bytes = b""
    calls: list = []

    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802 (http.server naming)
        type(self).calls.append(self.path)
        raw = self.body
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture(autouse=True)
def _reset():
    StubTraffic.status = 200
    StubTraffic.body = json.dumps(GOOD).encode()
    StubTraffic.calls = []
    yield


@pytest.fixture()
def stub_url():
    server = HTTPServer(("127.0.0.1", 0), StubTraffic)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def run(base: str, out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, "--out", str(out), *extra],
        capture_output=True, text=True,
    )


def previous_file(tmp_path: pathlib.Path) -> pathlib.Path:
    """A file already holding yesterday's good snapshot."""
    out = tmp_path / "activity.json"
    out.write_text(json.dumps({
        "calls": {"agent": 18, "crawler": 71, "mcp": 8687, "pageview": 526},
        "date": "2026-09-23", "generated_at": "2026-09-23T21:00:00Z",
        "source": "https://misakanet.org/api/analytics/traffic", "total": 9302,
    }, indent=2) + "\n", encoding="utf-8")
    return out


# ── the happy path ───────────────────────────────────────────────────────────────────────────────

def test_a_good_response_is_published_under_the_pinned_keys(stub_url, tmp_path):
    out = tmp_path / "activity.json"
    proc = run(stub_url, out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    written = json.loads(out.read_text(encoding="utf-8"))
    assert set(written) == {"generated_at", "source", "date", "total", "calls"}, written
    assert written["date"] == "2026-09-24"
    assert written["total"] == 9681
    assert written["calls"]["mcp"] == 9053
    assert written["source"].endswith("/api/analytics/traffic"), written["source"]


def test_the_snapshot_is_stable_json_so_a_diff_is_readable(stub_url, tmp_path):
    """It lands as a commit every few hours; an unstable key order would be noise in every diff."""
    out = tmp_path / "activity.json"
    assert run(stub_url, out).returncode == 0
    first = out.read_text(encoding="utf-8")
    assert first.endswith("\n")
    raw = json.loads(first)
    assert list(raw) == sorted(raw), f"keys are not sorted: {list(raw)}"
    assert '"agent"' in first and first.index('"calls"') < first.index('"date"')


def test_the_source_can_be_read_without_being_told_where_it_came_from(stub_url, tmp_path):
    """The file is the only record of where the number came from, so it has to carry the URL."""
    out = tmp_path / "activity.json"
    assert run(stub_url, out).returncode == 0
    assert json.loads(out.read_text())["source"] == f"{stub_url}/api/analytics/traffic"


# ── the refusals: what must never be published ───────────────────────────────────────────────────

def test_a_failed_fetch_never_publishes_a_zero(stub_url, tmp_path):
    """The whole point. `{"total": 0}` is a *plausible* sentence about a busy site."""
    out = previous_file(tmp_path)
    before = out.read_bytes()
    StubTraffic.status = 500
    StubTraffic.body = b'{"success": false}'
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert out.read_bytes() == before, "the previous snapshot was modified by a failed fetch"
    assert "refusing to write" in proc.stdout, proc.stdout
    assert json.loads(out.read_text())["total"] == 9302, "yesterday's number survived"


def test_an_endpoint_that_answers_zero_is_refused(stub_url, tmp_path):
    out = previous_file(tmp_path)
    before = out.read_bytes()
    StubTraffic.body = json.dumps({"date": "2026-09-24", "total": 0,
                                   "breakdown": {"mcp": 0, "agent": 0, "crawler": 0, "pageview": 0}}).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "total is 0" in proc.stdout, proc.stdout
    assert out.read_bytes() == before


def test_a_truncated_response_is_refused(stub_url, tmp_path):
    """`total` disagreeing with its own parts is what a body cut mid-flight looks like."""
    out = tmp_path / "activity.json"
    StubTraffic.body = json.dumps({"date": "2026-09-24", "total": 9681,
                                   "breakdown": {"mcp": 9053, "agent": 27, "crawler": 71}}).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "missing ['pageview']" in proc.stdout, proc.stdout
    assert not out.exists(), "a partial breakdown was written"


def test_a_class_the_schema_does_not_know_is_a_hard_error(stub_url, tmp_path):
    """A fifth class must fail loudly, not be dropped: the page would show a smaller number."""
    out = tmp_path / "activity.json"
    StubTraffic.body = json.dumps({
        "date": "2026-09-24", "total": 9701,
        "breakdown": {"mcp": 9053, "agent": 27, "crawler": 71, "pageview": 530, "webmcp": 20},
    }).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "does not" in proc.stdout and "webmcp" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_total_that_disagrees_with_its_parts_is_refused(stub_url, tmp_path):
    out = tmp_path / "activity.json"
    StubTraffic.body = json.dumps({"date": "2026-09-24", "total": 100,
                                   "breakdown": {"mcp": 9053, "agent": 27, "crawler": 71,
                                                 "pageview": 530}}).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "inconsistent" in proc.stdout, proc.stdout


def test_a_non_iso_date_is_refused(stub_url, tmp_path):
    out = tmp_path / "activity.json"
    StubTraffic.body = json.dumps({"date": "today", "total": 5,
                                   "breakdown": {"mcp": 5, "agent": 0, "crawler": 0,
                                                 "pageview": 0}}).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ISO8601" in proc.stdout, proc.stdout


def test_a_body_that_is_not_json_at_all_is_refused(stub_url, tmp_path):
    out = previous_file(tmp_path)
    before = out.read_bytes()
    StubTraffic.body = b"<html>502 Bad Gateway</html>"
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert out.read_bytes() == before


# ── what earns a commit ──────────────────────────────────────────────────────────────────────────

def test_an_unchanged_day_writes_nothing(stub_url, tmp_path):
    """A bot that opens a pull request to move a timestamp is churn where churn costs CI runs."""
    out = tmp_path / "activity.json"
    assert run(stub_url, out).returncode == 0
    first = out.read_bytes()
    proc = run(stub_url, out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "nothing to write" in proc.stdout, proc.stdout
    assert out.read_bytes() == first, "generated_at alone must not cause a rewrite"


def test_force_writes_anyway(stub_url, tmp_path):
    """`--force` exists for the case the material check cannot express: the file was tampered with.

    Note what the non-forced run does here — it leaves the tampered timestamp alone, because the
    material fields did not move. That is the intended behaviour (a bot must not open a pull request
    to move a timestamp), and it is also why `--force` has to exist.
    """
    out = tmp_path / "activity.json"
    assert run(stub_url, out).returncode == 0
    tampered = json.loads(out.read_text(encoding="utf-8"))
    tampered["generated_at"] = "1999-01-01T00:00:00Z"
    out.write_text(json.dumps(tampered, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert run(stub_url, out).returncode == 0
    assert json.loads(out.read_text())["generated_at"] == "1999-01-01T00:00:00Z", (
        "an unchanged-day run rewrote the file, which is churn"
    )

    assert run(stub_url, out, "--force").returncode == 0
    forced = json.loads(out.read_text())
    assert forced["generated_at"] != "1999-01-01T00:00:00Z", "--force did not rewrite the snapshot"
    assert forced["total"] == tampered["total"], "the rewrite lost the data"


def test_a_moved_total_is_written(stub_url, tmp_path):
    out = tmp_path / "activity.json"
    assert run(stub_url, out).returncode == 0
    StubTraffic.body = json.dumps({**GOOD, "total": 9682,
                                   "breakdown": {**GOOD["breakdown"], "mcp": 9054}}).encode()
    assert run(stub_url, out).returncode == 0
    assert json.loads(out.read_text())["total"] == 9682


# ── --check: what CI runs ────────────────────────────────────────────────────────────────────────

def test_check_accepts_the_committed_file():
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "is a valid snapshot" in proc.stdout, proc.stdout


def test_check_rejects_a_zeroed_file(tmp_path):
    """The shape a "fix" would take if someone decided to blank the file rather than fail the job."""
    out = tmp_path / "activity.json"
    out.write_text(json.dumps({"calls": {"mcp": 0, "agent": 0, "crawler": 0, "pageview": 0},
                               "date": "2026-09-24", "generated_at": "2026-09-24T00:00:00Z",
                               "source": "x", "total": 0}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", "--out", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "total is 0" in proc.stdout, proc.stdout


def test_check_rejects_a_missing_file(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", "--out",
                           str(tmp_path / "nope.json")], capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "does not exist" in proc.stdout, proc.stdout


def test_check_rejects_an_unknown_class(tmp_path):
    out = tmp_path / "activity.json"
    payload = {"calls": {"mcp": 1, "agent": 0, "crawler": 0, "pageview": 0, "smtp": 4},
               "date": "2026-09-24", "generated_at": "2026-09-24T00:00:00Z", "source": "x", "total": 5}
    out.write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--check", "--out", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "smtp" in proc.stdout, proc.stdout
