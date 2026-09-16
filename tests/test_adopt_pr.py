#!/usr/bin/env python3
"""Offline tests for scripts/adopt_pr.py (issue #1778 — the `/adopt` fork-PR short path).

Every test builds throwaway repositories under ``tmp_path`` and drives the script against
them with a **local** "head repo" path, so nothing here touches the network, GitHub, or the
real checkout. The dry run is additionally asserted to be write-free: the refs and reflogs of
both the working repo and the "fork" are byte-identical before and after.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "adopt_pr.py"

PR = 1656
HEAD_BRANCH = "fix-issue-1652"
AUTHOR = "Taher Ezzi <taherezzi.dev@gmail.com>"
AUTHOR_LOGIN = "TaherEzzi"
ORIGINAL_TITLE = "fix: resolve #1652 - [Bounty][$0][Lessons] 把 intake #1553 转成课程"
ORIGINAL_BODY = "## Summary\n\nOriginal description, kept verbatim.\n\nCloses #1652\n"
REPO_SLUG = "Ikalus1988/MisakaNet"
FORK_SLUG = "TaherEzzi/MisakaNet"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_AUTHOR_DATE": "2026-09-16T10:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-09-16T10:00:00+00:00",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
}

CO_AUTHOR_RE = re.compile(r"^Co-authored-by: (?P<name>.+) <(?P<email>[^<>@\s]+@[^<>\s]+)>$", re.MULTILINE)


# --------------------------------------------------------------------------------------
# fixtures / helpers
# --------------------------------------------------------------------------------------


def git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env={**GIT_ENV, **(env or {})},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout.strip()


def commit(cwd: Path, message: str, *, signoff: bool = False, filename: str = "file.txt") -> str:
    target = cwd / filename
    target.write_text(target.read_text(encoding="utf-8") + message + "\n" if target.exists() else message + "\n",
                      encoding="utf-8")
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", *(("-s",) if signoff else ()), "-m", message)
    return git(cwd, "rev-parse", "HEAD")


def snapshot(path: Path) -> dict:
    """Everything a stray write would move: refs, reflogs, HEAD and the working tree."""
    refs = git(path, "for-each-ref", "--format=%(refname) %(objectname)")
    reflog = git(path, "reflog", "show", "--all", "--format=%H %gD %gs")
    head = git(path, "rev-parse", "HEAD")
    status = git(path, "status", "--porcelain")
    files = sorted(str(p.relative_to(path)) for p in path.rglob("*") if ".git" not in p.parts)
    return {"refs": refs, "reflog": reflog, "head": head, "status": status, "files": files}


class Fixture:
    def __init__(self, base: Path, fork: Path, head_sha: str, signed_sha: str) -> None:
        self.base = base
        self.fork = fork
        self.head_sha = head_sha
        self.signed_sha = signed_sha


@pytest.fixture()
def repos(tmp_path: Path) -> Fixture:
    """A clean working checkout plus a "fork" whose PR branch has one unsigned commit.

    The fork has two commits: ``base commit`` (signed off, shared with the base repo) and
    ``PR commit`` (no ``Signed-off-by``) on the PR branch — exactly the stalled shape.
    """
    base = tmp_path / "base"
    base.mkdir()
    git(base, "init", "-q", "-b", "main", ".")
    commit(base, "base commit", signoff=True)

    fork = tmp_path / "fork"
    fork.mkdir()
    git(fork, "init", "-q", "-b", "main", ".")
    commit(fork, "base commit", signoff=True)
    git(fork, "checkout", "-q", "-b", HEAD_BRANCH)
    head_sha = commit(fork, "PR commit: no signoff")
    # A second, fully signed-off branch — the "nothing to adopt" case.
    git(fork, "checkout", "-q", "-b", "all-signed", "main")
    signed_sha = commit(fork, "signed commit", signoff=True)
    git(fork, "checkout", "-q", HEAD_BRANCH)
    return Fixture(base=base, fork=fork, head_sha=head_sha, signed_sha=signed_sha)


def run_adopt(
    fixture: Fixture, *extra: str, pr: int = PR, workdir: Path | None = None, sha: str | None = None
):
    argv = [
        sys.executable,
        str(SCRIPT),
        str(pr),
        "--head-repo",
        str(fixture.fork),
        "--head-repo-full-name",
        FORK_SLUG,
        "--head-branch",
        HEAD_BRANCH,
        "--head-sha",
        sha or fixture.head_sha,
        "--head-label",
        f"{AUTHOR_LOGIN}:{HEAD_BRANCH}",
        "--author",
        AUTHOR,
        "--author-login",
        AUTHOR_LOGIN,
        "--title",
        ORIGINAL_TITLE,
        "--body",
        ORIGINAL_BODY,
        "--repo",
        REPO_SLUG,
        "--workdir",
        str(workdir or fixture.base),
        *extra,
    ]
    return subprocess.run(
        argv,
        cwd=str(fixture.base),
        env=GIT_ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# --------------------------------------------------------------------------------------
# plan generation
# --------------------------------------------------------------------------------------


def test_dry_run_plan_for_fork_pr(repos: Fixture):
    result = run_adopt(repos)

    assert result.returncode == 0, result.stderr
    plan = result.stdout
    assert f"/adopt plan for PR #{PR}" in plan
    assert "DRY RUN" in plan
    # how the head ref is fetched: the fork's clone URL plus the PR head branch
    assert f"git fetch --no-tags {repos.fork} +refs/heads/{HEAD_BRANCH}" in plan
    assert FORK_SLUG in plan  # the fork is shown with GitHub's capitalisation, not lowercased
    assert f"git fetch --no-tags origin refs/pull/{PR}/head" in plan  # documented fallback
    assert repos.head_sha in plan  # the head SHA pins the fetch
    # the rebase and the target branch
    assert "rebase --signoff" in plan
    assert f"git checkout -b adopted/{PR} FETCH_HEAD" in plan
    assert f"git push origin HEAD:refs/heads/adopted/{PR}" in plan
    # the new PR: original title unchanged, body template, original PR link
    assert ORIGINAL_TITLE in plan
    assert f"https://github.com/{REPO_SLUG}/pull/{PR}" in plan
    assert ORIGINAL_BODY.strip() in plan
    assert f"gh pr create --base main --head adopted/{PR}" in plan
    assert f"gh pr close {PR} --delete-branch=false" in plan


def test_json_plan_is_machine_readable(repos: Fixture):
    result = run_adopt(repos, "--json")

    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan["ok"] is True
    assert plan["pr"] == PR
    assert plan["is_fork"] is True
    assert plan["target_branch"] == f"adopted/{PR}"
    assert plan["title"] == ORIGINAL_TITLE
    assert plan["base"] == "main"
    assert plan["commit_count"] == 1 and plan["unsigned_count"] == 1
    assert plan["rebase_command"].endswith("rebase --signoff " + plan["base_ref"])
    assert plan["pr_body"].startswith(f"## Adopted from #{PR}")
    assert len(plan["steps"]) >= 6


def test_plan_never_forces_a_push_and_only_targets_adopted(repos: Fixture):
    result = run_adopt(repos, "--json")

    plan = json.loads(result.stdout)
    assert plan["push_command"] == f"git push origin HEAD:refs/heads/adopted/{PR}"
    assert "--force" not in plan["push_command"]
    assert plan["target_branch"] == f"adopted/{PR}"
    assert "main" not in plan["push_command"].split(":")[-1]


# --------------------------------------------------------------------------------------
# refusals (exit code 2)
# --------------------------------------------------------------------------------------


def test_refuses_same_repo_pr(repos: Fixture):
    result = run_adopt(
        repos, "--head-repo", f"https://github.com/{REPO_SLUG}.git", "--head-repo-full-name", REPO_SLUG
    )

    assert result.returncode == 2, result.stdout
    assert "not from a fork" in result.stderr
    assert "fix-dco" in result.stderr  # points at the same-repo workflow instead


def test_refuses_pr_whose_commits_are_all_signed(repos: Fixture):
    result = run_adopt(repos, "--head-branch", "all-signed", sha=repos.signed_sha)

    assert result.returncode == 2, result.stdout
    assert "Signed-off-by" in result.stderr
    assert "nothing to adopt" in result.stderr


def test_refuses_when_target_branch_exists(repos: Fixture):
    git(repos.base, "branch", f"adopted/{PR}")

    result = run_adopt(repos)

    assert result.returncode == 2, result.stdout
    assert f"adopted/{PR} already exists" in result.stderr
    # and nothing was built on top of the branch that is already there
    assert git(repos.base, "rev-parse", f"adopted/{PR}") != repos.head_sha


def test_refuses_when_target_branch_exists_on_origin(repos: Fixture):
    git(repos.base, "update-ref", f"refs/remotes/origin/adopted/{PR}", git(repos.base, "rev-parse", "HEAD"))

    result = run_adopt(repos)

    assert result.returncode == 2, result.stdout
    assert f"adopted/{PR} already exists" in result.stderr


def test_refuses_dirty_worktree(repos: Fixture):
    (repos.base / "file.txt").write_text("uncommitted local edit\n", encoding="utf-8")

    result = run_adopt(repos)

    assert result.returncode == 2, result.stdout
    assert "dirty" in result.stderr


def test_refusal_writes_a_comment_file_and_json(repos: Fixture, tmp_path: Path):
    comment = tmp_path / "refusal.md"

    result = run_adopt(
        repos,
        "--json",
        "--comment-out",
        str(comment),
        "--head-repo",
        f"https://github.com/{REPO_SLUG}.git",
        "--head-repo-full-name",
        REPO_SLUG,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False and payload["refused"] is True
    assert "refused" in comment.read_text(encoding="utf-8")
    assert "not from a fork" in comment.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# the credit line
# --------------------------------------------------------------------------------------


def test_co_authored_by_line_format(repos: Fixture):
    result = run_adopt(repos, "--json")
    plan = json.loads(result.stdout)
    body = plan["pr_body"]

    matches = CO_AUTHOR_RE.findall(body)
    lines = [line for line in body.splitlines() if line.startswith("Co-authored-by:")]
    assert lines == [f"Co-authored-by: {AUTHOR}"], lines
    assert matches == [("Taher Ezzi", "taherezzi.dev@gmail.com")]
    assert plan["co_authored_by"] == [AUTHOR]

    # the body must also carry the original body verbatim, the link, and the scope note
    assert ORIGINAL_BODY.strip() in body
    assert f"https://github.com/{REPO_SLUG}/pull/{PR}" in body
    assert "The only change made by the adopter is the `Signed-off-by:` trailer" in body
    assert f"the original author" in body and f"@{AUTHOR_LOGIN}" in body
    # trailers live at the end of the body, where a squash commit message would keep them
    assert body.rstrip().splitlines()[-1].startswith("_Adopted via")


def test_co_author_argument_adds_an_extra_trailer(repos: Fixture):
    result = run_adopt(repos, "--json", "--co-author", "Second Author <second@example.com>")

    plan = json.loads(result.stdout)
    assert plan["co_authored_by"] == [AUTHOR, "Second Author <second@example.com>"]
    assert "Co-authored-by: Second Author <second@example.com>" in plan["pr_body"]


def test_author_email_falls_back_to_the_login(repos: Fixture):
    result = run_adopt(repos, "--json", "--author", "TaherEzzi")

    plan = json.loads(result.stdout)
    assert plan["co_authored_by"] == [f"{AUTHOR_LOGIN} <{AUTHOR_LOGIN}@users.noreply.github.com>"]


# --------------------------------------------------------------------------------------
# the dry run must not write anything
# --------------------------------------------------------------------------------------


def test_dry_run_performs_no_writes(repos: Fixture, tmp_path: Path):
    before_base = snapshot(repos.base)
    before_fork = snapshot(repos.fork)

    result = run_adopt(repos, "--body-out", str(tmp_path / "body.md"), "--comment-out", str(tmp_path / "comment.md"))

    assert result.returncode == 0, result.stderr
    assert snapshot(repos.base) == before_base
    assert snapshot(repos.fork) == before_fork
    # no adopted branch, no fetched fork remote, no rebase in flight
    assert f"adopted/{PR}" not in git(repos.base, "for-each-ref", "--format=%(refname)")
    assert "refs/remotes/adopt" not in git(repos.base, "for-each-ref", "--format=%(refname)")
    assert git(repos.base, "rev-parse", "HEAD") == before_base["head"]
    assert git(repos.fork, "rev-parse", HEAD_BRANCH) == repos.head_sha
    # the fork's own history is untouched: still exactly one unsigned commit
    assert "Signed-off-by" not in git(repos.fork, "log", "-1", "--format=%B")


def test_dry_run_does_not_create_the_body_file_inside_the_repo(repos: Fixture):
    before = snapshot(repos.base)

    result = run_adopt(repos)

    assert result.returncode == 0
    assert snapshot(repos.base) == before


def test_comment_fence_is_longer_than_any_fence_in_the_original_body(repos: Fixture, tmp_path: Path):
    """A PR body containing a ```` block must not be able to break out of the posted comment."""
    body = "lead in\n\n````text\nnested block\n````\n\ntail\n"
    comment = tmp_path / "comment.md"

    result = run_adopt(repos, "--body", body, "--comment-out", str(comment))

    assert result.returncode == 0, result.stderr
    text = comment.read_text(encoding="utf-8")
    assert "`````text" in text  # one backtick more than the longest run inside
    assert "nested block" in text


# --------------------------------------------------------------------------------------
# --apply: executed against a local bare "origin", so still offline
# --------------------------------------------------------------------------------------


class ApplyFixture(Fixture):
    def __init__(self, base: Path, fork: Path, origin: Path, seed: Path, head_sha: str) -> None:
        super().__init__(base=base, fork=fork, head_sha=head_sha, signed_sha=head_sha)
        self.origin = origin
        self.seed = seed


CONTRIBUTOR = ("Orig Author", "orig@example.com")


@pytest.fixture()
def apply_repos(tmp_path: Path) -> ApplyFixture:
    """base clone + fork clone + a local bare origin: a full, network-free apply target."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main", ".")
    (seed / "file.txt").write_text("line1\nline2\n", encoding="utf-8")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-s", "-m", "base commit")
    git(seed, "remote", "add", "origin", str(origin))
    git(seed, "push", "-q", "-u", "origin", "main")

    base = tmp_path / "base"
    git(tmp_path, "clone", "-q", "-b", "main", str(origin), str(base))
    fork = tmp_path / "fork"
    git(tmp_path, "clone", "-q", "-b", "main", str(origin), str(fork))
    git(fork, "checkout", "-q", "-b", HEAD_BRANCH)
    # the contributor authors the PR commit; a different local user commits it
    (fork / "file.txt").write_text("FORK VERSION\nline2\n", encoding="utf-8")
    git(fork, "add", "-A")
    git(
        fork,
        "commit",
        "-q",
        "-m",
        "PR commit: no signoff",
        env={"GIT_AUTHOR_NAME": CONTRIBUTOR[0], "GIT_AUTHOR_EMAIL": CONTRIBUTOR[1]},
    )
    return ApplyFixture(
        base=base, fork=fork, origin=origin, seed=seed, head_sha=git(fork, "rev-parse", "HEAD")
    )


def run_apply(fixture: ApplyFixture, tmp_path: Path, *extra: str):
    return run_adopt(
        fixture,
        "--apply",
        "--adopter",
        "Ikalus1988",
        "--body-out",
        str(tmp_path / "body.md"),
        "--comment-out",
        str(tmp_path / "notice.md"),
        "--summary-out",
        str(tmp_path / "summary.json"),
        *extra,
    )


def test_apply_pushes_a_signed_branch_and_keeps_the_contributor_as_author(apply_repos: ApplyFixture, tmp_path: Path):
    result = run_apply(apply_repos, tmp_path)

    assert result.returncode == 0, result.stderr
    # the branch is on origin, signed off by the adopter…
    message = git(tmp_path, "--git-dir", str(apply_repos.origin), "log", "-1", "--format=%B", f"adopted/{PR}")
    assert "Signed-off-by: Ikalus1988 <Ikalus1988@users.noreply.github.com>" in message
    # …while the contributor stays the author and only the trailer changed
    author = git(tmp_path, "--git-dir", str(apply_repos.origin), "log", "-1", "--format=%an <%ae>", f"adopted/{PR}")
    assert author == f"{CONTRIBUTOR[0]} <{CONTRIBUTOR[1]}>"
    assert git(tmp_path, "--git-dir", str(apply_repos.origin), "log", "-1", "--format=%s", f"adopted/{PR}") == (
        "PR commit: no signoff"
    )
    # the tree is byte-for-byte the contributor's work
    tree = git(tmp_path, "--git-dir", str(apply_repos.origin), "show", f"adopted/{PR}:file.txt")
    assert tree == "FORK VERSION\nline2"

    # the fork was never written to
    assert git(apply_repos.fork, "rev-parse", HEAD_BRANCH) == apply_repos.head_sha
    assert "Signed-off-by" not in git(apply_repos.fork, "log", "-1", "--format=%B")

    # outputs for the workflow
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["applied"] is True and summary["target_branch"] == f"adopted/{PR}"
    assert summary["authors_preserved"] is True and summary["dropped_empty"] == 0
    assert CO_AUTHOR_RE.search((tmp_path / "body.md").read_text(encoding="utf-8"))
    assert "{{NEW_PR_URL}}" in (tmp_path / "notice.md").read_text(encoding="utf-8")


def test_apply_refuses_when_origin_is_the_fork(apply_repos: ApplyFixture, tmp_path: Path):
    """The fork is read-only for /adopt: a checkout whose origin *is* the fork must not push."""
    git(apply_repos.base, "remote", "set-url", "origin", str(apply_repos.fork))

    result = run_apply(apply_repos, tmp_path)

    assert result.returncode == 1, result.stdout
    assert "read-only" in result.stderr
    refs = git(tmp_path, "--git-dir", str(apply_repos.origin), "for-each-ref", "--format=%(refname)")
    assert f"adopted/{PR}" not in refs
    # and the fork itself gained no branch either
    assert f"adopted/{PR}" not in git(apply_repos.fork, "for-each-ref", "--format=%(refname)")


def test_apply_stops_on_conflict_and_pushes_nothing(apply_repos: ApplyFixture, tmp_path: Path):
    # main moves so the contributor's hunk no longer applies
    (apply_repos.seed / "file.txt").write_text("MAIN VERSION\nline2\n", encoding="utf-8")
    git(apply_repos.seed, "commit", "-q", "-s", "-am", "main edits line1")
    git(apply_repos.seed, "push", "-q", "origin", "main")
    git(apply_repos.base, "fetch", "-q", "origin")

    result = run_apply(apply_repos, tmp_path)

    assert result.returncode == 1, result.stdout
    assert "conflict" in result.stderr
    assert "file.txt" in result.stderr
    refs = git(tmp_path, "--git-dir", str(apply_repos.origin), "for-each-ref", "--format=%(refname)")
    assert f"adopted/{PR}" not in refs  # nothing was pushed
    assert git(apply_repos.base, "rev-parse", "--abbrev-ref", "HEAD") == "main"  # checkout restored
    assert f"adopted/{PR}" not in git(apply_repos.base, "for-each-ref", "--format=%(refname)")
