#!/usr/bin/env python3
"""Tests that spawn a child must give it a PATH that works on the OS they run on (ci-cross-platform).

`PATH="/usr/bin:/bin"` was copied into five test files as a determinism habit. On Linux it is harmless:
the children are launched as `sys.executable` by absolute path and the scripts under test use the
standard library. On Windows it is fatal in a way that reads like a code failure:

    urllib.error.URLError: <urlopen error [WinError 10106] The requested service provider could not
    be loaded or initialized>

Winsock lives in `System32`, so a child whose PATH excludes the system directories cannot open a socket
at all. Measured on the `windows-latest` legs before this fix (2026-09-25, PR #2195's head): **50
failures per leg** across six files, every one of them environment rather than code —

    test_workers_builds_watch.py          16
    test_cf_diagnostics_builds_step.py    15
    test_cf_diagnostics_query.py           7
    test_cf_diagnostics_kv_step.py         6
    test_d1_backup_guard.py                5
    test_worker_compat_dates.py            1

`tests/subprocess_env.py` keeps the POSIX value where it is safe and inherits the host PATH on Windows.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))

import subprocess_env  # noqa: E402
from subprocess_env import POSIX_PATH, child_env  # noqa: E402

# The files that spawn a child and used to hardcode a POSIX PATH.
PATCHED = (
    "test_workers_builds_watch.py",
    "test_cf_diagnostics_builds_step.py",
    "test_cf_diagnostics_query.py",
    "test_cf_diagnostics_kv_step.py",
    "test_automation_output_audit.py",
)


def test_posix_children_keep_the_deterministic_path(monkeypatch):
    monkeypatch.setattr(subprocess_env.os, "name", "posix")
    assert child_env()["PATH"] == POSIX_PATH


def test_windows_children_inherit_the_host_path(monkeypatch):
    """The whole point: a Windows child needs `System32` on PATH or Winsock cannot load."""
    monkeypatch.setattr(subprocess_env.os, "name", "nt")
    monkeypatch.setenv("PATH", r"C:\Windows\System32;C:\Windows")
    assert child_env()["PATH"] == r"C:\Windows\System32;C:\Windows"


def test_windows_children_still_get_a_nonempty_path_when_the_host_has_none(monkeypatch):
    monkeypatch.setattr(subprocess_env.os, "name", "nt")
    monkeypatch.delenv("PATH", raising=False)
    assert isinstance(child_env()["PATH"], str)   # never None: `env["PATH"] = None` raises in subprocess


def test_the_host_environment_is_inherited(monkeypatch):
    """A fresh dict of two keys is what broke the windows legs twice: these children talk HTTP to a stub
    server, and Windows needs its own system variables to initialise Winsock at all.

    Asserted with a **marker variable the test sets**, not with `SystemRoot`: the runner's environment is
    not something this repository controls, and the first version of this test failed on Windows with
    `KeyError: 'SystemRoot'` — an assumption about somebody else's environment, which is the same mistake
    the module exists to fix. What the contract actually promises is inheritance.
    """
    monkeypatch.setenv("MISAKANET_CHILD_ENV_MARKER", "inherited")
    assert child_env()["MISAKANET_CHILD_ENV_MARKER"] == "inherited"


def _get(env: dict, name: str) -> str | None:
    """Read `name` the way the *platform* spells it, not the way the caller typed it.

    Windows environment variables are case-insensitive and Python reports the ones it inherits in upper
    case: `monkeypatch.setenv("SystemRoot", …)` puts `SYSTEMROOT` into `os.environ`, so a plain
    `env.get("SystemRoot")` is `None` there. That is not the contract failing — the child does receive
    the variable — it is the assertion reading it in a case the OS never uses. Measured 2026-09-25: this
    one line failed all three `windows-latest` legs with `AssertionError: SystemRoot / assert None ==
    'marker-value'`.
    """
    if name in env:
        return env[name]
    wanted = name.lower()
    for key, value in env.items():
        if key.lower() == wanted:
            return value
    return None


def test_the_child_keeps_the_system_variables_it_is_given(monkeypatch):
    """Whatever the host provides — `SystemRoot` on Windows, `HOME` elsewhere — must reach the child,
    because the fix was precisely that "build a fresh env for determinism" dropped it.

    Read back case-insensitively: the question is whether the variable is there, not whether the runner
    spells it the way this test does.
    """
    for name in ("SystemRoot", "windir", "HOME", "LANG"):
        monkeypatch.setenv(name, "marker-value")
    env = child_env()
    for name in ("SystemRoot", "windir", "HOME", "LANG"):
        assert _get(env, name) == "marker-value", f"{name} did not reach the child: {sorted(env)[:5]}…"


def test_the_lookup_is_case_insensitive_on_purpose():
    """The guard for the line above: `SystemRoot` on Windows is `SYSTEMROOT` in `os.environ`."""
    assert _get({"SYSTEMROOT": "x"}, "SystemRoot") == "x"
    assert _get({"SystemRoot": "x"}, "SYSTEMROOT") == "x"
    assert _get({}, "SystemRoot") is None


def test_overrides_win(monkeypatch):
    monkeypatch.setattr(subprocess_env.os, "name", "posix")
    env = child_env({"A": 1}, B=2)
    assert env["A"] == "1" and env["B"] == "2"     # values are stringified for the child
    assert child_env({"PATH": "/only/this"})["PATH"] == "/only/this"


@pytest.mark.parametrize("name", PATCHED)
def test_no_test_file_hardcodes_a_posix_path_for_a_child(name):
    """The regression this file exists for: the literal coming back into a spawning test."""
    text = (REPO / "tests" / name).read_text(encoding="utf-8")
    assert '"PATH": "/usr/bin:/bin"' not in text, (
        f"{name} hands a child a POSIX-only PATH again — on Windows that stops Winsock loading and "
        "every socket call in the child fails with WinError 10106"
    )
    assert "child_env" in text, f"{name} no longer builds its child environment with child_env"


def test_the_docstring_names_the_measured_failure():
    """A helper whose reason is only in a commit message gets deleted by the next tidy-up."""
    text = (REPO / "tests" / "subprocess_env.py").read_text(encoding="utf-8")
    assert "WinError 10106" in text, text[:200]
    assert re.search(r"[Ww]insock", text), text[:200]
