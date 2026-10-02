#!/usr/bin/env python3
"""The activity trend's static fallback must not be able to show a lie, so the snapshot is gated.

`docs/data/activity-series.json` is what the homepage's chart reads when `/api/activity/history`
cannot be reached (issue #2521). It is the trend sibling of `docs/data/activity.json`, and it carries
that file's failure mode with it — **the file can be wrong and still look like data** — multiplied by
the one property a chart has that a number does not: a chart draws a *shape*, so a hole in the series
becomes a slope and a flat zero week becomes a true-looking quiet period.

So the interesting tests here are the refusals, and they are stricter than the single-day writer's:

* a failed fetch leaves the previous file byte-for-byte as it was;
* a series with a **hole** in it is refused — two points joined across a missing day lie about the
  trend more convincingly than a missing number ever could;
* a series that is zero in **every** day is refused (an unreadable store is not a quiet week);
* each day needs the full four-class breakdown and `total == sum(calls)`;
* `window` has to agree with the series it wraps, or the axis is drawn to the wrong width;
* a material change is what earns a commit — the timestamp alone is not one.

The page's side of the contract — that it renders only what this file (or the live route) writes,
that every class has a label in both dictionaries, and that it draws **no chart** rather than an empty
one when neither answers — lives in `tests/test_activity_history_panel.py`.
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
SCRIPT = REPO / "scripts" / "sync_activity_series.py"

CALL_CLASSES = ("mcp", "agent", "crawler", "pageview")


def day(date: str, mcp: int, agent: int = 10, crawler: int = 2, pageview: int = 4) -> dict:
    calls = {"mcp": mcp, "agent": agent, "crawler": crawler, "pageview": pageview}
    return {"date": date, "total": sum(calls.values()), "calls": calls}


def payload(days: list[dict], source: str = "/api/activity/history") -> dict:
    return {
        "generated_at": f"{days[-1]['date']}T21:00:00Z",
        "source": source,
        "window": {"from": days[0]["date"], "to": days[-1]["date"], "days": len(days)},
        "series": days,
    }


GOOD = payload([
    day("2026-09-25", 15000), day("2026-09-26", 12000), day("2026-09-27", 11000),
    day("2026-09-28", 8000), day("2026-09-29", 8000), day("2026-09-30", 13000),
    day("2026-10-01", 9000),
])


class StubHistory(BaseHTTPRequestHandler):
    """The history endpoint, with the response under test's control."""

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
    StubHistory.status = 200
    StubHistory.body = json.dumps(GOOD).encode()
    StubHistory.calls = []
    yield


@pytest.fixture()
def stub_url():
    server = HTTPServer(("127.0.0.1", 0), StubHistory)
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
    """A file already holding last week's good series."""
    out = tmp_path / "activity-series.json"
    out.write_text(json.dumps(payload([
        day("2026-09-18", 7000), day("2026-09-19", 6000), day("2026-09-20", 5000),
        day("2026-09-21", 9000), day("2026-09-22", 8000), day("2026-09-23", 9302),
        day("2026-09-24", 9681),
    ]), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


# ── the happy path ───────────────────────────────────────────────────────────────────────────────

def test_a_good_response_is_published_under_the_pinned_keys(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    proc = run(stub_url, out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    written = json.loads(out.read_text(encoding="utf-8"))
    assert set(written) == {"generated_at", "source", "window", "series"}, written
    assert written["window"] == {"from": "2026-09-25", "to": "2026-10-01", "days": 7}
    assert [d["date"] for d in written["series"]] == [d["date"] for d in GOOD["series"]]
    assert written["series"][-1]["total"] == 9000 + 10 + 2 + 4


def test_the_snapshot_is_stable_json_so_a_diff_is_readable(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    assert run(stub_url, out).returncode == 0
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    raw = json.loads(text)
    assert list(raw) == sorted(raw), f"keys are not sorted: {list(raw)}"


def test_the_source_can_be_read_without_being_told_where_it_came_from(stub_url, tmp_path):
    """The file is the only record of where the numbers came from, so it has to carry the route."""
    out = tmp_path / "activity-series.json"
    assert run(stub_url, out).returncode == 0
    assert json.loads(out.read_text())["source"] == f"{stub_url}/api/activity/history"


def test_the_window_is_requested_explicitly_and_recorded(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    assert run(stub_url, out, "--days", "7").returncode == 0
    assert any("days=7" in path for path in StubHistory.calls), StubHistory.calls
    assert json.loads(out.read_text())["window"]["days"] == 7


# ── the refusals: what must never be published ───────────────────────────────────────────────────

def test_a_failed_fetch_never_publishes_a_zero_week(stub_url, tmp_path):
    out = previous_file(tmp_path)
    before = out.read_bytes()
    StubHistory.status = 500
    StubHistory.body = b'{"success": false}'
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert out.read_bytes() == before, "the previous series was modified by a failed fetch"
    assert "refusing to write" in proc.stdout, proc.stdout


def test_an_all_zero_series_is_refused(stub_url, tmp_path):
    """Seven zero days is a reader that cannot see the counters, wearing a quiet week's clothes."""
    out = previous_file(tmp_path)
    before = out.read_bytes()
    zero = payload([day(d, 0, 0, 0, 0) for d in
                    ("2026-09-25", "2026-09-26", "2026-09-27", "2026-09-28", "2026-09-29",
                     "2026-09-30", "2026-10-01")])
    StubHistory.body = json.dumps(zero).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "every day totals 0" in proc.stdout, proc.stdout
    assert out.read_bytes() == before


def test_a_hole_in_the_series_is_refused(stub_url, tmp_path):
    """The chart joins points across a gap as if it were a slope; a hole is refused, not drawn."""
    out = tmp_path / "activity-series.json"
    holed = payload([day("2026-09-25", 15000), day("2026-09-26", 12000),
                     day("2026-09-28", 8000), day("2026-09-29", 8000)])
    StubHistory.body = json.dumps(holed).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "hole in the series" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_truncated_day_is_refused(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    days = [dict(d) for d in GOOD["series"]]
    days[-1] = {"date": "2026-10-01", "total": 9016,
                "calls": {"mcp": 9000, "agent": 10, "crawler": 2}}  # no pageview
    StubHistory.body = json.dumps(payload(days)).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "missing ['pageview']" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_class_the_schema_does_not_know_is_a_hard_error(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    days = [dict(d) for d in GOOD["series"]]
    last = dict(days[-1])
    last["calls"] = {**last["calls"], "webmcp": 20}
    last["total"] = sum(last["calls"].values())
    days[-1] = last
    StubHistory.body = json.dumps(payload(days)).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "webmcp" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_total_that_disagrees_with_its_parts_is_refused(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    days = [dict(d) for d in GOOD["series"]]
    days[-1] = {**days[-1], "total": 100}
    StubHistory.body = json.dumps(payload(days)).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "inconsistent" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_window_that_disagrees_with_the_series_is_refused(stub_url, tmp_path):
    """The axis is drawn from `window`; a mismatch draws it to the wrong width."""
    out = tmp_path / "activity-series.json"
    body = payload(GOOD["series"])
    body["window"] = {"from": "2026-09-01", "to": "2026-10-01", "days": 7}
    StubHistory.body = json.dumps(body).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "window is" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_length_that_disagrees_with_the_window_is_refused(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    body = payload(GOOD["series"])
    body["window"] = {**body["window"], "days": 30}
    StubHistory.body = json.dumps(body).encode()
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "wrong width" in proc.stdout, proc.stdout
    assert not out.exists()


def test_a_body_that_is_not_json_at_all_is_refused(stub_url, tmp_path):
    out = previous_file(tmp_path)
    before = out.read_bytes()
    StubHistory.body = b"<html>502 Bad Gateway</html>"
    proc = run(stub_url, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert out.read_bytes() == before


# ── --check: the committed file ──────────────────────────────────────────────────────────────────

def test_check_accepts_a_missing_file_because_no_chart_is_a_designed_state(stub_url, tmp_path):
    """Unlike `activity.json` (the fallback for the panel's *numbers*), absence here is not a failure."""
    out = tmp_path / "activity-series.json"
    proc = run(stub_url, out, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "absent" in proc.stdout, proc.stdout
    assert not out.exists(), "--check must not write"


def test_check_validates_a_committed_file_and_rejects_a_hole(tmp_path):
    out = previous_file(tmp_path)
    proc = run("http://127.0.0.1:1", out, "--check")  # no network: --check never fetches
    assert proc.returncode == 0, proc.stdout + proc.stderr

    broken = json.loads(out.read_text())
    broken["series"] = broken["series"][:2] + broken["series"][3:]
    broken["window"]["days"] = 6
    out.write_text(json.dumps(broken), encoding="utf-8")
    proc = run("http://127.0.0.1:1", out, "--check")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "hole in the series" in proc.stdout, proc.stdout


# ── what earns a commit ──────────────────────────────────────────────────────────────────────────

def test_an_unchanged_week_writes_nothing(stub_url, tmp_path):
    out = tmp_path / "activity-series.json"
    assert run(stub_url, out).returncode == 0
    first = out.read_bytes()
    proc = run(stub_url, out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "nothing to write" in proc.stdout, proc.stdout
    assert out.read_bytes() == first, "generated_at alone must not cause a rewrite"


def test_a_new_day_is_a_material_change(stub_url, tmp_path):
    out = previous_file(tmp_path)
    assert run(stub_url, out).returncode == 0
    written = json.loads(out.read_text())
    assert written["window"]["to"] == "2026-10-01"
    assert [d["date"] for d in written["series"]][-1] == "2026-10-01"


def test_the_script_reads_the_history_route_and_not_the_day_route(stub_url, tmp_path):
    """`/api/analytics/traffic` is maintainer-aware and must never be this file's source."""
    out = tmp_path / "activity-series.json"
    assert run(stub_url, out).returncode == 0
    for path in StubHistory.calls:
        assert path.startswith("/api/activity/history"), path
        assert "analytics" not in path


# ── --from-committed-snapshots: the bootstrap ────────────────────────────────────────────────────
#
# Before `/api/activity/history` is deployed there is no endpoint to read a series from, and a chart
# with no data is a chart that cannot be reviewed. This mode rebuilds the series from what the
# repository has already committed (`docs/data/activity.json`, every three hours since 2026-09-24) —
# real measurements, each in git — and labels the result as what it is: a **lower bound** per day,
# because the last snapshot of a day was taken before that day ended.


def day_snapshot(date: str, total: int, calls: dict) -> dict:
    return {"generated_at": f"{date}T21:00:00Z", "source": "https://misakanet.org/api/analytics/traffic",
            "date": date, "total": total, "calls": calls}


def make_repo(tmp_path: pathlib.Path, snapshots: list[dict]) -> pathlib.Path:
    """A git repository whose history holds these versions of docs/data/activity.json, one per commit."""
    repo = tmp_path / "repo"
    (repo / "docs" / "data").mkdir(parents=True)
    for command in (["git", "init", "-q"], ["git", "config", "user.email", "test@example.com"],
                    ["git", "config", "user.name", "test"]):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
    for snap in snapshots:
        (repo / "docs" / "data" / "activity.json").write_text(json.dumps(snap), encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "snapshot"], cwd=repo, check=True, capture_output=True)
    return repo


def run_bootstrap(repo: pathlib.Path, out: pathlib.Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--from-committed-snapshots", "--repo", str(repo),
         "--out", str(out), *extra],
        capture_output=True, text=True,
    )


def test_the_bootstrap_writes_a_labeled_lower_bound_series(tmp_path):
    """Three finished days of committed snapshots, plus one for today (dropped: still counting)."""
    import datetime as dt

    today = dt.datetime.now(dt.timezone.utc).date()
    days = [(today - dt.timedelta(days=n)).isoformat() for n in (3, 2, 1, 0)]
    # total is always the sum of its classes, as `validate` demands of any source.
    def counted(mcp: int) -> tuple:
        return mcp + 16, {"mcp": mcp, "agent": 10, "crawler": 2, "pageview": 4}

    repo = make_repo(tmp_path, [
        day_snapshot(days[0], *counted(1000)),
        day_snapshot(days[1], *counted(2000)),
        # two snapshots of the same day: the higher total is the later measurement of it
        day_snapshot(days[2], *counted(3000)),
        day_snapshot(days[2], *counted(3500)),
        day_snapshot(days[3], *counted(983)),  # today: in progress, must not be drawn
    ])
    out = tmp_path / "activity-series.json"
    proc = run_bootstrap(repo, out, "--days", "7")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["source"] == "git-history:docs/data/activity.json"
    assert [d["date"] for d in written["series"]] == days[:3]
    assert [d["total"] for d in written["series"]] == [1016, 2016, 3516], "the better snapshot of a day won"
    assert written["window"] == {"from": days[0], "to": days[2], "days": 3}
    assert [d["date"] for d in written["series"]].count(days[3]) == 0, (
        "a day still in progress was published as a total")


def test_the_bootstrap_never_spans_a_hole(tmp_path):
    """A gap in the commits is a gap in the data; the newest contiguous stretch is what gets drawn."""
    import datetime as dt

    today = dt.datetime.now(dt.timezone.utc).date()
    call = {"mcp": 1, "agent": 1, "crawler": 1, "pageview": 1}
    dates = [(today - dt.timedelta(days=n)).isoformat() for n in (6, 5, 4, 2, 1)]
    repo = make_repo(tmp_path, [day_snapshot(d, 4, dict(call)) for d in dates])
    out = tmp_path / "activity-series.json"
    proc = run_bootstrap(repo, out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    written = json.loads(out.read_text(encoding="utf-8"))
    # dates[3:] is the newest contiguous run (the isolated day at the far end is not part of it)
    assert [d["date"] for d in written["series"]] == dates[3:], written["series"]


def test_the_bootstrap_refuses_when_there_is_no_two_day_stretch(tmp_path):
    import datetime as dt

    today = dt.datetime.now(dt.timezone.utc).date()
    call = {"mcp": 1, "agent": 1, "crawler": 1, "pageview": 1}
    lone = (today - dt.timedelta(days=3)).isoformat()
    repo = make_repo(tmp_path, [day_snapshot(lone, 4, dict(call))])
    out = tmp_path / "activity-series.json"
    proc = run_bootstrap(repo, out)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "not a trend" in proc.stdout, proc.stdout
    assert not out.exists()


def test_the_bootstrap_output_passes_the_same_gate_as_the_endpoint_output(tmp_path):
    """One judge for both sources: `validate` must not be able to tell them apart structurally."""
    import datetime as dt
    import sync_activity_series

    today = dt.datetime.now(dt.timezone.utc).date()
    call = {"mcp": 5, "agent": 5, "crawler": 5, "pageview": 5}
    repo = make_repo(tmp_path, [
        day_snapshot((today - dt.timedelta(days=n)).isoformat(), 20, dict(call)) for n in (2, 1)
    ])
    out = tmp_path / "activity-series.json"
    assert run_bootstrap(repo, out).returncode == 0
    sync_activity_series.validate(json.loads(out.read_text()), where=str(out))
