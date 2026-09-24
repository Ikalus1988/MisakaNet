#!/usr/bin/env python3
"""The status-code query has cost three human approvals to guesswork, so it is now tested.

`cf-diagnostics.yml` is `workflow_dispatch`-only and sits behind the `release` environment's required
reviewer: every mistake in it costs a person a click, and the mistakes are all the same shape —
a GraphQL field name I believed existed.

Measured 2026-09-24, in order:

1. `filter: {datetime_geq: "-24h"}` → `error parsing args: datetime_geq: not an iso8601 time`;
2. `dimensions { edgeResponseTime … }` → `unknown field "edgeResponseTime"` (#2135);
3. `dimensions { clientRequestHost … }` → `unknown field "clientRequestHost"` — and because the step
   printed the error and exited 0, run 4 reported **success** while printing an empty table.

Three strikes is a design problem, not bad luck: the query asserted a schema instead of asking for it.
The step now introspects the schema, uses the name it finds (falling back to a short candidate list,
and then to no host dimension at all), and **fails the step** on GraphQL validation errors while still
treating a 403 as a finding.

This file runs that exact script — extracted from the YAML, not copied — against a stub GraphQL
endpoint, and covers the case that matters: the stub's schema calls the host dimension something the
workflow does not hardcode.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "cf-diagnostics.yml"

STEP_NAME = "HTTP status codes by route"


def step_script() -> str:
    """The `run:` body of the status-code step, exactly as CI executes it."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["diagnose"]["steps"]:
        if (step.get("name") or "").startswith(STEP_NAME):
            return step["run"]
    raise AssertionError(f"no step named {STEP_NAME!r} in {WORKFLOW.name} — rename the pin with it")


def python_block(script: str) -> str:
    match = re.search(r"python3 - <<'PY'\n(.*?)\nPY\n", script, re.S)
    assert match, "the step no longer runs a python heredoc; fix this test with the step"
    return match.group(1)


class StubGraphQL(BaseHTTPRequestHandler):
    """Answers introspection, then data — and only for the field name its schema declares."""

    types = ["AccountHttpRequestsAdaptiveGroupsDimensions", "ZoneHttpRequestsAdaptiveGroups"]
    fields = ["clientRequestHTTPHost", "clientRequestPath", "edgeResponseStatus", "datetime"]
    seen: list[str] = []

    def log_message(self, *args):  # keep pytest output clean
        pass

    def do_POST(self):  # noqa: N802 (http.server naming)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        query = body.get("query", "")
        type(self).seen.append(query)

        if "__schema" in query:
            payload = {"data": {"__schema": {"types": [{"name": n} for n in self.types]}}}
        elif "__type" in query:
            payload = {"data": {"__type": {"fields": [{"name": n} for n in self.fields]}}}
        else:
            # The data query: it must ask for the field this schema actually declares.
            asked = re.search(r"dimensions\s*\{([^}]*)\}", query)
            names = (asked.group(1).split() if asked else [])
            unknown = [n for n in names if n not in self.fields]
            if unknown:
                payload = {"errors": [{"message": f'unknown field "{unknown[0]}"'}]}
            else:
                host = next((n for n in names if "host" in n.lower()), None)
                rows = [
                    {"count": 12, "dimensions": {"edgeResponseStatus": 522, "clientRequestPath": "/ping",
                                                 **({host: "misakanet.org"} if host else {})}},
                    {"count": 900, "dimensions": {"edgeResponseStatus": 200, "clientRequestPath": "/mcp",
                                                  **({host: "misakanet.org"} if host else {})}},
                ]
                payload = {"data": {"viewer": {"accounts": [{"httpRequestsAdaptiveGroups": rows}]}}}

        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture()
def stub():
    """A live stub GraphQL server, and the env the step needs to talk to it."""
    StubGraphQL.seen = []
    server = HTTPServer(("127.0.0.1", 0), StubGraphQL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/graphql"
    finally:
        server.shutdown()
        server.server_close()


def run_step(endpoint: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Execute the step's python exactly as the workflow does (bash -e, env from the job)."""
    script = REPO / ".github" / "workflows" / "cf-diagnostics.yml"
    py = python_block(step_script())
    proc = subprocess.run(
        [sys.executable, "-c", py],
        capture_output=True, text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "CLOUDFLARE_ACCOUNT_ID": "6b92325b505f2b76aec49e9fe4195d31",
            "CLOUDFLARE_API_TOKEN": "stub-token",
            "CF_GRAPHQL_URL": endpoint,
            "HOURS": "24",
            **(env_extra or {}),
        },
    )
    assert script.exists()
    return proc


def test_the_query_uses_the_host_dimension_the_schema_declares(stub):
    """The whole point: the field name comes from the schema, not from this repository."""
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "using host dimension: clientRequestHTTPHost" in proc.stdout, proc.stdout
    # …and the data query really asked for it, rather than printing a table from a fallback.
    assert any("clientRequestHTTPHost" in q and "__schema" not in q for q in StubGraphQL.seen), \
        StubGraphQL.seen
    # The table itself: totals by status, the 5xx route, and the host breakdown.
    assert "522: 12" in proc.stdout and "200: 900" in proc.stdout, proc.stdout
    assert "522 12 path=/ping host=misakanet.org" in proc.stdout, proc.stdout
    assert "misakanet.org: 12" in proc.stdout, proc.stdout


def test_a_different_schema_name_is_discovered_too(stub, monkeypatch):
    """Guard-the-guard: rename the field in the stub and the workflow must follow it.

    A hardcoded `clientRequestHTTPHost` would pass the test above by accident — this one cannot be
    passed without actually reading the schema.
    """
    monkeypatch.setattr(StubGraphQL, "fields",
                        ["clientRequestHTTPHostname", "clientRequestPath", "edgeResponseStatus"])
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "using host dimension: clientRequestHTTPHostname" in proc.stdout, proc.stdout
    assert any("clientRequestHTTPHostname" in q for q in StubGraphQL.seen), StubGraphQL.seen


def test_a_schema_with_no_host_dimension_still_reports_status_by_path(stub, monkeypatch):
    monkeypatch.setattr(StubGraphQL, "fields", ["clientRequestPath", "edgeResponseStatus"])
    monkeypatch.setattr(StubGraphQL, "types", [])
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no host dimension available" in proc.stdout, proc.stdout
    assert "522: 12" in proc.stdout, proc.stdout


def test_a_validation_error_fails_the_step(stub, monkeypatch):
    """The failure mode that hid this for three runs: a broken query that reports success.

    Run 4 concluded `success` while printing an empty table, because the step caught every GraphQL
    error and exited 0 — and the same shape produced the two earlier failures (`edgeResponseTime`,
    then `clientRequestHost`): a field this repository believes exists and the schema does not have.
    Here the schema lacks `clientRequestPath`, which the step does hardcode, so the data query is
    invalid and the step must go red rather than print an empty table.

    Note what the discovery *does* absorb: an unknown **host** dimension is survivable — the
    candidate list fails, the step groups by path alone and says so. A validation error can only
    come from a field that is not discovered at all.
    """
    monkeypatch.setattr(StubGraphQL, "types", [])
    monkeypatch.setattr(StubGraphQL, "fields", ["edgeResponseStatus"])
    proc = run_step(stub)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "::error::the GraphQL query is invalid" in proc.stdout, proc.stdout
    assert "unknown field" in proc.stdout, proc.stdout


def test_a_missing_permission_warns_but_does_not_stop_the_run(stub, monkeypatch):
    """A 403 is a finding about the token, not a bug in the step: the other steps must still run."""
    class Unauthorized(StubGraphQL):
        def do_POST(self):  # noqa: N802
            raw = json.dumps({"success": False, "errors": [{"code": 10000,
                                                             "message": "Authentication error"}]}).encode()
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = HTTPServer(("127.0.0.1", 0), Unauthorized)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        proc = run_step(f"http://127.0.0.1:{server.server_port}/graphql")
    finally:
        server.shutdown()
        server.server_close()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "::warning::graphql query failed" in proc.stdout, proc.stdout
