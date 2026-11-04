#!/usr/bin/env python3
"""`scripts/pr_agent_verdict.py` — the classification, not the network.

#2972's residual is that a `failure` conclusion cannot say whether the model answered. The script's
whole value is the mapping from log text to verdict, so that is what is pinned here: the order of the
checks (an error beats a marker in both directions), and one measured sample per verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import pr_agent_verdict as verdict  # noqa: E402


def test_a_model_timeout_is_the_infra_verdict():
    """The shape measured on 2026-11-04 (PR #4402): the job hit the 15-minute ceiling."""
    log = ("2026-11-04T02:20:00Z Reviewing PR #4402\n"
           "2026-11-04T02:26:00Z Failed to review PR: Request timed out\n"
           "The job has exceeded the maximum execution time of 15m0s")
    assert verdict.classify(log) == "model_timeout"


def test_a_missing_secret_is_its_own_verdict():
    """A fork run gets no `OPENAI_KEY`; the red says nothing about the diff (measured 2026-11-03)."""
    log = ("Error: OPENAI_KEY environment variable is not set\n"
           "Incorrect API key provided (401 Unauthorized)")
    assert verdict.classify(log) == "missing_secret"


def test_a_skipped_run_is_not_reviewed():
    log = "PR-Agent Skipping action: synchronize\n"
    assert verdict.classify(log) == "skipped"


def test_a_reviewed_run_is_named_as_such():
    log = "Reviewing PR #4397\nReviewing PR #4397: 3 issues found\n"
    assert verdict.classify(log) == "reviewed"


def test_no_marker_is_unknown_not_clean():
    """Absence of evidence is the verdict that deserves a human, not the one that reads as fine."""
    assert verdict.classify("") == "unknown"
    assert verdict.classify("Build failed: npm ERR! missing script: test") == "unknown"


def test_an_error_beats_a_marker_in_both_directions():
    """A log can say `Reviewing PR` *and* time out — the call started and did not finish."""
    assert verdict.classify("Reviewing PR #1\nAPITimeoutError: Request timed out") == "model_timeout"
    # And a skip that mentions the model in passing is still a skip (never reached the call).
    assert verdict.classify("Skipping action: opened (OPENAI_KEY present)") == "skipped"


def test_the_api_token_does_not_follow_the_redirect_to_the_blob_host():
    """Measured 2026-11-04: the log endpoint redirects to a signed URL that rejects the Bearer token.

    Without this, every verdict is `unknown` — the failure looks like "the log has no marker", which
    is the one verdict that asks a human to read it. A redirect that keeps the header turns a
    classification tool into a log reader that always says "read the log".
    """
    import http.server
    import threading

    seen: list[str] = []

    class Target(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("Authorization", ""))
            body = b"Reviewing PR #1\nReviewing PR #1: ok\n"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class Redirector(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_address[1]}/blob")
            self.end_headers()

        def log_message(self, *args):
            pass

    target = http.server.HTTPServer(("127.0.0.1", 0), Target)
    redirector = http.server.HTTPServer(("127.0.0.1", 0), Redirector)
    threads = [threading.Thread(target=server.serve_forever, daemon=True)
               for server in (target, redirector)]
    for thread in threads:
        thread.start()
    try:
        text = verdict._get(f"http://127.0.0.1:{redirector.server_address[1]}/logs",
                            "secret-token", text=True)
    finally:
        redirector.shutdown()
        target.shutdown()
        redirector.server_close()
        target.server_close()
    assert verdict.classify(text) == "reviewed"
    assert seen == [""], f"the signed URL received the API token: {seen}"
