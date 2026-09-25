#!/usr/bin/env python3
"""A red site build was invisible for a day; the watcher that fixes that is tested for the same fault.

#2136's failure mode is "a red check nobody is required to look at": `Workers Builds: misakanet-web`
is not in the ruleset's required list, its check-run carries no summary, no annotation and no log, and
the build command is not in this repository — so the first failing build (2026-09-23T17:40Z, the #2133
merge) went unnoticed while ~25 commits landed and the live site stayed byte-identical to the commit
before it (`7fcebbf2a`).

`scripts/workers_builds_watch.py` turns that red check into an issue. Which means the watcher's own
failure modes are the interesting part, and they are the mirror image of the bug it fixes:

* **silence** — a watcher that decides "nothing to do" on the state it exists to catch (a queued build
  read as a failure, a split green/red pair read as green, a missing tracker read as "already
  reported") is the original bug with more code in it;
* **noise** — a watcher that comments on every push is a different way to be ignored, which is why the
  policy is transitions only.

Both are pinned here, plus the end-to-end runs against a stub GitHub that check which writes actually
happen — the policy being right is not the same as the right request being sent.
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
SCRIPT = REPO / "scripts" / "workers_builds_watch.py"
WORKFLOW = REPO / ".github" / "workflows" / "workers-builds-watch.yml"

OWNER_REPO = "Ikalus1988/MisakaNet"
SHA = "8c1f3d1a9f120bfe9f35a5908456cb27b7b778f4"
GREEN_SHA = "7fcebbf2a0000000000000000000000000000000"
BUILD_UUID = "591e7ff1-4cd2-4bcd-a1b8-2fa0b210ff0b"
LABEL = "site-build-red"
DETAILS = (f"https://dash.cloudflare.com/6b92325b505f2b76aec49e9fe4195d31/workers/services/view/"
           f"misakanet-web/production/builds/{BUILD_UUID}")


def sys_path_setup():
    sys.path.insert(0, str(REPO / "scripts"))


def load_module():
    """Import the watcher as a module, so `plan()` can be tested without a subprocess."""
    sys_path_setup()
    import importlib
    return importlib.import_module("workers_builds_watch")


def run_watch(base: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra],
        capture_output=True, text=True,
        # `child_env`, not a hardcoded POSIX PATH: on Windows a PATH without System32 cannot load
        # Winsock, so every stub call failed with WinError 10106 and these tests were red on that leg
        # for a harness reason (tests/subprocess_env.py).
        # the mapping form, not keyword arguments: the kwargs spelling writes the token name and an
        # equals sign next to a quoted value, which is the assignment shape
        # `tests/test_scanner_secret_patterns.py` refuses to keep in this surface (it caught this very
        # line). The dict spelling keeps the scan clean, as it was before.
        env=child_env({"GH_TOKEN": "stub-token", "GH_REPO": OWNER_REPO,
                       "GH_API_BASE": base, "PYTHONPATH": str(REPO / "scripts")}),
    )


def check_run(conclusion: str, status: str = "completed", name: str = "Workers Builds: misakanet-web") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion,
            "external_id": BUILD_UUID, "details_url": DETAILS}


class StubGitHub(BaseHTTPRequestHandler):
    """A repository whose site build is red, and a recorder of every write the watcher attempts."""

    runs: list = [check_run("failure")]
    issues: list = []          # open issues carrying the label
    comments: list = []        # comments on the tracker issue
    label_status = 201
    writes: list = []
    seen: list = []

    def log_message(self, *args):
        pass

    def _json(self, payload, status: int = 200) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802 (http.server naming)
        path = self.path.split("?")[0]
        type(self).seen.append("GET " + self.path)
        if path.endswith("/check-runs"):
            return self._json({"check_runs": self.runs})
        if path == f"/repos/{OWNER_REPO}/issues":
            return self._json(self.issues)
        if path.endswith("/comments"):
            return self._json(self.comments)
        if path.startswith(f"/repos/{OWNER_REPO}/branches/"):
            return self._json({"commit": {"sha": SHA}})
        return self._json({})

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode()) if length else {}
        type(self).writes.append(("POST", path, body))
        if path == f"/repos/{OWNER_REPO}/labels":
            if self.label_status != 201:
                return self._json({"message": "Validation Failed"}, self.label_status)
            return self._json({"name": body.get("name")}, 201)
        if path == f"/repos/{OWNER_REPO}/issues":
            return self._json({"number": 4242, "html_url": "https://example.test/issues/4242"}, 201)
        if path.endswith("/comments"):
            return self._json({"html_url": "https://example.test/issues/1#issuecomment-1"}, 201)
        return self._json({}, 201)


@pytest.fixture(autouse=True)
def _reset():
    StubGitHub.runs = [check_run("failure")]
    StubGitHub.issues = []
    StubGitHub.comments = []
    StubGitHub.label_status = 201
    StubGitHub.writes = []
    StubGitHub.seen = []
    yield


@pytest.fixture()
def stub():
    server = HTTPServer(("127.0.0.1", 0), StubGitHub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def marker_comment(state: str) -> dict:
    return {"body": f"report\n\n<!-- workers-builds-watch: state={state} sha={SHA} -->"}


def posts() -> list[tuple[str, str]]:
    return [(m, p) for m, p, _ in StubGitHub.writes]


# ── the policy, as a table ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("state,tracker_exists,previous,expected", [
    # the bug this exists for: red and nobody has said anything yet
    ("red", False, "unknown", "create"),
    ("red", True, "unknown", "comment"),      # a human just labelled the tracker
    ("red", True, "green", "comment"),        # it went red again
    ("red", True, "red", "none"),             # 25 pushes are not 25 comments
    # going green is a transition worth one comment, not one per push
    ("green", True, "red", "comment"),
    ("green", True, "green", "none"),
    # and nothing is said about a healthy repo with no tracker
    ("green", False, "unknown", "none"),
    # an unfinished or unreadable build is not a failure
    ("unknown", False, "unknown", "none"),
    ("unknown", True, "red", "none"),
])
def test_the_policy_is_transitions_only(state, tracker_exists, previous, expected):
    assert load_module().plan(state, tracker_exists, previous) == expected


def test_red_wins_over_green_when_a_commit_has_both(stub):
    """A commit can carry two Workers Builds runs (a preview trigger and the production one).

    Reporting the healthy half of a split pair is the exact mistake the watcher exists to prevent.
    """
    StubGitHub.runs = [check_run("success"), check_run("failure")]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "site build: red" in proc.stdout, proc.stdout
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), posts()


def test_an_unfinished_build_is_not_a_failure(stub):
    StubGitHub.runs = [check_run(None, status="in_progress")]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "site build: unknown" in proc.stdout, proc.stdout
    assert StubGitHub.writes == [], StubGitHub.writes


def test_no_workers_builds_check_run_at_all_is_not_a_failure(stub):
    StubGitHub.runs = [{"name": "gate", "status": "completed", "conclusion": "failure"}]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "no Workers Builds check-run" in proc.stdout, proc.stdout
    assert StubGitHub.writes == [], StubGitHub.writes


# ── the requests actually sent ──────────────────────────────────────────────────────────────────────

def test_a_red_build_with_no_tracker_opens_one_issue_carrying_the_label(stub):
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ("POST", f"/repos/{OWNER_REPO}/labels") in posts(), posts()
    creates = [b for m, p, b in StubGitHub.writes if p == f"/repos/{OWNER_REPO}/issues"]
    assert len(creates) == 1, StubGitHub.writes
    assert LABEL in creates[0]["labels"], creates[0]
    # The issue has to be actionable by itself: which build, and how to get its log.
    assert BUILD_UUID in creates[0]["body"], creates[0]["body"]
    assert "CF diagnostics" in creates[0]["body"], creates[0]["body"]
    assert "<!-- workers-builds-watch: state=red" in creates[0]["body"], creates[0]["body"]


def test_a_repeated_red_build_writes_nothing(stub):
    """The difference between an alert and noise: the state did not change."""
    StubGitHub.issues = [{"number": 2136, "title": "tracker"}]
    StubGitHub.comments = [marker_comment("red")]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip().endswith("-> none"), proc.stdout
    assert StubGitHub.writes == [], StubGitHub.writes


def test_a_new_red_transition_comments_on_the_tracker(stub):
    StubGitHub.issues = [{"number": 2136, "title": "tracker"}]
    StubGitHub.comments = [marker_comment("green")]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert posts() == [("POST", f"/repos/{OWNER_REPO}/issues/2136/comments")], posts()
    body = StubGitHub.writes[0][2]["body"]
    assert "state=red" in body, body
    assert SHA in body, body


def test_going_green_comments_once_and_does_not_close_the_issue(stub):
    """A green build is evidence; whether that closes the issue is the maintainer's call."""
    StubGitHub.runs = [check_run("success")]
    StubGitHub.issues = [{"number": 2136, "title": "tracker"}]
    StubGitHub.comments = [marker_comment("red")]
    proc = run_watch(stub, "--sha", GREEN_SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert posts() == [("POST", f"/repos/{OWNER_REPO}/issues/2136/comments")], posts()
    body = StubGitHub.writes[0][2]["body"]
    assert "green again" in body, body
    assert "state=green" in body, body


def test_a_healthy_repository_with_no_tracker_is_left_alone(stub):
    StubGitHub.runs = [check_run("success")]
    proc = run_watch(stub, "--sha", GREEN_SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert StubGitHub.writes == [], StubGitHub.writes


def test_a_label_that_already_exists_does_not_stop_the_issue(stub):
    """`POST /labels` answers 422 for a label that exists, and that is not a reason to stay silent."""
    StubGitHub.label_status = 422
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "label not created" in proc.stdout, proc.stdout
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), posts()


def test_a_pull_request_is_not_mistaken_for_the_tracker(stub):
    """`GET /issues?labels=` returns pull requests too, and commenting on a PR is not the contract."""
    StubGitHub.issues = [{"number": 2158, "pull_request": {"url": "x"}}]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), posts()


def test_dry_run_writes_nothing(stub):
    proc = run_watch(stub, "--sha", SHA, "--dry-run")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "would create the tracking issue" in proc.stdout, proc.stdout
    assert StubGitHub.writes == [], StubGitHub.writes


# ── the event path ──────────────────────────────────────────────────────────────────────────────────

def write_event(tmp_path: Path, sha: str, branch: str) -> str:
    payload = {"check_suite": {"head_sha": sha, "head_branch": branch,
                               "app": {"slug": "cloudflare-workers-and-pages"},
                               "conclusion": "failure"}}
    path = tmp_path / "event.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_the_event_payload_supplies_the_commit_and_the_branch(stub, tmp_path):
    event = write_event(tmp_path, SHA, "main")
    proc = run_watch(stub, "--event", event)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"sha={SHA[:9]}" in proc.stdout, proc.stdout
    assert not any("/branches/" in s for s in StubGitHub.seen), \
        "the event carries head_sha, so the branch tip must not be fetched at all"


def test_a_red_build_on_a_feature_branch_is_not_the_maintainers_problem(stub, tmp_path):
    """Only the branch that deploys the site is worth an issue on the tracker."""
    event = write_event(tmp_path, SHA, "feature/whatever")
    proc = run_watch(stub, "--event", event)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # The message has to name the real reason: the first version printed "no commit for main (branch
    # main is not visible?)", which sends a reader hunting a token problem that is not there.
    assert "skipped on purpose" in proc.stdout, proc.stdout
    assert "feature/whatever is not main" in proc.stdout, proc.stdout
    assert StubGitHub.writes == [], StubGitHub.writes


def test_any_branch_can_be_watched_on_request(stub, tmp_path):
    event = write_event(tmp_path, SHA, "feature/whatever")
    proc = run_watch(stub, "--event", event, "--any-branch")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), posts()


def test_the_scheduled_path_reads_the_tip_of_main(stub):
    proc = run_watch(stub, "--branch", "main")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert any(f"/branches/main" in s for s in StubGitHub.seen), StubGitHub.seen
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), posts()


# ── an unreadable payload is not a reason to lose the run ───────────────────────────────────────────
#
# `resolve_target` called `json.loads(Path(args.event).read_text())` directly, so `$GITHUB_EVENT_PATH`
# pointing at a file that is absent (`FileNotFoundError`) or half-written (`JSONDecodeError`) ended the
# run in a stack trace. The trigger always sets that variable for the events this workflow listens to,
# which is exactly why the failure is worth surviving rather than printing: it means the trigger changed,
# not that the build is fine, and the answer the watcher needs is also available from the branch tip. A
# watcher that exists because a red build was invisible must not be the thing that goes invisible.

def test_a_missing_event_payload_falls_back_to_the_branch_tip(stub, tmp_path):
    missing = tmp_path / "not-there.json"
    proc = run_watch(stub, "--event", str(missing))
    assert proc.returncode == 0, (
        "an unreadable payload must not end the run in a traceback:\n" + proc.stdout + proc.stderr)
    assert "Event payload unreadable" in proc.stderr, proc.stderr
    assert str(missing) in proc.stderr, "the warning has to name the file, or nobody can check it"
    assert "/branches/main" in " ".join(StubGitHub.seen), StubGitHub.seen
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), (
        "the run still has to report the red build it was triggered by")


def test_a_malformed_event_payload_falls_back_to_the_branch_tip(stub, tmp_path):
    half_written = tmp_path / "event.json"
    half_written.write_text('{"check_suite": {"head_sha": "8c1f3d1a', encoding="utf-8")
    proc = run_watch(stub, "--event", str(half_written))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Event payload unreadable" in proc.stderr, proc.stderr
    assert f"sha={SHA[:9]}" in proc.stdout, proc.stdout
    assert ("POST", f"/repos/{OWNER_REPO}/issues") in posts(), posts()


# ── the workflow around it ──────────────────────────────────────────────────────────────────────────

def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_watcher_can_read_checks_and_write_issues():
    """`checks: read` is what makes the check-run visible; without it every run says "nothing to do"."""
    permissions = workflow()["permissions"]
    assert permissions.get("checks") == "read", permissions
    assert permissions.get("issues") == "write", permissions
    assert permissions.get("contents") == "read", permissions


def test_the_watcher_runs_on_cloudflare_check_suites_and_on_a_schedule():
    """Two triggers, because each covers the other's blind spot: instant delivery, and delivery that
    might quietly stop."""
    triggers = workflow().get("on") or workflow().get(True)  # YAML 1.1 turns `on` into True
    assert "completed" in triggers["check_suite"]["types"], triggers
    assert any("cron" in str(entry) for entry in triggers["schedule"]), triggers
    assert "workflow_dispatch" in triggers, triggers


def test_the_job_ignores_check_suites_from_other_apps():
    """Actions' own suites do not fire this event, but the filter is what makes that an assumption
    rather than a requirement."""
    condition = workflow()["jobs"]["watch"]["if"]
    assert "cloudflare-workers-and-pages" in condition, condition


def test_the_job_does_not_even_start_for_feature_branches():
    """The same rule as the script's branch guard, one level earlier.

    The repository pushes many branches, and each Cloudflare suite on one would otherwise start a run
    whose entire job is to print "skipped on purpose" — noise in the Actions list, which is where noise
    hides the real thing. The script keeps the guard as well, because that copy is the one the tests
    exercise and the one the cron uses.
    """
    condition = workflow()["jobs"]["watch"]["if"]
    assert "check_suite.head_branch == 'main'" in condition, condition


def test_only_one_watcher_runs_at_a_time():
    """Two concurrent runs that both see "no tracker" would both open an issue."""
    assert workflow()["concurrency"]["group"], workflow()["concurrency"]
    assert workflow()["concurrency"]["cancel-in-progress"] is False, workflow()["concurrency"]


def test_the_script_is_called_with_the_event_payload_in_the_event_path():
    steps = workflow()["jobs"]["watch"]["steps"]
    runs = "\n".join(step.get("run") or "" for step in steps)
    assert "workers_builds_watch.py" in runs, runs
    assert "--event" in runs, runs
    assert "GITHUB_EVENT_PATH" in runs, runs


def test_the_repository_is_passed_explicitly():
    """A watcher that silently watches the wrong repository reports nothing and looks healthy.

    The first version of the step set `GH_REPO` in the env and never read it in the shell — caught by
    `tests/test_workflow_env_is_used.py`, which is why the repository is an argument now.
    """
    steps = workflow()["jobs"]["watch"]["steps"]
    runs = "\n".join(step.get("run") or "" for step in steps)
    assert runs.count('--repo "${GITHUB_REPOSITORY}"') == 2, runs



def test_the_label_payload_fits_what_github_accepts(stub):
    """Measured 2026-09-24: a 157-character description made label creation answer
    `422 Validation Failed … description is too long (maximum is 100 characters)`.

    It is a small thing that fails in a quiet way — creating the label is best-effort here, so the
    run continues and only the label lacks its description — which is exactly the kind of silent
    half-failure this repository writes tests for. The request body is checked, not the constant, so
    the assertion holds wherever the string comes from.
    """
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    label_calls = [b for m, p, b in StubGitHub.writes if p == f"/repos/{OWNER_REPO}/labels"]
    assert len(label_calls) == 1, StubGitHub.writes
    assert len(label_calls[0]["description"]) <= 100, label_calls[0]
    assert label_calls[0]["name"] == LABEL, label_calls[0]


def test_the_red_wording_does_not_claim_it_opened_an_issue(stub):
    """The first production run commented on an existing tracker, and the text said "opened this".

    That was the watcher's only wrong output in production — and it was wrong in the direction that
    matters least for safety and most for trust: a maintainer reading it would look for an issue that
    does not exist, or wonder what the watcher thought it was doing. Both paths (create and comment)
    use this body, so the sentence has to be true of both.
    """
    StubGitHub.issues = [{"number": 2136, "title": "tracker"}]
    proc = run_watch(stub, "--sha", SHA)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    body = StubGitHub.writes[0][2]["body"]
    assert "reported this" in body, body
    assert "opened this" not in body, body
