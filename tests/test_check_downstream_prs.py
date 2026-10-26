#!/usr/bin/env python3
"""The downstream-PR check: "none" must be an observation, not a failed command."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import check_downstream_prs as cdp  # noqa: E402


class GhStub:
    """Records the argv and returns a canned CompletedProcess."""

    def __init__(self, stdout: str = "[]", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


def test_no_downstream_pr_is_a_clean_zero(monkeypatch, capsys):
    stub = GhStub("[]")
    monkeypatch.setattr(cdp.subprocess, "run", stub)
    assert cdp.main(["feature"]) == 0
    assert "no open PR is based on 'feature'" in capsys.readouterr().out
    assert stub.calls and "--base" in stub.calls[0]
    assert stub.calls[0][stub.calls[0].index("--base") + 1] == "feature"


def test_a_downstream_pr_is_one(monkeypatch, capsys):
    row = [{"number": 123, "title": "child of feature", "headRefName": "child"}]
    stub = GhStub(json.dumps(row))
    monkeypatch.setattr(cdp.subprocess, "run", stub)
    assert cdp.main(["feature"]) == 1
    out = capsys.readouterr().out
    assert "#123" in out and "child" in out
    assert "will close them" in out


def test_a_failed_gh_is_two_not_zero(monkeypatch, capsys):
    stub = GhStub(stderr="HTTP 401: Bad credentials", returncode=1)
    monkeypatch.setattr(cdp.subprocess, "run", stub)
    assert cdp.main(["feature"]) == 2
    err = capsys.readouterr().err
    assert "COULD NOT CHECK" in err
    assert "Do not read this as 'no downstream PRs'" in err


def test_unreadable_json_is_two(monkeypatch, capsys):
    stub = GhStub("not json")
    monkeypatch.setattr(cdp.subprocess, "run", stub)
    assert cdp.main(["feature"]) == 2
    assert "unreadable JSON" in capsys.readouterr().err


def test_repo_is_passed_through(monkeypatch):
    stub = GhStub("[]")
    monkeypatch.setattr(cdp.subprocess, "run", stub)
    assert cdp.main(["feature", "--repo", "owner/name"]) == 0
    argv = stub.calls[0]
    assert "--repo" in argv and argv[argv.index("--repo") + 1] == "owner/name"
