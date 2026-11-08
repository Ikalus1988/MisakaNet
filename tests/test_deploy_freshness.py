#!/usr/bin/env python3
"""`doctor.py --deploy-freshness` answers the question the version cannot (#2779).

Production sat three days and five merged PRs behind on 2026-10-03 with every check green,
because `serverInfo.version` only moves on a release and the post-deploy probe only runs after a
deploy that already succeeded. These tests pin the three outcomes the check has to distinguish —
same commit, behind, and *cannot tell* — because collapsing the last two is exactly the defect:
a probe that reports "fine" when it measured nothing is worse than no probe at all.

They also pin the two halves that make the number mean anything: the worker has to report a SHA,
and the deploy has to be the thing that passes it.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import doctor  # noqa: E402  (after sys.path, and deliberately the real module)

HEAD = "a" * 40
LIVE = "b" * 40


def _patch(monkeypatch, live_sha, head=HEAD, behind=None, worker_commits=None):
    monkeypatch.setattr(
        doctor, "health_body",
        lambda url=doctor.HEALTH_ENDPOINT: (True, f"{url} reachable", {"commit_sha": live_sha}),
    )
    monkeypatch.setattr(doctor, "local_head_sha", lambda: head)
    monkeypatch.setattr(doctor, "commits_behind", lambda live, h: behind)
    monkeypatch.setattr(doctor, "worker_commits_since", lambda live, h, cwd=None: worker_commits)


def test_the_same_commit_passes(monkeypatch):
    _patch(monkeypatch, HEAD)
    ok, message = doctor.check_deploy_freshness()
    assert ok, message
    assert HEAD[:12] in message


def test_a_stale_deployment_fails_and_says_by_how_much(monkeypatch):
    # `worker_commits` non-empty: at least one of the seven commits changes the deployed worker,
    # which is exactly the deploy that did not land.
    _patch(monkeypatch, LIVE, head=HEAD, behind=7, worker_commits=["c" * 40])
    ok, message = doctor.check_deploy_freshness()
    assert not ok, "a worker on an older commit is stale, whatever version it reports"
    assert LIVE[:12] in message and HEAD[:12] in message
    assert "7 commit(s) behind" in message


def test_corpus_commits_after_the_deploy_are_not_staleness(monkeypatch):
    """main gets a corpus-sync commit several times a day; the worker is redeployed only when one
    of WORKER_DEPLOY_PATHS changes. Measured 2026-11-06..08: all three scheduled runs reddened on
    seven `chore(data)` commits, i.e. on a deploy that had nothing to deploy."""
    _patch(monkeypatch, LIVE, head=HEAD, behind=7, worker_commits=[])
    ok, message = doctor.check_deploy_freshness()
    assert ok, message
    assert "last commit that changes the worker" in message
    assert "7 commit(s) behind" in message, "the size of the gap is still reported"


def test_an_unmeasurable_git_answer_is_not_freshness(monkeypatch):
    """`worker_commits_since` returns None on a shallow clone or an unknown SHA. Only an empty
    *measurement* may turn the probe green; "could not tell" must keep the old failure."""
    _patch(monkeypatch, LIVE, head=HEAD, behind=7, worker_commits=None)
    ok, message = doctor.check_deploy_freshness()
    assert not ok, "a probe that could not measure must not report fresh"
    assert "stale" in message


def test_worker_commits_since_reads_the_deploy_paths(tmp_path):
    """The real git call, against a throwaway repository: a commit outside `workers/` is not a
    deploy, and a commit inside it is."""
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
            cwd=repo, check=True, capture_output=True, text=True,
        ).stdout.strip()
    git("init", "-q")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "docs: first")
    first = git("rev-parse", "HEAD")
    (repo / "data").mkdir()
    (repo / "data" / "lessons.json").write_text("{}\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "chore(data): sync")
    (repo / "workers").mkdir()
    (repo / "workers" / "register-proxy-sw.js").write_text("export default {};\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "fix(worker): change the deployed artifact")
    second = git("rev-parse", "HEAD")

    assert doctor.worker_commits_since(first, second, cwd=str(repo)) == [second]
    assert doctor.worker_commits_since(first, first, cwd=str(repo)) == []


def test_an_unknown_sha_fails_rather_than_claiming_freshness(monkeypatch):
    """`make deploy-api` deploys without a SHA. Reporting that as fresh would reintroduce the
    original defect in a new place, so it is reported as unverified."""
    for value in ("unknown", "", None):
        _patch(monkeypatch, value)
        ok, message = doctor.check_deploy_freshness()
        assert not ok, f"{value!r} must not read as fresh"
        assert "cannot be" in message and "verified" in message


def test_an_unreachable_service_is_not_reported_as_stale(monkeypatch):
    """A dropped TLS handshake is weather. It must not read as "production is behind" — this
    workflow retries rather than trusting a single answer, precisely because a TLS handshake to
    misakanet.org drops often enough on a real connection to be unremarkable."""
    monkeypatch.setattr(doctor, "health_body", lambda url=doctor.HEALTH_ENDPOINT: (False, f"{url} unreachable", {}))
    ok, message = doctor.check_deploy_freshness()
    assert not ok
    assert "unreachable" in message
    assert "behind" not in message, "an unreachable service is not evidence of staleness"


def test_a_checkout_with_no_readable_head_does_not_guess(monkeypatch):
    _patch(monkeypatch, LIVE, head="")
    ok, message = doctor.check_deploy_freshness()
    assert not ok
    assert "no readable HEAD" in message


def test_the_worker_actually_reports_its_commit():
    """Without this the check can only ever say `unknown` and stay red forever.

    Asserts the endpoint goes through `deployedCommit()` rather than carrying the fallback inline, so
    the "unknown" behaviour is covered by `workers/health-commit-sha.test.mjs` — which drives the
    real helper — instead of only being visible on the deployed endpoint. A literal in the handler
    would be the one branch nothing can exercise until it is live.
    """
    source = (REPO / "workers" / "register-proxy-sw.js").read_text(encoding="utf-8")
    assert "commit_sha: deployedCommit(env)" in source, (
        "/api/health must expose commit_sha via deployedCommit(env); an inline `env.COMMIT_SHA || "
        '"unknown" leaves the fallback untestable until the worker is deployed'
    )
    assert "function deployedCommit(env = {})" in source, "the helper must exist to be called"
    assert "export function deployedCommit" not in source, (
        "deployedCommit is exported from the block at the bottom of the file, not inline; declaring "
        "it twice is a SyntaxError that breaks every worker test"
    )


def test_the_deploy_is_what_supplies_the_sha():
    """The value has to come from the pipeline. A var that only exists in wrangler.toml would be
    frozen at whatever it said when it was written — the same class of bug as the version."""
    workflow = (REPO / ".github" / "workflows" / "deploy-worker.yml").read_text(encoding="utf-8")
    assert "--var COMMIT_SHA:" in workflow, (
        "deploy-worker.yml must pass COMMIT_SHA from GITHUB_SHA, or every deployment reports the "
        "same stale value"
    )
    assert "${GITHUB_SHA}" in workflow, "the SHA must be the one being deployed, not a literal"


def test_the_fallback_var_is_honest_about_being_unknown():
    toml = (REPO / "workers" / "wrangler.toml").read_text(encoding="utf-8")
    assert '[vars]' in toml and 'COMMIT_SHA = "unknown"' in toml, (
        "wrangler.toml needs a COMMIT_SHA default, and it must be 'unknown' rather than a real "
        "sha that would read as a deployment record it is not"
    )


def test_the_freshness_probe_is_scheduled_not_only_post_deploy():
    """The whole point: post-deploy verification cannot catch a deploy that never ran."""
    workflow = (REPO / ".github" / "workflows" / "deploy-freshness.yml")
    assert workflow.exists(), "the daily freshness workflow is the part that closes the #2779 gap"
    text = workflow.read_text(encoding="utf-8")
    assert "schedule:" in text, "a workflow_dispatch-only probe is a probe somebody must remember"
    assert "cron:" in text
    assert "--deploy-freshness" in text
    # Full history, or "N commits behind" degrades to "unknown" on every run.
    assert "fetch-depth: 0" in text, (
        "a shallow checkout cannot count how far behind production is, which is the number a human "
        "needs to decide whether to redeploy now or after review"
    )


def test_post_deploy_also_reads_the_sha_back():
    """Right after a deploy the checkout *is* the deployed commit, so this is the only place that
    can answer "did the COMMIT_SHA var actually reach the bundle" rather than "is production
    behind"."""
    text = (REPO / ".github" / "workflows" / "deploy-worker.yml").read_text(encoding="utf-8")
    probe = text[text.index("--post-deploy"):]
    assert "--deploy-freshness" in probe, (
        "the post-deploy probe must read the deployed SHA back; otherwise a deploy that lands the "
        "wrong bytes is indistinguishable from one that lands the right ones"
    )


def test_the_freshness_job_names_the_branch_it_measures_against():
    """`ref:` is not decoration — it is the difference between measuring and guessing.

    This job answers "is production running **main's** commit", so `main` is the only correct
    checkout on all three of its triggers. `schedule` and `workflow_run` default to the default
    branch, so those two were right by accident; `workflow_dispatch` accepts any ref, so a manual
    dispatch from a PR branch compared production against that PR's commit and reported a staleness
    that was not one. Naming the ref is also what settles code-scanning alerts #325 / #326
    (`GITHUB_ACTIONS_UNTRUSTED_CHECKOUT`), which fire on the `workflow_run` trigger and cannot see
    which ref such a checkout actually resolves to.

    The `|| 'main'` fallback is load-bearing rather than defensive: a `schedule` event's payload
    does not always carry `repository.default_branch`, and a freshness probe that resolves to
    nothing on its own backstop trigger is the precise failure this workflow was written to prevent.
    """
    text = (REPO / ".github" / "workflows" / "deploy-freshness.yml").read_text(encoding="utf-8")
    start = text.index("uses: actions/checkout")
    end = text.index("- name:", start)
    checkout = text[start:end]
    assert "ref:" in checkout, (
        "the checkout does not name a ref, so this job's answer depends on which trigger fired: a "
        "workflow_dispatch from a PR branch would compare production against that branch and report "
        "a staleness that does not exist"
    )
    assert "default_branch" in checkout, (
        "the ref must come from the repository rather than a literal — a hardcoded branch name is "
        "wrong the day the default branch is renamed"
    )
    assert "|| 'main'" in checkout, (
        "the schedule trigger's payload may not carry repository.default_branch, and a probe that "
        "resolves to nothing on its own backstop trigger is worse than no probe"
    )


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except TypeError:
                print("SKIP (needs fixtures)")
            except Exception as e:
                print(f"FAIL: {e}")
