#!/usr/bin/env python3
"""Two gates that only failed on *somebody else's machine* (#2001).

The issue behind these is the shape this repository keeps hitting: a check whose verdict depends on the
environment it runs in, so it passes where CI runs and fails where users are.

1. **The one-line installer could not download at all without `curl`.** `bootstrap.sh` defined
   `fetch()` for curl *or* wget and then called `curl` directly in the download loop — the helper was
   dead code, so on a wget-only machine every mirror "failed" while the script held the function that
   would have worked. (The macOS half of the same defect — a bare `timeout`, which GNU ships and macOS
   does not — was fixed earlier and is pinned here too.)
2. **The merge-conflict fixture assumed the base branch is `master` or `main`.**
   `git switch -q master || git switch -q main` dies with `fatal: invalid reference: main` on a machine
   with `init.defaultBranch=dev`, before any conflict exists, and the benchmark reports "setup failed"
   for an environment reason. Measured 2026-09-25: it now works under `dev`, `trunk`, `main` and
   `master`, and the test runs all four rather than trusting one.

Note on naming: the issue proposes `tests/test_issue_2001_environment_gates.py` and PR #2002 carries a
version of it, still open and conflicted. This file is deliberately separate so a later merge of that PR
does not leave two copies of the same assertions.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "integrations" / "agent-autostart" / "bootstrap.sh"
FIXTURE = REPO / "bench" / "fixtures" / "git-merge-conflict" / "setup.sh"

pytestmark = pytest.mark.skipif(
    not shutil.which("git"), reason="these gates drive git; without it they prove nothing"
)


# ── 1. the fixture must not assume a branch name ────────────────────────────────────
def _isolated_git_env(tmp_path: Path, default_branch: str) -> dict:
    """A git environment whose only configured default branch is `default_branch`."""
    config = tmp_path / "gitconfig"
    config.write_text(f"[init]\n\tdefaultBranch = {default_branch}\n", encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "GIT_CONFIG_GLOBAL": str(config),
        "GIT_CONFIG_NOSYSTEM": "1",       # the host's /etc/gitconfig must not leak in
        "HOME": str(tmp_path),            # nothing else reaches for the developer's config
    })
    return env


@pytest.mark.parametrize("default_branch", ["dev", "trunk", "main", "master"])
def test_the_merge_conflict_fixture_works_whatever_the_default_branch_is(default_branch, tmp_path):
    """The fixture's job is to create a conflict; the branch name is incidental.

    Under `init.defaultBranch=dev` the old `switch master || switch main` exited before creating one —
    the benchmark then reported a fixture failure that had nothing to do with the benchmark.
    """
    workdir = tmp_path / "work"
    proc = subprocess.run(["bash", str(FIXTURE), str(workdir)],
                          capture_output=True, text=True, env=_isolated_git_env(tmp_path, default_branch))
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"

    base = subprocess.run(["git", "-C", str(workdir / "repo"), "symbolic-ref", "--short", "HEAD"],
                          capture_output=True, text=True, env=_isolated_git_env(tmp_path, default_branch))
    assert base.stdout.strip() == default_branch, (
        f"the fixture left the repo on {base.stdout.strip()!r}, not the initialised branch "
        f"{default_branch!r} — it is creating its state on a branch it made up"
    )
    status = subprocess.run(["git", "-C", str(workdir / "repo"), "status", "--porcelain"],
                            capture_output=True, text=True, env=_isolated_git_env(tmp_path, default_branch))
    assert "UU config.txt" in status.stdout, (
        f"no conflict was produced, which is the only thing this fixture exists for: {status.stdout!r}"
    )


def test_the_fixture_asks_git_for_the_branch_it_created():
    """Structural half: the fix is 'ask', and a hardcoded name is what broke it."""
    source = "\n".join(line for line in FIXTURE.read_text(encoding="utf-8").splitlines()
                       if not line.strip().startswith("#"))
    assert "symbolic-ref --short HEAD" in source, source
    assert not re.search(r"switch -q (master|main)\b", source), (
        "a branch name is hardcoded again — `git init` honours init.defaultBranch (#2001)"
    )


# ── 2. the installer must use whichever fetcher exists ──────────────────────────────
def _bootstrap_code() -> str:
    """The script's lines with comments removed — this repo has had four tests satisfied by their own
    explanatory comments, and the comments here quote `curl` on purpose."""
    return "\n".join(line for line in BOOTSTRAP.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def test_the_download_loop_calls_the_fetcher_rather_than_curl():
    """The call site must go through the fetcher, and the timeout must wrap an *executable*.

    Both halves have been wrong here. First the loop called `curl` directly while `fetch()` sat
    unused, so a wget-only machine could not install. Then — fixing that — `with_timeout fetch …`
    looked right and failed on every machine that *has* `timeout`: `timeout` runs a program, and
    `fetch` is a shell function, so the wrapper could not execute it.
    """
    code = _bootstrap_code()
    download_calls = [line.strip() for line in code.splitlines() if '"$DIR/$f"' in line]
    assert download_calls, "the download call is gone"
    for line in download_calls:
        assert re.search(r"\bfetch ", line), f"the download bypasses the fetcher: {line}"
        assert "curl" not in line, f"the download calls curl directly again: {line}"
    assert "with_timeout fetch" not in code, (
        "`timeout` cannot run a shell function — the wrapper belongs inside fetch(), around the "
        "fetcher binary"
    )
    assert code.count("with_timeout curl") == 1, "the curl fetcher must wrap the wrapper exactly once"
    assert code.count("with_timeout wget") == 1, "the wget fetcher must wrap the wrapper exactly once"


def test_the_fetcher_carries_its_own_timeouts():
    """The timeouts used to sit at the call site, which only the curl path ever reached."""
    code = _bootstrap_code()
    assert "--max-time" in code and "--connect-timeout" in code, code
    assert re.search(r"wget[^\n]*--timeout", code), (
        "the wget branch has no timeout, so a stalled transfer hangs there forever"
    )


def test_a_wget_only_machine_can_download(tmp_path):
    """Behavioural: PATH contains no curl, a stub wget serves a local mirror, and the three files must
    land. This is the claim the previous fix only *appeared* to make."""
    mirror = tmp_path / "mirror"
    files = ("install_misakanet_agent.py", "checkpoint_reminder.py", "checkpoint_reminder.mjs", "prompt.md")
    for name in files:
        target = mirror / "integrations" / "agent-autostart" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {name}\n", encoding="utf-8")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    # a wget good enough for `wget -q --timeout=25 --tries=1 -O OUT URL`
    (bindir / "wget").write_text(
        '#!/bin/sh\nout=""\nwhile [ $# -gt 0 ]; do\n'
        '  case "$1" in -O) out="$2"; shift 2 ;; --timeout=*|--tries=*|-q) shift ;; *) url="$1"; shift ;; esac\n'
        'done\ncp "${url#file://}" "$out"\n', encoding="utf-8")
    (bindir / "wget").chmod(0o755)
    # the installer itself is out of scope here; stop at the hand-over
    (bindir / "python3").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (bindir / "python3").chmod(0o755)
    for name in ("sed", "mkdir", "cp", "rm", "mktemp", "tr", "sh"):
        found = shutil.which(name)
        if found:
            (bindir / name).symlink_to(found)

    setup_dir = tmp_path / "setup"
    env = {
        "PATH": str(bindir),                       # no curl anywhere: PATH is the only input
        "HOME": str(tmp_path),
        "MISAKANET_RAW_BASE": f"file://{mirror}",
        "MISAKANET_RAW_ONLY": "1",                 # one source, so the stub wget is the only path
        "MISAKANET_SETUP_DIR": str(setup_dir),
    }
    # absolute path: with `env=` the child's own PATH is what resolves the program, and this PATH
    # deliberately contains no shell.
    bash = shutil.which("bash") or "/bin/bash"
    proc = subprocess.run([bash, str(BOOTSTRAP), "--dry-run"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    missing = [name for name in files if not (setup_dir / name).is_file()]
    assert missing == [], (
        f"a wget-only machine still cannot install; missing {missing}\n{proc.stdout}"
    )


def test_the_macos_timeout_assumption_is_gone():
    """macOS ships neither `timeout` nor `gtimeout`; wrapping the download in it broke every mirror
    there, and the failure then reported the *network* as the cause."""
    code = _bootstrap_code()
    assert "command -v timeout" in code, code
    assert re.search(r"with_timeout\(\) \{ \"\$@\"; \}", code), (
        "the fallback that runs the command unguarded is gone, so macOS is broken again"
    )
    assert not re.search(r"(?m)^\s*timeout \d+ ", code), (
        "a bare `timeout` invocation is back — GNU coreutils only (#2001)"
    )
