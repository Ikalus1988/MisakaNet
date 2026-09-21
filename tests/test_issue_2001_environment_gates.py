#!/usr/bin/env python3
"""Regression tests for three environment-dependent defects found on macOS (#2001).

Each of these passed on GitHub CI and failed on a stock macOS machine, because all
three depend on local environment rather than on the repository contents:

* `timeout` is GNU coreutils; macOS ships neither it nor `gtimeout`.
* `init.defaultBranch` is honoured by `git init`, so a machine set to `dev` has
  neither `master` nor `main`.
* `core.ignorecase` is true on macOS/Windows, so an unanchored `STATUS.md` pattern
  also matches `docs/integrations/status.md`.

The point of testing them here is that a gate which only runs on the CI image cannot
see any of them.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BOOTSTRAP = REPO / "integrations" / "agent-autostart" / "bootstrap.sh"
INTEGRATION = REPO / "integrations" / "agent-autostart"
FIXTURE_SETUP = REPO / "bench" / "fixtures" / "git-merge-conflict" / "setup.sh"
ORCHESTRATOR = REPO / "bench" / "phase-b" / "orchestrator.py"

BASH = shutil.which("bash")


def test_bootstrap_does_not_require_gnu_timeout(tmp_path):
    """macOS has no `timeout`; the download must still work, and must actually happen."""
    if not BASH:
        pytest.skip("bash unavailable")
    setup_dir = tmp_path / "setup"
    env = dict(
        os.environ,
        MISAKANET_RAW_BASE=f"file://{REPO}",
        MISAKANET_RAW_ONLY="1",
        MISAKANET_SETUP_DIR=str(setup_dir),
        # Reproduce the stock-macOS case: no GNU coreutils on PATH at all.
        PATH="/usr/bin:/bin",
    )
    result = subprocess.run(
        [BASH, str(BOOTSTRAP), "--home", str(tmp_path / "home"),
         "--only", "claude", "--no-register"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(tmp_path), timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (setup_dir / "prompt.md").is_file(), result.stdout
    assert "unbound variable" not in (result.stdout + result.stderr)


def test_bootstrap_still_works_where_timeout_does_exist(tmp_path):
    """The inverse of the test above, and the case a first attempt at this fix broke.

    `timeout` cannot execute a shell function, it execs its argument. Wrapping the call to the
    `fetch()` helper therefore made every download fail on the machines that *do* have GNU
    coreutils (which is what the CI runner has, so the bug showed up as a red audit job). The
    binary has to be wrapped inside `fetch()`, around curl or wget.
    """
    if not BASH:
        pytest.skip("bash unavailable")
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    # A stand-in that behaves like `timeout`: drop the duration, exec the rest.
    shim = shim_dir / "timeout"
    shim.write_text('#!/bin/sh\nshift\nexec "$@"\n', encoding="utf-8")
    shim.chmod(0o755)

    setup_dir = tmp_path / "setup"
    env = dict(
        os.environ,
        MISAKANET_RAW_BASE=f"file://{REPO}",
        MISAKANET_RAW_ONLY="1",
        MISAKANET_SETUP_DIR=str(setup_dir),
        PATH=f"{shim_dir}:/usr/bin:/bin",
    )
    result = subprocess.run(
        [BASH, str(BOOTSTRAP), "--home", str(tmp_path / "home"),
         "--only", "claude", "--no-register"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(tmp_path), timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (setup_dir / "prompt.md").is_file(), result.stdout


def test_bootstrap_survives_a_multibyte_char_after_an_expansion(tmp_path):
    """`$DIR，` parses as the variable `DIR\\xef` under bash 3.2 and aborts under `set -u`.

    bash 3.2 is what /bin/bash is on macOS and it is still the interpreter the documented
    `curl ... | bash` one-liner lands in, so this is the default path, not an edge case.
    """
    if not BASH:
        pytest.skip("bash unavailable")
    version = subprocess.run([BASH, "--version"], capture_output=True, text=True).stdout
    if "3.2" not in version:
        pytest.skip(f"this failure mode is specific to bash 3.2 (found: {version.splitlines()[0]})")

    setup_dir = tmp_path / "setup"
    env = dict(
        os.environ,
        MISAKANET_RAW_BASE=f"file://{REPO}",
        MISAKANET_RAW_ONLY="1",
        MISAKANET_SETUP_DIR=str(setup_dir),
        PATH="/usr/bin:/bin",
    )
    result = subprocess.run(
        [BASH, str(BOOTSTRAP), "--home", str(tmp_path / "home"),
         "--only", "claude", "--no-register"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(tmp_path), timeout=120,
    )
    assert "unbound variable" not in (result.stdout + result.stderr), result.stderr


def test_no_shell_script_glues_a_multibyte_char_to_an_expansion():
    """The bug class, not just the one instance: `$VAR` immediately followed by a non-ASCII byte.

    bash 3.2 folds the following bytes into the variable name, so the expansion silently
    becomes a different (usually unset) variable.
    """
    files = subprocess.run(["git", "ls-files", "*.sh", "*.bash"],
                           cwd=REPO, capture_output=True, text=True, check=True).stdout.split()
    assert files, "expected to find shell scripts to scan"
    pattern = re.compile(rb"\$[A-Za-z_][A-Za-z0-9_]*[\x80-\xff]")
    offenders = []
    for name in files:
        raw = (REPO / name).read_bytes()
        for lineno, line in enumerate(raw.split(b"\n"), 1):
            # A comment may quote the bug to explain it; only executable lines matter.
            stripped = line.lstrip()
            if stripped.startswith(b"#"):
                continue
            match = pattern.search(line)
            if match:
                offenders.append(f"{name}:{lineno}: {line.decode('utf-8', 'replace').strip()}")
    assert not offenders, (
        "these expansions are followed by a multibyte character, so bash 3.2 reads the "
        "variable name as `NAME\\xNN`:\n  " + "\n  ".join(offenders)
    )


def test_the_merge_conflict_fixture_ignores_the_configured_default_branch(tmp_path):
    """`git init` honours init.defaultBranch, so a `dev` machine has no `master`/`main`.

    The fixture used to switch to `master`, fall back to `main`, and die with
    "fatal: invalid reference: main" before creating any conflict.
    """
    if not BASH:
        pytest.skip("bash unavailable")
    setup_script = FIXTURE_SETUP.read_text(encoding="utf-8")
    assert "switch -q master" not in setup_script and "switch -q main" not in setup_script, (
        "the fixture must pin its own branch rather than guess the machine's"
    )
    assert re.search(r"git .*init[^\n]*-b\s+\S+", setup_script), (
        "`git init` must pin the initial branch explicitly"
    )


@pytest.mark.parametrize("default_branch", ["dev", "trunk", "main", "master"])
def test_the_merge_conflict_fixture_works_on_any_default_branch(default_branch):
    """Run the real fixture under each `init.defaultBranch` a machine might be configured with."""
    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), "--fixture", "git-merge-conflict", "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=REPO, timeout=120,
        env=dict(os.environ, GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="init.defaultBranch",
                 GIT_CONFIG_VALUE_0=default_branch),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"status": "PASS"' in result.stdout, result.stdout


def test_the_status_pattern_is_root_anchored(tmp_path):
    """A bare `STATUS.md` also matches `docs/integrations/status.md` where ignorecase is on."""
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "\n/STATUS.md\n" in ignore, "the status pattern must be root-anchored"
    assert "\nSTATUS.md\n" not in ignore, (
        "an unanchored STATUS.md matches docs/integrations/status.md on macOS and Windows, "
        "leaving that tracked document both ignored and committed"
    )


def test_the_root_status_snapshot_is_still_ignored(tmp_path):
    """The anchor must not have traded one bug for another: root STATUS.md stays ignored."""
    scratch = tmp_path / "repo"
    scratch.mkdir()
    for cmd in (["init", "-q", "-b", "base"], ["config", "user.email", "t@example.com"],
                ["config", "user.name", "t"]):
        subprocess.run(["git", *cmd], cwd=scratch, check=True, capture_output=True)
    (scratch / ".gitignore").write_text((REPO / ".gitignore").read_text(encoding="utf-8"),
                                        encoding="utf-8")
    (scratch / "STATUS.md").write_text("local snapshot\n", encoding="utf-8")
    (scratch / "docs" / "integrations").mkdir(parents=True)
    (scratch / "docs" / "integrations" / "status.md").write_text(
        "committed doc\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", "STATUS.md", "docs/integrations/status.md"],
                   cwd=scratch, check=True, capture_output=True)

    ignored = subprocess.run(["git", "-c", "core.ignorecase=true", "check-ignore", "--no-index",
                              "STATUS.md", "docs/integrations/status.md"],
                             cwd=scratch, capture_output=True, text=True)
    assert "STATUS.md" in ignored.stdout, "the root snapshot must stay ignored"
    assert "docs/integrations/status.md" not in ignored.stdout, (
        "the tracked document must not be ignored"
    )
