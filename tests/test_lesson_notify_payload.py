#!/usr/bin/env python3
"""A lesson notification must not be dropped silently, and a dropped one must be visible.

`lesson-notify.yml` posts a Feishu card whose `msg_type` is `interactive`. The payload was
assembled by interpolating the issue's title and body into a JSON heredoc, and sent with
`curl -s` — no `--fail`. Both halves have to be true for a notification to be lost without a
trace, and both were:

* an issue title is attacker-chosen text, and a double quote or a backslash in it produces
  JSON that Feishu rejects with 400;
* `curl -s` without `--fail` exits 0 on a 4xx, so the 400 was invisible — the step went green
  and the card was never delivered.

Measured against a stub receiver that parses the body the way Feishu does:

    title                       receiver            as committed      with --fail
    docs: add a lesson          ACCEPTED (350 B)    exit 0, green      exit 0, green
    fix: handle "quoted" input  REJECTED           exit 0, GREEN      exit 22, red
    docs: add a backslash       REJECTED           exit 0, GREEN      exit 22, red

`jq -n --arg` fixes the payload and `--fail` fixes the silence; either alone leaves the other
half standing, so the tests below pin both. The step runs inside `.github/actions/retry/`, which
is covered by `tests/test_retry_action.py` — this file is about the payload and the exit code.

`jq` is preinstalled on the `ubuntu-latest` runner this workflow uses, and is already a dependency
of `adopt-pr.yml:86` and `fix-dco.yml:34`. Where it is absent the execution tests **skip loudly**
rather than pass: an empty payload plus `--fail` exits 22, so a missing `jq` cannot quietly turn
these green, but it must not be reported as coverage either.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from pathlib import Path

import pytest

from posix_shell import require_posix_shell

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "lesson-notify.yml"

#: The two execution tests below need `jq` to build the payload. The text assertions do not.
needs_jq = pytest.mark.skipif(
    shutil.which("jq") is None,
    reason="jq is not on PATH here, so the step's payload cannot be built or read; "
           "the text assertions in this file still run",
)

#: A title no one would think twice of, and the two that break string interpolation.
PLAIN_TITLE = "docs: add a lesson"
QUOTED_TITLE = 'fix: handle "quoted" input'
BACKSLASH_TITLE = r"docs: add \ lesson"


def notify_script() -> str:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in document["jobs"].values():
        for step in job.get("steps", []):
            if "retry" in str(step.get("uses", "")):
                return step["with"]["run"]
    raise AssertionError("the notify step disappeared from lesson-notify.yml")


class _StubFeishu:
    """A receiver that accepts exactly the JSON Feishu would accept, and records the verdicts."""

    def __init__(self):
        self.bodies: list[bytes] = []
        handler = self._make_handler()
        self._server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _make_handler(self):
        bodies = self.bodies

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):                       # noqa: N802 — BaseHTTPRequestHandler API
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                bodies.append(body)
                try:
                    json.loads(body)
                    code = 200
                except ValueError:
                    code = 400
                self.send_response(code)
                self.end_headers()

            def log_message(self, *args):
                pass
        return Handler

    def close(self):
        self._server.shutdown()
        self._server.server_close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def post(title: str, body: str = "a body line") -> tuple[int, list[bytes]]:
    """Run the real notify step against the stub, once, with no retry delay.

    The shell comes from `require_posix_shell()` rather than a literal `bash`: on `windows-latest`
    `bash` on PATH is the WSL launcher and dies with *"Windows Subsystem for Linux has no
    installed distributions"*, which is a fact about the runner and not a test result.
    `scripts/posix_shell.py` has the full account — these four tests were the red legs it
    describes, a second time.
    """
    shell = require_posix_shell()
    with tempfile.TemporaryDirectory() as tmp:
        step = Path(tmp) / "notify.sh"
        step.write_text(notify_script(), encoding="utf-8")
        proc = subprocess.run(
            [shell, str(step)], capture_output=True, text=True, timeout=120, cwd=tmp,
            env={
                **os.environ,
                "GITHUB_WORKSPACE": tmp,
                "WEBHOOK": f"http://127.0.0.1:{_CURRENT_STUB[0].port}/hook",
                "TITLE": title,
                "USER": "someone",
                "URL": "https://example.invalid/1",
                "BODY": body,
            },
        )
    return proc.returncode, _CURRENT_STUB[0].bodies


#: The stub the helpers above reach for. Set by the fixture so the helper signature can stay short.
_CURRENT_STUB: list[_StubFeishu] = []


@pytest.fixture
def stub():
    with _StubFeishu() as server:
        _CURRENT_STUB.append(server)
        try:
            yield server
        finally:
            _CURRENT_STUB.pop()


# ── The payload has to survive the title it is given ───────────────────────────────────────────────

@needs_jq
def test_a_title_containing_a_double_quote_still_produces_valid_json(stub):
    code, bodies = post(QUOTED_TITLE)
    assert bodies, "the stub received nothing — the step never posted"
    try:
        payload = json.loads(bodies[0])
    except ValueError as exc:
        pytest.fail(f"the card is not valid JSON ({exc}); raw: {bodies[0][:240]!r}")
    content = payload["card"]["elements"][0]["content"]
    assert QUOTED_TITLE in content, f"the title did not survive into the card: {content!r}"
    assert code == 0, f"{code}\n{content!r}"


@needs_jq
def test_a_title_containing_a_backslash_still_produces_valid_json(stub):
    code, bodies = post(BACKSLASH_TITLE)
    assert bodies, "the stub received nothing — the step never posted"
    try:
        payload = json.loads(bodies[0])
    except ValueError as exc:
        pytest.fail(f"the card is not valid JSON ({exc}); raw: {bodies[0][:240]!r}")
    assert BACKSLASH_TITLE in payload["card"]["elements"][0]["content"]


@needs_jq
def test_the_plain_title_still_works(stub):
    """The regression guard for the regression guard: `jq` must not have changed the happy path."""
    code, bodies = post(PLAIN_TITLE)
    assert code == 0
    payload = json.loads(bodies[0])
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "📘 新 Lesson 贡献"
    content = payload["card"]["elements"][0]["content"]
    for expected in ("someone", PLAIN_TITLE, "https://example.invalid/1", "a body line"):
        assert expected in content, f"{expected!r} missing from the card: {content!r}"


@needs_jq
def test_a_multi_line_body_is_summarised_into_one_line(stub):
    code, bodies = post(PLAIN_TITLE, body="one\ntwo\nthree\nfour\nfive\nsix")
    assert code == 0
    content = json.loads(bodies[0])["card"]["elements"][0]["content"]
    summary = content.split("**摘要：** ")[1].split("\n")[0]
    assert "one" in summary and "five" in summary, summary
    assert "six" not in summary, f"the summary is meant to be the first 5 lines: {summary!r}"


# ── A rejection has to be visible ──────────────────────────────────────────────────────────────────

def test_the_step_uses_curl_fail():
    """A 4xx from the webhook must reach the caller, or the loss is silent.

    Asserted on the text because there is no way to make the real Feishu endpoint return 400 from a
    test; `test_a_rejected_payload_would_be_visible` shows what that flag is worth.
    """
    script = notify_script()
    assert "--fail" in script, (
        "`curl` without `--fail` exits 0 on a 4xx, so a card Feishu rejected is indistinguishable "
        "from one it accepted. This is the half that turns a lost notification into a lost "
        "notification nobody hears about.")


def test_a_rejected_payload_would_be_visible(tmp_path):
    """The other half, demonstrated rather than asserted: point the step at a receiver that always
    answers 400, and `curl --fail` must turn that into a non-zero exit.

    Uses a script with the step's own `curl` line rather than the whole step, so the receiver can
    be made to fail on demand without a second workflow shape.
    """
    shell = require_posix_shell()
    curl_line = next(line for line in notify_script().splitlines() if "curl" in line and "POST" in line)
    assert "--fail" in curl_line, "the curl line lost --fail"

    class Always400(http.server.BaseHTTPRequestHandler):
        def do_POST(self):                            # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(400)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Always400)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        script = curl_line.replace("$WEBHOOK", f"http://127.0.0.1:{server.server_address[1]}/hook")
        script += '\n-d \'{}\'\n'
        target = tmp_path / "only-curl.sh"
        target.write_text(script, encoding="utf-8")
        proc = subprocess.run([shell, str(target)], capture_output=True, text=True,
                              env={**os.environ,
                                   "WEBHOOK": f"http://127.0.0.1:{server.server_address[1]}/hook"},
                              timeout=60)
    finally:
        server.shutdown()
        server.server_close()
    assert proc.returncode != 0, (
        "the webhook answered 400 and the step still exited 0 — that is the silent loss this "
        "file exists to rule out")


# ── The shape of the payload ────────────────────────────────────────────────────────────────────────

def test_the_payload_is_built_by_jq_and_not_by_interpolating_into_a_heredoc():
    """A heredoc means the caller's text is spliced into JSON syntax.

    The value is passed with `--arg` instead, so it is data at every point. This is the structural
    statement of what `test_a_title_containing_a_double_quote_still_produces_valid_json` measures
    for one input.
    """
    script = notify_script()
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
    assert "<<PAYLOAD" not in code, (
        "the payload is a heredoc again: an issue title carrying `\"` or `\\` ends up inside the "
        "JSON syntax rather than inside a string")
    assert "jq -n" in code and "--arg title" in code, (
        "the payload is not built with `jq -n --arg`, so a title is not escaped as data")
