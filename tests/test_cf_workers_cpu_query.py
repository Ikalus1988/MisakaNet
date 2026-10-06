#!/usr/bin/env python3
"""The Workers CPU query asserts nothing about Cloudflare's schema, and fails loudly when it cannot.

Why this file exists (#2897)
----------------------------
Every published claim about worker cost here was a **local Node proxy** number — `0.093` to
`0.196` ms/req, measured in a maintainer's terminal. That is a different runtime
(workerd vs Node) and a different unit from the one that is billed: Cloudflare charges **CPU
milliseconds per request** against a hard ceiling (10 ms free, 30 ms paid). The two numbers were
never comparable, and the one that was comparable could not be read, because the token on that
machine had expired. So the question sat open and the honest answer was "unmeasured".

CI *can* reach Cloudflare — `deploy-worker.yml` proves it on every release — and
`cf-diagnostics.yml` already holds `CF_OBSERVABILITY_TOKEN` and a GraphQL harness. The missing
piece was one query. This step adds it on a schedule rather than in someone's terminal.

What this file checks
---------------------
The step extracts its Python from the YAML — not a copy of it — and runs it against a stub:

1. **The dataset and metric are discovered.** The stub's schema calls the CPU field
   `cpuTimeMicroseconds`; a second case renames it again. A step that hardcoded a field name would
   fail both, which is the point: `cf-diagnostics.yml` has already cost three human approvals to a
   guessed field name (#2135, #2136), and a wrong-but-*existing* field is worse than a missing one
   because it validates and prints a confident, meaningless number.
2. **A GraphQL `errors` list fails the step.** This is the failure that already happened: run 4
   reported `success` while printing an empty table.
3. **A missing CPU field is a warning, not a fake number.** A duration-like field measures
   wall-clock, which `waitUntil` can inflate without costing anything — reporting it as CPU would
   reproduce the original confusion.
4. **A p99 over the billed ceiling fails the step**, because that is a real billing problem.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml
from subprocess_env import child_env  # tests/subprocess_env.py

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "cf-diagnostics.yml"
STEP_PREFIX = "Workers CPU time per script"


def step_script() -> str:
    """The `run:` body of the CPU step, exactly as CI executes it."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["diagnose"]["steps"]:
        if (step.get("name") or "").startswith(STEP_PREFIX):
            return step["run"]
    raise AssertionError(f"no step starting {STEP_PREFIX!r} in {WORKFLOW.name}")


def python_block(script: str) -> str:
    """The heredoc body, scanned rather than regexed — CodeQL alert #281 flagged the regex form."""
    opener = "python3 - <<'PY'\n"
    start = script.find(opener)
    assert start != -1, "the step no longer runs a python heredoc; fix this test with the step"
    body_start = start + len(opener)
    end = script.find("\nPY\n", body_start)
    assert end != -1, "the python heredoc in the step is never closed"
    return script[body_start:end]


class StubGraphQL(BaseHTTPRequestHandler):
    """A schema the step must read rather than assume, and one switch to make it lie."""

    type_name = "WorkersWorkersAdaptiveGroups"
    fields = ["cpuTimeMicroseconds", "scriptName", "requests", "datetime", "duration"]
    # p99 of the busiest script, in the same unit the step prints.
    rows = [
        {"sum": {"cpuTimeMicroseconds": 41230.5}, "max": {"cpuTimeMicroseconds": 8.9},
         "quantiles": {"p50": 0.21, "p95": 1.4, "p99": 2.7},
         "dimensions": {"scriptName": "misakanet-web"}},
        {"sum": {"cpuTimeMicroseconds": 90.0}, "max": {"cpuTimeMicroseconds": 0.4},
         "quantiles": {"p50": 0.05, "p95": 0.2, "p99": 0.3},
         "dimensions": {"scriptName": "misakanet-inbox"}},
    ]
    data_error: str | None = None
    seen: list[str] = []

    def log_message(self, *args):  # keep pytest output clean
        pass

    def do_POST(self):  # noqa: N802 (http.server naming)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        query = body.get("query", "")
        type(self).seen.append(query)

        if "__schema" in query:
            payload = {"data": {"__schema": {"types": [{"name": n} for n in
                                                       ["ZoneHttpRequestsAdaptiveGroups",
                                                        self.type_name]]}}}
        elif "__type" in query:
            payload = {"data": {"__type": {"fields": [{"name": n} for n in self.fields]}}}
        elif type(self).data_error:
            payload = {"errors": [{"message": type(self).data_error}]}
        else:
            payload = {"data": {"viewer": {"accounts": [{self.type_name: self.rows}]}}}
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture()
def stub():
    StubGraphQL.seen = []
    StubGraphQL.data_error = None
    server = HTTPServer(("127.0.0.1", 0), StubGraphQL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/graphql"
    finally:
        server.shutdown()
        server.server_close()


def run_step(endpoint: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", python_block(step_script())],
        capture_output=True, text=True, timeout=120,
        env=child_env({
            "CLOUDFLARE_ACCOUNT_ID": "6b92325b505f2b76aec49e9fe4195d31",
            "CLOUDFLARE_API_TOKEN": "stub-token",
            "CF_GRAPHQL_URL": endpoint,
            "HOURS": "24",
        }),
    )


def test_the_cpu_field_comes_from_the_schema_not_from_the_workflow(stub):
    """The stub calls it `cpuTimeMicroseconds`; nothing in the workflow hardcodes that."""
    result = run_step(stub)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "misakanet-web" in result.stdout, result.stdout
    assert "misakanet-inbox" in result.stdout, result.stdout
    assert any("cpuTimeMicroseconds" in q and "__type" not in q for q in StubGraphQL.seen), \
        StubGraphQL.seen
    # And the local proxy number this replaces was never CPU: 0.196 ms/req at the top of the range.
    assert "billed ceiling" in result.stdout, result.stdout


def test_a_different_cpu_field_name_is_discovered_too(stub, monkeypatch):
    # The stub renames the field in the schema *and* in the data it returns, because that is what a
    # real account does: the response key is the schema key. A step that hardcoded `cpuTime` would
    # fail here; one that discovers it asks for `cpuTimeTotalMicroseconds` and gets a full table.
    monkeypatch.setattr(StubGraphQL, "fields",
                        ["cpuTimeTotalMicroseconds", "scriptName", "requests", "datetime"])
    monkeypatch.setattr(StubGraphQL, "rows",
                        [{**r, "sum": {"cpuTimeTotalMicroseconds": 1200.0}}
                         for r in StubGraphQL.rows])
    result = run_step(stub)
    assert result.returncode == 0, result.stdout + result.stderr
    assert any("cpuTimeTotalMicroseconds" in q and "__type" not in q for q in StubGraphQL.seen), \
        StubGraphQL.seen


def test_the_report_states_the_unit_and_the_ceiling(stub):
    """A CPU number with no unit is how the local proxy number got misread to begin with."""
    result = run_step(stub)
    assert "billed ceiling" in result.stdout, result.stdout
    assert "ms" in result.stdout, result.stdout
    # The per-request percentile, not the total, is what the ceiling applies to.
    assert "p99 CPU per request" in result.stdout, result.stdout


def test_a_graphql_error_fails_the_step_instead_of_printing_an_empty_table(stub, monkeypatch):
    """The trap this workflow already fell into: run 4 reported success on an empty result."""
    monkeypatch.setattr(StubGraphQL, "data_error", 'Cannot query field "sum" on type "X".')
    result = run_step(stub)
    assert result.returncode == 1, (
        "a GraphQL validation error must fail the step — exiting 0 here is how a run reports "
        f"success while printing nothing. stdout was:\n{result.stdout}"
    )
    assert "::error::" in result.stdout, result.stdout


def test_no_cpu_field_is_a_warning_not_a_substitute_number(stub, monkeypatch):
    """`duration` measures wall-clock. Reporting it as CPU would recreate the original confusion."""
    monkeypatch.setattr(StubGraphQL, "fields", ["duration", "scriptName", "requests", "datetime"])
    result = run_step(stub)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning::" in result.stdout, result.stdout
    assert "wall-clock" in result.stdout, result.stdout
    assert "misakanet-web" not in result.stdout, (
        "a table was printed without a CPU metric — that is the empty-table failure wearing a hat"
    )


def test_no_workers_dataset_is_reported_rather_than_guessed(stub, monkeypatch):
    monkeypatch.setattr(StubGraphQL, "type_name", "ZoneHttpRequestsAdaptiveGroups")
    result = run_step(stub)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning::" in result.stdout, result.stdout
    assert "no Workers adaptive-groups dataset" in result.stdout, result.stdout


def test_a_p99_over_the_ceiling_fails_the_step(stub, monkeypatch):
    """A real billing problem must not print as another green row."""
    rows = [dict(StubGraphQL.rows[0], quantiles={"p50": 9.0, "p95": 40.0, "p99": 95.0})]
    monkeypatch.setattr(StubGraphQL, "rows", rows)
    result = run_step(stub)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "exceeds the" in result.stdout and "ceiling" in result.stdout, result.stdout


def test_the_window_is_iso8601_not_a_relative_string(stub):
    """`datetime_geq: "-24h"` was the first of the three approved-by-mistake failures (#2135)."""
    run_step(stub)
    assert not any('"-24h"' in q or "'-24h'" in q for q in StubGraphQL.seen), StubGraphQL.seen
