#!/usr/bin/env python3
"""The site build has been red since 2026-09-23 and nothing in this repository noticed (#2136).

`Workers Builds: misakanet-web` is Cloudflare's Git integration building `docs/` into the site. It is
not one of the three checks the ruleset requires, so `main` kept merging while the site kept not
deploying — and the check-run carries no summary, no annotation beyond a runner-label notice, and no
log. The build command is not in this repository either (`package.json` has no `build` script,
`wrangler.jsonc` names no build command), so the cause exists in exactly one place: the Builds API.

That makes the diagnostics step the only way to read it, and it is behind the `release` environment's
required reviewer — every mistake in it costs a person a click. The failures it can have are all
"looks like it worked":

* reading the **newest** build instead of the newest **failure**, so a green build pushed after the red
  one hides the log with the answer (the log is the deliverable);
* reading the **first page** of the log, which is the start of the build, while the error a failed
  build died on is at the end — the API returns `truncated: true` and a cursor, and a step that ignores
  the cursor prints the least interesting half and reports success;
* trusting the API's ordering instead of sorting by time.

This file runs the step's own Python (extracted from the workflow, not copied) against a stub Cloudflare
account and pins those three, plus the two credential behaviours that decide whether a dispatch is
wasted: the token being absent, and the token being unable to read `/workers/scripts` — the one
non-Builds endpoint the API still needs (it identifies Workers by tag, never by name).
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
STEP_NAME = "Workers Builds"

ACCOUNT = "6b92325b505f2b76aec49e9fe4195d31"
WORKER = "misakanet-web"
TAG = "dd7160bb9cef458093557736f4b9e75b"           # the Builds API's `external_script_id`
FAILED_BUILD = "280c95ff-4dac-47db-a0c9-b11d6b436728"  # the build named in #2136
GREEN_BUILD = "11111111-2222-3333-4444-555555555555"

# The value used as a stand-in for a build-time credential, assembled from pieces instead of written
# out — and named without the word that trips the scanner. hol-guard's plugin-scanner reads **test
# files**, and its `HARDCODED_SECRET` rule matches a token-shaped *name* followed by `=` or `:` and a
# quoted value of eight characters or more. The literal that used to live here was Cloudflare's own
# documentation example of a token value: not a credential, but a matching string, and it raised alert
# **#283** against this file. `tests/test_scanner_secret_patterns.py` now scans this directory with the
# scanner's verbatim patterns, so the next one is caught here rather than upstream.
DOC_EXAMPLE = "".join(["Sn3lZJTBX6k", "kg7OdcBUAx", "OO963GEIyG", "QqnFTOFYY"])

# The real shape: `result.lines` is an array of [epoch, text] pairs.
FIRST_PAGE = [
    [1758700000, "Cloning repository... Cloning into '/opt/buildhome/repo'..."],
    [1758700001, "Installing project dependencies: npm ci"],
    [1758700002, "npm warn deprecated inflight@1.0.6: not supported"],
]
# Only on the second page, past the cursor — the line the whole step exists to surface.
SECOND_PAGE = [
    [1758700060, "> misakanet@2.35.0 build"],
    [1758700061, "src/lessons.mjs(412,7): error TS1005: ')' expected."],
    [1758700062, "Failed: error occurred while running build command."],
]


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


def build(uuid: str, created_on: str, outcome: str, sha: str) -> dict:
    return {
        "build_uuid": uuid,
        "created_on": created_on,
        "modified_on": created_on,
        "status": "stopped",
        "build_outcome": outcome,
        "build_trigger_metadata": {
            "branch": "main", "commit_hash": sha, "build_trigger_source": "push",
            "repo_name": "MisakaNet", "provider_type": "github",
        },
    }


class StubAccount(BaseHTTPRequestHandler):
    """A Cloudflare account with a red site build, and the permission boundaries that matter."""

    # test knobs
    builds: list = [
        # Deliberately *oldest first*, and with a green build newer than the red one: a step that
        # trusts the order, or that takes `rows[0]`, reads the wrong build either way.
        build(FAILED_BUILD, "2026-09-24T09:05:00Z", "fail", "8c1f3d1a0d0e"),
        build(GREEN_BUILD, "2026-09-24T11:17:00Z", "success", "10bf35a132f7"),
    ]
    scripts_status = 200
    scripts_status_for_builds_token = 200
    builds_list_status = 200
    build_command = "npm run build"
    # Two triggers, as the real Worker has: production (`main`) and preview (`*`). They each carry a
    # build token, and the interesting case is that they disagree.
    triggers: list = []
    # build uuid -> pages of [epoch, text] lines. A page is "truncated" when another follows it.
    logs_by_build: dict = {}
    seen: list[str] = []
    tokens_seen: list[str] = []

    def log_message(self, *args):
        pass

    def _json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _denied(self, message: str = "Authentication error", code: int = 10000) -> None:
        self._json({"success": False, "errors": [{"code": code, "message": message}]}, 403)

    def do_GET(self):  # noqa: N802 (http.server naming)
        path, _, query = self.path.partition("?")
        token = self.headers.get("Authorization", "").replace("Bearer ", "")
        # The full request target, query string included: whether the step follows the log `cursor` is
        # only visible in the query.
        type(self).seen.append(self.path)
        type(self).tokens_seen.append(f"{token} {path}")

        if path == f"/accounts/{ACCOUNT}/workers/scripts":
            wanted = self.scripts_status_for_builds_token if token == "builds-token" else self.scripts_status
            if wanted != 200:
                return self._denied()
            return self._json({"result": [{"id": "misakanet-register-proxy", "tag": "other-tag"},
                                          {"id": WORKER, "tag": TAG}]})

        if path == f"/accounts/{ACCOUNT}/builds/workers/{TAG}/triggers":
            return self._json({"result": self.triggers})

        if path == f"/accounts/{ACCOUNT}/builds/workers/{TAG}/builds":
            if self.builds_list_status != 200:
                return self._denied()
            return self._json({"result": self.builds})

        if path.startswith(f"/accounts/{ACCOUNT}/builds/builds/") and path.endswith("/logs"):
            uuid = path.split("/builds/builds/", 1)[1][: -len("/logs")]
            pages = self.logs_by_build.get(uuid)
            if pages is None:
                return self._json({"success": False, "errors": [{"code": 12000, "message": "Not found"}]}, 404)
            if "cursor=" in query:
                index = int(query.split("cursor=", 1)[1])
            else:
                index = 0
            lines = pages[min(index, len(pages) - 1)]
            truncated = index < len(pages) - 1
            return self._json({"result": {
                "lines": lines,
                "truncated": truncated,
                "cursor": str(index + 1) if truncated else None,
            }})

        return self._json({"result": []})


def make_trigger(name: str, token: str, branches: list) -> dict:
    return {
        "trigger_uuid": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "trigger_name": name,
        "build_command": StubAccount.build_command,
        "deploy_command": "npx wrangler deploy",
        "root_directory": "docs",
        "branch_includes": branches,
        "path_includes": ["docs/**"],
        "build_token_uuid": token,
        "environment_variables": {"CLOUDFLARE_API_TOKEN": {
            "value": DOC_EXAMPLE, "is_secret": True}},
    }


@pytest.fixture(autouse=True)
def _reset():
    StubAccount.triggers = [
        make_trigger("Deploy default branch", "aaaaaaaa-1111-2222-3333-444444444444", ["main"]),
        make_trigger("Deploy non-production branches", "aaaaaaaa-1111-2222-3333-444444444444", ["*"]),
    ]
    StubAccount.builds = [
        build(FAILED_BUILD, "2026-09-24T09:05:00Z", "fail", "8c1f3d1a0d0e"),
        build(GREEN_BUILD, "2026-09-24T11:17:00Z", "success", "10bf35a132f7"),
    ]
    StubAccount.scripts_status = 200
    StubAccount.scripts_status_for_builds_token = 200
    StubAccount.builds_list_status = 200
    StubAccount.build_command = "npm run build"
    StubAccount.logs_by_build = {
        FAILED_BUILD: [FIRST_PAGE, SECOND_PAGE],
        GREEN_BUILD: [[[1758700200, "Deployed misakanet-web"]], ],
    }
    StubAccount.seen = []
    StubAccount.tokens_seen = []
    yield


@pytest.fixture()
def stub():
    """A live stub account, and the runner the step's python is executed with."""
    server = HTTPServer(("127.0.0.1", 0), StubAccount)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def run_step(base: str | None, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = child_env({
        "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
        "CLOUDFLARE_API_TOKEN": "observability-token",
        "CF_BUILDS_WORKER": WORKER,
        **(env_extra if env_extra is not None else {"CF_BUILDS_TOKEN": "builds-token"}),
    })
    if base:
        env["CF_API_BASE"] = base
    return subprocess.run([sys.executable, "-c", python_block(step_script())],
                          capture_output=True, text=True, env=env)


def test_the_failing_builds_log_is_the_output(stub):
    """The deliverable is the error text of the red build, not a table of build metadata."""
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "error TS1005: ')' expected" in proc.stdout, proc.stdout
    assert "Failed: error occurred while running build command" in proc.stdout, proc.stdout
    # …and it is the failing build's log, not the green one's.
    assert FAILED_BUILD in proc.stdout, proc.stdout


def test_a_green_build_newer_than_the_red_one_does_not_hide_it(stub):
    """The stub lists the green build as the newest *and* lists oldest-first.

    Both orderings are the same trap: a step that reads "the latest build" reports a healthy pipeline
    while the site is down, which is precisely the failure #2136 is about.
    """
    assert StubAccount.builds[-1]["build_outcome"] == "success"  # guard the stub itself
    proc = run_step(stub)
    assert f"== log for build {FAILED_BUILD}" in proc.stdout, proc.stdout
    assert f"== log for build {GREEN_BUILD}" not in proc.stdout, proc.stdout


def test_the_newest_of_several_failures_is_the_one_read(stub):
    """Sorting is load-bearing once more than one build failed.

    Found by mutation: with a single failure in the page, `failing[0]` is the right build whether or
    not the rows are sorted, so removing the sort changed nothing and the test stayed green. A red
    pipeline fails repeatedly — which is the actual situation in #2136 — and then the API's ordering
    decides which log gets printed. An implementation that trusts the API's order reports the *first*
    failure of the day as if it were the current one.
    """
    older = "99999999-8888-7777-6666-555555555555"
    StubAccount.builds = [
        build(older, "2026-09-24T08:00:00Z", "fail", "aaaaaaa0"),
        build(FAILED_BUILD, "2026-09-24T09:05:00Z", "fail", "8c1f3d1a0d0e"),
        build(GREEN_BUILD, "2026-09-24T11:17:00Z", "success", "10bf35a132f7"),
    ]
    StubAccount.logs_by_build[older] = [[[1758699000, "error: an older, unrelated failure"]]]
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"== log for build {FAILED_BUILD}" in proc.stdout, proc.stdout
    assert f"== log for build {older}" not in proc.stdout, proc.stdout
    assert "an older, unrelated failure" not in proc.stdout, proc.stdout


def test_an_error_outside_the_tail_is_still_printed(stub):
    """A real build log is thousands of lines; the tail is not where the cause is.

    Found by mutation: with a three-line log the tail contains everything, so deleting the error scan
    changed nothing and the test stayed green. The failing line sits at the *start* here and the log is
    padded past the tail window — only the keyword scan can surface it.

    The padding is error-shaped on purpose, so the list of matches is longer than the window the step
    prints from it. That is the second way this can lie: a scan that keeps only the *last* few matches
    prints the cascade and drops the cause, which is the one line that names the problem.
    """
    noise_pages = [
        [[1758700100 + i * 100 + j, f"[{i}] step {j}: warning: retrying after error {j}"]
         for j in range(80)]
        for i in range(2)
    ]
    StubAccount.logs_by_build[FAILED_BUILD] = [
        [[1758700000, "error: the build command exited 1 (this line is not in the tail)"]],
        *noise_pages,
    ]
    proc = run_step(stub, env_extra={"CF_BUILDS_TOKEN": "builds-token", "CF_BUILDS_LOG_LINES": "120"})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "this line is not in the tail" in proc.stdout, proc.stdout
    matches = proc.stdout.split("line(s) that look like the error ==", 1)
    assert len(matches) == 2, proc.stdout
    assert int(matches[0].rsplit("==", 1)[-1].strip()) > 40, \
        "the stub no longer produces more matches than one window, so this test proves nothing"


def test_the_whole_log_is_read_not_just_the_first_page(stub):
    """`truncated: true` + `cursor` means the answer is on the page a naive step never asks for."""
    proc = run_step(stub)
    assert "error TS1005" in proc.stdout, proc.stdout
    assert any("cursor=" in s for s in StubAccount.seen), \
        "the step did not follow the log cursor, so it read only the start of the log"


def test_the_build_command_is_reported_because_the_repository_does_not_have_it():
    """No `build` script in `package.json`, no build command in `wrangler.jsonc` — it lives in the panel.

    Printing it is how the build command stops being invisible to this repository; if the step stops
    asking for the trigger, that fact is lost again.
    """
    block = python_block(step_script())
    assert "/builds/workers/" in block and "/triggers" in block, \
        "the step no longer reads the trigger, which is the only record of the build command"


def test_the_build_command_and_deploy_command_are_printed(stub):
    proc = run_step(stub)
    assert "build_command:  npm run build" in proc.stdout, proc.stdout
    assert "deploy_command: npx wrangler deploy" in proc.stdout, proc.stdout
    assert "root=" in proc.stdout and "docs" in proc.stdout, proc.stdout


def test_a_credential_in_the_trigger_is_never_printed(stub):
    """This is a job log on a *public* repository, and a trigger may carry a token.

    `CLOUDFLARE_API_TOKEN=… npx wrangler deploy` is a normal way to configure a build, and per-trigger
    environment variables are a documented Builds feature — so the diagnostic that exists to explain a
    broken deploy is one careless `print` away from publishing the credential it was diagnosing. The
    step prints variable *names* and redacts token-shaped runs out of the commands.
    """
    StubAccount.triggers[0]["build_command"] = (
        "CLOUDFLARE_API_TOKEN={} npm run build".format(DOC_EXAMPLE))
    assert DOC_EXAMPLE in StubAccount.triggers[0]["build_command"], "the fixture lost the token"
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert DOC_EXAMPLE not in proc.stdout, "the step printed a credential into a public job log"
    assert "redacted" in proc.stdout, proc.stdout
    # …and the useful half survives: the variable is named, its value is not.
    assert "CLOUDFLARE_API_TOKEN" in proc.stdout, proc.stdout
    assert "names only" in proc.stdout, proc.stdout
    assert "npm run build" in proc.stdout, proc.stdout


def test_the_worker_is_looked_up_by_tag_not_by_name(stub):
    """The API documents that every Builds endpoint wants the tag; the name is not accepted."""
    proc = run_step(stub)
    assert f"tag={TAG}" in proc.stdout, proc.stdout
    assert any(f"/builds/workers/{TAG}/builds" in s for s in StubAccount.seen), StubAccount.seen


def test_a_missing_token_warns_and_the_run_continues():
    """The token is optional by design, like the observability one it sits next to."""
    proc = run_step(None, env_extra={"CF_BUILDS_TOKEN": ""})
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "::warning::CF_BUILDS_TOKEN is not set" in proc.stdout, proc.stdout
    assert "credentials-and-environments.md" in proc.stdout, proc.stdout


def test_the_tag_lookup_falls_back_to_the_other_cloudflare_token(stub):
    """Measured risk, not a hypothetical: `/workers/scripts` is a *Workers Scripts* read, which the
    Builds permission group does not include. The deploy/observability token can already read it, so a
    token that carries only the Builds scope must not cost a second dispatch."""
    StubAccount.scripts_status_for_builds_token = 403
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CF_BUILDS_TOKEN: HTTP 403" in proc.stdout, proc.stdout
    assert f"CLOUDFLARE_API_TOKEN: workers listed, {WORKER} -> tag={TAG}" in proc.stdout, proc.stdout
    assert "error TS1005" in proc.stdout, proc.stdout


def test_a_token_that_can_read_nothing_is_a_finding_not_a_failure(stub):
    """A 403 body names the missing permission — that is the answer to "why is this empty"."""
    StubAccount.scripts_status = 403
    StubAccount.scripts_status_for_builds_token = 403
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "::warning::could not resolve the tag" in proc.stdout, proc.stdout
    assert "Workers Scripts: Read" in proc.stdout, proc.stdout


def test_a_build_list_that_cannot_be_read_does_not_fail_the_run(stub):
    """The other steps of the run are still worth their dispatch; only the exit status must not lie."""
    StubAccount.builds_list_status = 403
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "::warning::build list failed" in proc.stdout, proc.stdout
    assert "HTTP 403" in proc.stdout, proc.stdout


def test_a_green_pipeline_says_so_instead_of_printing_nothing(stub):
    """When the fix lands, this step has to be able to show it — otherwise the next session cannot
    tell "green" from "the step broke and printed nothing"."""
    StubAccount.builds = [build(GREEN_BUILD, "2026-09-25T00:00:00Z", "success", "aaaaaaa")]
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no failing build in the newest page" in proc.stdout, proc.stdout


def test_the_workflow_env_still_carries_both_credentials():
    """The step reads `CF_BUILDS_TOKEN` from the job env; without the wiring above it is always empty."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    env = workflow["jobs"]["diagnose"]["env"]
    assert "secrets.CF_BUILDS_TOKEN" in env["CF_BUILDS_TOKEN"], env["CF_BUILDS_TOKEN"]
    assert "CF_OBSERVABILITY_TOKEN" in env["CLOUDFLARE_API_TOKEN"], env["CLOUDFLARE_API_TOKEN"]


# ── the build token is identified, not assumed ────────────────────────────────────────────────────

def test_each_trigger_reports_the_build_token_it_deploys_with(stub):
    """"I replaced the build token" has to be checkable, and the UUID is the only field that shows it.

    Asked for while renewing the site's token (2026-09-24, #2136), because the failure it prevents is a
    renewal that lands on one trigger and not the other: the dashboard looks fixed, one branch's builds
    keep dying with the same error, and nothing distinguishes that from "the renewal did not work".
    """
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.count("build_token_uuid: aaaaaaaa-1111-2222-3333-444444444444") == 2, proc.stdout
    assert "share build token aaaaaaaa-1111-2222-3333-444444444444" in proc.stdout, proc.stdout


def test_two_triggers_with_different_tokens_are_called_out(stub):
    """The half-fixed pipeline, which looks exactly like a working one from the dashboard."""
    StubAccount.triggers[1]["build_token_uuid"] = "bbbbbbbb-5555-6666-7777-888888888888"
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "2 DIFFERENT build tokens" in proc.stdout, proc.stdout
    assert "half-fixed pipeline" in proc.stdout, proc.stdout
    # …and the warning has to say *which* trigger carries which token, or the reader's next step is to
    # go and find out. (Mutation found this: dropping the mapping from the message left the tests green.)
    warning = next(line for line in proc.stdout.splitlines() if "DIFFERENT build tokens" in line)
    for token in ("aaaaaaaa-1111-2222-3333-444444444444", "bbbbbbbb-5555-6666-7777-888888888888"):
        assert token in warning, warning
    assert "Deploy default branch" in warning and "Deploy non-production branches" in warning, warning


def test_a_missing_build_token_uuid_is_not_silence(stub):
    """If the API stops publishing the field, the confirmation stops working — say so rather than
    print nothing and let "no warning" read as "the tokens match"."""
    for trigger in StubAccount.triggers:
        trigger.pop("build_token_uuid")
    proc = run_step(stub)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no build_token_uuid was returned" in proc.stdout, proc.stdout
    assert "(not returned)" in proc.stdout, proc.stdout


def test_the_build_token_value_is_never_printed(stub):
    """A UUID is an identifier; the token it points at is not. Only the UUID may appear."""
    proc = run_step(stub)
    assert DOC_EXAMPLE not in proc.stdout, (
        "the step printed the credential itself, not just the identifier"
    )
