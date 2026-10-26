#!/usr/bin/env python3
"""The hook redacts the query before it leaves the machine (issue #3692).

The trial user's own words: "报错片段会作为查询关键词发到该服务器——这意味着内部表名、路径等可能随查询外发
(有脱敏规则但是概率性的，靠 agent 执行不是确定性过滤)". So the redaction moved out of the rules text
— where it was a *request to the model* — and into the hook, where it is code.

What is pinned here:

* every rule class replaces its own secret, in **both** implementations (the npm package ships
  the Node hook, the Python installers ship the Python one);
* the ordinary text of an error message survives unchanged: the corpus is indexed by error
  text, so over-redaction costs search quality for a leak that is not in scope;
* the redaction happens **before** the fragment is printed into the agent's context, because
  the agent may copy that text into its own `misakanet_search` call — redacting only at the
  network call would leave the raw text in the agent's reach;
* with the hook's networking off (the default) nothing goes out at all.

The hooks are driven as subprocesses, exactly as an agent runs them: JSON on stdin, text to
inject on stdout. The file paths are resolved relative to this file — never imported from the
installed package, whose editable install points at another checkout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
AUTOSTART = REPO / "integrations" / "agent-autostart"
PY_HOOK = AUTOSTART / "checkpoint_reminder.py"
MJS_HOOK = AUTOSTART / "checkpoint_reminder.mjs"

HOOKS = {
    "node": ["node", str(MJS_HOOK)],
    "python": [sys.executable, str(PY_HOOK)],
}

# The three secrets the issue names, in one string: a path, an address and a token.
THE_ISSUE_SAMPLE = (
    "Traceback (most recent call last): File /home/alice/project/secret.py, line 42 — "
    "reporter alice@corp.com sent header Bearer abc123"
)

# One case per rule class: the secret, and the placeholder that must replace it.
RULE_CASES = [
    ("abs_path", "/home/alice/project/secret.py", "<PATH>"),
    ("windows_path", r"C:\Users\alice\project\secret.py", "<PATH>"),
    ("email", "alice@corp.com", "<REDACTED:email>"),
    ("bearer_token", "Bearer abc123", "[REDACTED:bearer_token]"),
    ("api_key", "sk-abcdefghijklmnop", "[REDACTED:api_key]"),
    ("github_token", "ghp_abcdefghijklmnop", "[REDACTED:github_token]"),
]

# A path is redacted when it looks like a *filesystem* path: it starts at a known root,
# or its last segment carries a file extension. The second column says which shape it is.
PATHS_TO_REDACT = [
    ("/home/alice/project/secret.py", "a home directory"),
    ("/opt/app/config.yaml", "a known root"),
    ("/srv/x/server.py", "a known root"),
    ("/data/db.sqlite locked", "a known root"),
    ("C:\\Users\\alice\\project\\secret.py", "a Windows path"),
]

# Paths that are NOT filesystem paths: they are API routes, and the corpus is full of
# them. Swallowing one destroys the lesson it belongs to.
PATHS_TO_KEEP = [
    "/api/v1/users",
    "/v1/sessions",
    "/oauth/token",
]

# Error text that must come through untouched. Every entry is something a real build, a
# real lesson or a real user produces; mangling any of them would cost the corpus its
# search quality.
ORDINARY_TEXT = [
    "ModuleNotFoundError: No module named 'requests'",
    "EADDRINUSE: address already in use :::3000",
    "docker compose up failed with exit code 137",
    "the task_identifier field is wrong",
    "see https://example.com/docs/api for the full list",
    "连接被拒绝，请检查服务是否已经启动。",
    "安装依赖失败：找不到 requirements.txt，请重试。",
]


def run_hook(hook: str, payload, *, mode: str = "failure", tmp_path: Path,
             env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Run one hook the way an agent runs it: JSON on stdin, text to inject on stdout."""
    env = {
        **os.environ,
        "MISAKANET_HOOK_STATE": str(tmp_path / f"state-{hook}"),
        "MISAKANET_AGENT_DIR": str(tmp_path / f"agent-{hook}"),
        "MISAKANET_HOOK_FETCH": "0",      # the default: advice only, no network
        # A proxy in the environment would send the local stub request somewhere else.
        "no_proxy": "127.0.0.1,localhost",
        "NO_PROXY": "127.0.0.1,localhost",
    }
    for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env.pop(name, None)
    env.update(env_extra or {})
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([*HOOKS[hook], mode], input=raw, capture_output=True, text=True,
                          env=env, timeout=60)


@contextmanager
def endpoint_recorder():
    """A local endpoint that records every request body it receives.

    The point is not the response — it is that "nothing went out" becomes an observable
    fact instead of an assumption about the code path.
    """
    bodies: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            bodies.append(self.rfile.read(length).decode("utf-8", "replace"))
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
                "structuredContent": {"results": []}}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/mcp", bodies
    finally:
        server.shutdown()
        server.server_close()


# How many times a hook may be asked to fetch before the test calls it broken.
FETCH_ATTEMPTS = 3


def run_until_a_request_leaves(hook: str, payload, *, tmp_path: Path,
                               env_extra: dict | None = None):
    """Run the hook until a request actually reaches the endpoint.

    Why this is not just "run it once": the hook's network call is bounded by a **four-second
    stall guard** — the product's rule, "a hook must never stall a session". On a loaded Windows
    runner the *first* fetch in a fresh Node process can spend seconds loading the HTTP client,
    and that load happens *inside* the guard. The hook then does exactly the right thing (it gives
    up instead of stalling) and the request never leaves. Measured 2026-10-22 on
    `windows-latest, 3.12`: the Node variant took **7.13s** and failed, while the Python twin,
    running **0.76s** later against the same server, passed in under a second. The same test
    passed on all three Windows legs of PR #3707's run — so this is the cold-start case, not a
    broken fetch path.

    So the test tells the two apart instead of racing the clock: the hook says on stderr
    (`MISAKANET_HOOK_DEBUG=1`) that it *tried and gave up* — "search failed: ..." — and only that
    case may be retried. A run that produced no request **and no attempt** is a broken fetch path
    and goes red at once.

    The assertion this protects keeps its full strength: if the opt-in fetch never reaches the
    network, no attempt produces a request and the test fails.
    """
    result = None
    bodies: list[str] = []
    for _attempt in range(FETCH_ATTEMPTS):
        with endpoint_recorder() as (url, recorded):
            result = run_hook(hook, payload, tmp_path=tmp_path,
                              env_extra={**env_extra, "MISAKANET_ENDPOINT": url,
                                         "MISAKANET_HOOK_DEBUG": "1"})
        assert result.returncode == 0, (
            f"the hook must never break a session: {result.stderr[-400:]}")
        bodies = recorded
        if bodies:
            break
        if "search failed" not in result.stderr:
            break       # the hook never tried to fetch: broken, not slow
    return result, bodies


@pytest.mark.parametrize("hook", sorted(HOOKS))
@pytest.mark.parametrize("rule_id, secret, placeholder", RULE_CASES, ids=[c[0] for c in RULE_CASES])
def test_each_rule_class_replaces_its_own_secret(hook, rule_id, secret, placeholder, tmp_path):
    result = run_hook(hook, {"error": f"boom: {secret} happened"}, tmp_path=tmp_path)
    assert result.returncode == 0, f"the hook must never break a session: {result.stderr[-400:]}"
    assert secret not in result.stdout, (
        f"{rule_id}: the secret is still in the query the agent is told to search with:\n{result.stdout}"
    )
    assert placeholder in result.stdout, (
        f"{rule_id}: the query must carry the placeholder instead:\n{result.stdout}"
    )


@pytest.mark.parametrize("hook", sorted(HOOKS))
def test_the_three_secrets_of_the_issue_are_gone_before_the_agent_sees_them(hook, tmp_path):
    result = run_hook(hook, {"error": THE_ISSUE_SAMPLE}, tmp_path=tmp_path)
    assert result.returncode == 0
    for secret in ("/home/alice/project/secret.py", "alice@corp.com", "abc123"):
        assert secret not in result.stdout, (
            f"{secret!r} reached the agent's context — the redaction must happen before the "
            f"fragment is printed, not only before it is sent:\n{result.stdout}"
        )
    for placeholder in ("<PATH>", "<REDACTED:email>", "[REDACTED:bearer_token]"):
        assert placeholder in result.stdout, f"missing {placeholder}:\n{result.stdout}"


@pytest.mark.parametrize("hook", sorted(HOOKS))
@pytest.mark.parametrize("text", ORDINARY_TEXT)
def test_ordinary_error_text_is_not_damaged(hook, text, tmp_path):
    """The other half of the trade: a redaction that eats prose is not a redaction.

    The corpus is indexed by error text, so a rule that mangles ordinary text costs the
    search quality it was supposed to protect.
    """
    result = run_hook(hook, {"error": text}, tmp_path=tmp_path)
    assert result.returncode == 0
    assert text in result.stdout, (
        f"ordinary text was mangled:\n  in : {text}\n  out: {result.stdout}"
    )


@pytest.mark.parametrize("hook", sorted(HOOKS))
@pytest.mark.parametrize("path, shape", PATHS_TO_REDACT, ids=[p[1] for p in PATHS_TO_REDACT])
def test_a_filesystem_path_is_redacted(hook, path, shape, tmp_path):
    result = run_hook(hook, {"error": f"cannot open {path}"}, tmp_path=tmp_path)
    assert result.returncode == 0
    assert path not in result.stdout, f"{shape} was not redacted:\n{result.stdout}"
    assert "<PATH>" in result.stdout, f"{shape} was not redacted:\n{result.stdout}"


@pytest.mark.parametrize("hook", sorted(HOOKS))
@pytest.mark.parametrize("route", PATHS_TO_KEEP)
def test_an_api_route_is_not_a_path(hook, route, tmp_path):
    """/api/v1/users is a route in a lesson, not a file on this machine.

    The intake path turns the redacted text into a public GitHub issue, so a rule that
    eats the route destroys the maintainer's ability to triage the report.
    """
    result = run_hook(hook, {"error": f"GET {route} returned 404"}, tmp_path=tmp_path)
    assert result.returncode == 0
    assert route in result.stdout, (
        f"an API route was swallowed:\n  in : {route}\n  out: {result.stdout}"
    )


@pytest.mark.parametrize("hook", sorted(HOOKS))
@pytest.mark.parametrize("spec", ["foo@1.2.3", "pkg@0.5.6", "npm install foo@1.2.3 failed"])
def test_a_version_spec_is_not_an_address(hook, spec, tmp_path):
    """foo@1.2.3 is an npm version spec, and eating it destroys the version.

    The top-level domain of a real address is alphabetic; a version spec's is a number.
    """
    result = run_hook(hook, {"error": spec}, tmp_path=tmp_path)
    assert result.returncode == 0
    assert spec in result.stdout, (
        f"a version spec was swallowed:\n  in : {spec}\n  out: {result.stdout}"
    )


@pytest.mark.parametrize("hook", sorted(HOOKS))
def test_with_the_networking_off_nothing_leaves_the_machine(hook, tmp_path):
    """The regression the issue is really about: the default hook sends nothing at all."""
    with endpoint_recorder() as (url, bodies):
        result = run_hook(hook, {"error": THE_ISSUE_SAMPLE}, tmp_path=tmp_path,
                          env_extra={"MISAKANET_ENDPOINT": url})
    assert result.returncode == 0
    assert bodies == [], (
        f"the hook reached the endpoint although MISAKANET_HOOK_FETCH is off: {bodies!r}"
    )
    # ... and it still did its job locally.
    assert "<PATH>" in result.stdout, result.stdout


@pytest.mark.parametrize("hook", sorted(HOOKS))
def test_the_query_that_leaves_the_machine_is_redacted(hook, tmp_path):
    """With the opt-in fetch on, what goes over the wire must be the redacted query."""
    result, bodies = run_until_a_request_leaves(
        hook, {"error": THE_ISSUE_SAMPLE}, tmp_path=tmp_path,
        env_extra={"MISAKANET_HOOK_FETCH": "1"})
    assert bodies, (
        "the fetch must have happened (MISAKANET_HOOK_FETCH=1); the hook said:\n"
        + (result.stderr[-600:] or "(nothing on stderr)")
    )
    sent = bodies[-1]
    for secret in ("/home/alice/project/secret.py", "alice@corp.com", "abc123"):
        assert secret not in sent, f"{secret!r} was sent to the server:\n{sent}"
    assert "<PATH>" in sent, f"the query that left the machine was not redacted:\n{sent}"


def _import_python_hook():
    """Import the twin so its `_mcp_search` can be driven with raw text (#3719)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("checkpoint_reminder_py", PY_HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_python_inner_gate_redacts_raw_text():
    """The inner gate is load-bearing even when the outer one never ran (#3719).

    The fragment printed into the agent's context is already redacted, so the old test could not
    tell "the inner gate redacted" from "the outer one did". Call `_mcp_search` with the raw text:
    removing its `_redact(query)` makes the secret appear in the recorded body.
    """
    module = _import_python_hook()
    with endpoint_recorder() as (url, bodies):
        old = os.environ.get("MISAKANET_ENDPOINT")
        os.environ["MISAKANET_ENDPOINT"] = url
        try:
            module._mcp_search(THE_ISSUE_SAMPLE)
        finally:
            if old is None:
                os.environ.pop("MISAKANET_ENDPOINT", None)
            else:
                os.environ["MISAKANET_ENDPOINT"] = old
    assert bodies, "the inner gate did not send a request"
    sent = bodies[-1]
    for secret in ("/home/alice/project/secret.py", "alice@corp.com", "abc123"):
        assert secret not in sent, f"{secret!r} left through the inner gate:\n{sent}"
    assert "<PATH>" in sent, f"the inner gate did not redact the raw text:\n{sent}"


def test_the_node_inner_gate_redacts_raw_text():
    """Same for the Node twin: import `search`, not the whole hook."""
    script = (
        f"import {{ search }} from {json.dumps(MJS_HOOK.as_uri())};"
        "await search(process.env.THE_RAW_TEXT);"
    )
    with endpoint_recorder() as (url, bodies):
        env = {**os.environ, "MISAKANET_ENDPOINT": url, "THE_RAW_TEXT": THE_ISSUE_SAMPLE}
        proc = subprocess.run(["node", "--input-type=module", "-e", script],
                              capture_output=True, text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr[-400:]
    assert bodies, "the inner gate did not send a request"
    sent = bodies[-1]
    for secret in ("/home/alice/project/secret.py", "alice@corp.com", "abc123"):
        assert secret not in sent, f"{secret!r} left through the inner gate:\n{sent}"
    assert "<PATH>" in sent, f"the inner gate did not redact the raw text:\n{sent}"


@pytest.mark.parametrize("hook", sorted(HOOKS))
@pytest.mark.parametrize("payload", ["", "not json", "[]", '{"error": null}', '{"error": 42}'])
def test_a_redaction_bug_may_not_turn_into_a_failed_hook(hook, payload, tmp_path):
    """The hook's contract is absolute: it never breaks a session, and it exits 0."""
    result = run_hook(hook, payload, tmp_path=tmp_path)
    assert result.returncode == 0, f"the hook failed on {payload!r}: {result.stderr[-400:]}"
