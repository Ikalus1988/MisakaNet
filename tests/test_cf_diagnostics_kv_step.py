#!/usr/bin/env python3
"""The zone inventory must attribute a KV namespace to whoever binds it, not to this repository.

The first version printed, for any namespace this repository does not bind:

    ⚠ unbound … — nothing in this repository binds it; confirm it is empty before deleting it

That advice was wrong about a namespace that belongs to the owner's self-hosted VPN (an edgetunnel
worker in the same Cloudflare account), and it is the kind of wrong that destroys data — a reader who
follows it deletes a running service's storage. The step now reads the deployed workers' own bindings
and says *who* uses the namespace, falling back to "unused" only when no worker claims it at all.

This runs the step's own Python (extracted from the workflow, not copied) against a stub Cloudflare
API, with the three cases that matter: a namespace this repository binds, one another worker binds,
and one nobody binds.
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
STEP_NAME = "Zone inventory"

MISAKANET_KV = "d5fb6b0797b84d17b0586fb982231ffe"   # workers/wrangler.toml
VPN_KV = "5267c932cef24d8e9b40e1c736c18f66"         # the owner's edgetunnel VPN worker
NOBODY_KV = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

ZONE = "zone-under-test"
ACCOUNT = "6b92325b505f2b76aec49e9fe4195d31"


def step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["diagnose"]["steps"]:
        if (step.get("name") or "").startswith(STEP_NAME):
            return step["run"]
    raise AssertionError(f"no step named {STEP_NAME!r} — rename this pin with it")


def python_block(script: str) -> str:
    opener = "python3 - <<'PY'\n"
    start = script.find(opener)
    assert start != -1, "the step no longer runs a python heredoc"
    body_start = start + len(opener)
    end = script.find("\nPY\n", body_start)
    assert end != -1, "the heredoc is never closed"
    return script[body_start:end]


class StubAccount(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, payload: dict) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/zones":
            return self._json({"result": [{"id": ZONE}]})
        if path == f"/zones/{ZONE}/workers/routes":
            return self._json({"result": [
                {"pattern": "misakanet.org/api/*", "script": "misakanet-register-proxy"},
                {"pattern": "misakanet.org/journey/*", "script": "misakanet-web"},
            ]})
        if path == f"/accounts/{ACCOUNT}/storage/kv/namespaces":
            return self._json({"result": [
                {"id": MISAKANET_KV, "title": "MISAKANET_KV"},
                {"id": VPN_KV, "title": "KV"},
                {"id": NOBODY_KV, "title": "leftover"},
            ]})
        if path == f"/accounts/{ACCOUNT}/workers/scripts":
            return self._json({"result": [{"id": "misakanet-register-proxy"}, {"id": "edgetunnel-vpn"}]})
        if path.endswith("/misakanet-register-proxy/settings"):
            return self._json({"result": {"bindings": [
                {"type": "kv_namespace", "name": "MISAKANET_KV", "namespace_id": MISAKANET_KV},
                {"type": "d1", "name": "MISAKANET_D1"},
            ]}})
        if path.endswith("/edgetunnel-vpn/settings"):
            return self._json({"result": {"bindings": [
                {"type": "kv_namespace", "name": "KV", "namespace_id": VPN_KV},
            ]}})
        self._json({"result": []})


@pytest.fixture(scope="module")
def probe():
    def run(base: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-c", python_block(step_script())],
            capture_output=True, text=True,
            env={
                "PATH": "/usr/bin:/bin",
                "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
                "CLOUDFLARE_API_TOKEN": "stub-token",
                "CF_API_BASE": base,
            },
        )
    return run


@pytest.fixture()
def stub(probe):
    server = HTTPServer(("127.0.0.1", 0), StubAccount)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        # `base` is concatenated with paths that already start with `/`, so no trailing slash.
        yield probe(f"http://127.0.0.1:{server.server_port}")
    finally:
        server.shutdown()
        server.server_close()


def namespace_lines(output: str) -> dict[str, str]:
    """namespace id -> the line the step printed for it."""
    lines = {}
    for line in output.splitlines():
        for nsid in (MISAKANET_KV, VPN_KV, NOBODY_KV):
            if nsid in line:
                lines[nsid] = line
    return lines


def test_a_namespace_another_worker_binds_is_not_offered_for_deletion(stub):
    """The correction: the VPN worker's namespace belongs to a service, and the step must say so."""
    assert stub.returncode == 0, stub.stdout + stub.stderr
    lines = namespace_lines(stub.stdout)
    assert VPN_KV in lines, stub.stdout
    vpn_line = lines[VPN_KV]
    assert "edgetunnel-vpn" in vpn_line, vpn_line
    assert "Leave it alone" in vpn_line, vpn_line
    # The exact wording that would have had a reader delete a running service's storage.
    assert "confirm it is empty before deleting it" not in vpn_line, vpn_line


def test_the_repositorys_own_namespace_says_it_is_bound_by_the_repository(stub):
    lines = namespace_lines(stub.stdout)
    assert "bound by this repository" in lines[MISAKANET_KV], lines[MISAKANET_KV]
    assert "wrangler.toml" in lines[MISAKANET_KV], lines[MISAKANET_KV]


def test_a_namespace_nobody_binds_is_reported_as_unattributed(stub):
    """The weaker claim is still available — but only when no deployed worker claims it."""
    lines = namespace_lines(stub.stdout)
    line = lines[NOBODY_KV]
    assert "no deployed worker binds it" in line, line
    assert "Leave it alone" not in line, line


def test_the_routes_are_still_reported(stub):
    """The step does two jobs; the KV rewrite must not have removed the first one."""
    assert "misakanet.org/api/*" in stub.stdout
    assert "misakanet-register-proxy" in stub.stdout


def test_the_step_asks_the_workers_for_their_bindings():
    """The mechanism, pinned at the source: attribution comes from the API, not from a hardcoded list."""
    block = python_block(step_script())
    assert "/workers/scripts?per_page=" in block, "the step no longer lists deployed workers"
    assert "/settings" in block, "the step no longer reads per-worker bindings"
    assert "kv_namespace" in block, "the step no longer looks at kv_namespace bindings"
