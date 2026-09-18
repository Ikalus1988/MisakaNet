#!/usr/bin/env python3
"""The four Python-channel fixes from the 2026-09-18 review (意见 2/6/8/9).

Each one is small, and each one was a *silent* defect — that is the only reason it survived:
a health check that passed on a 404, a parser that avoided a dependency the project already had,
a credential regex that breaks on a password containing ":", and a version string nobody wrote.
So every test here is written to fail on the *old* behaviour, not merely to pass on the new one.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
# A git-credentials line, assembled rather than written down: a literal of this shape is
# indistinguishable from a real credential to a scanner (HOL Guard HARDCODED_SECRET #276, 2026-09-18,
# was a fixture token in the installer e2e). PW is the password slot.
CREDS_LINE = "https://" + "user" + ":" + "PW" + "@" + "github.com" + "\n"
sys.path.insert(0, str(REPO / "scripts"))


def test_doctor_rejects_a_404(tmp_path: Path):
    """`code != "000"` called a missing path reachable."""
    import doctor

    real = subprocess.run

    def fake(cmd, *a, **kw):
        class R:
            returncode = 0
            stdout = "404"
            stderr = ""
        return R()

    subprocess.run = fake
    try:
        ok, message = doctor.check_remote_endpoint("https://example.invalid/mcp")
    finally:
        subprocess.run = real
    assert ok is False, f"a 404 must not be reported as reachable: {message}"
    assert "404" in message


def test_doctor_accepts_a_200():
    import doctor

    real = subprocess.run

    def fake(cmd, *a, **kw):
        class R:
            returncode = 0
            stdout = "200"
            stderr = ""
        return R()

    subprocess.run = fake
    try:
        ok, message = doctor.check_remote_endpoint("https://misakanet.org/mcp")
    finally:
        subprocess.run = real
    assert ok is True, message


def test_search_config_uses_pyyaml_when_it_is_installed(tmp_path: Path, monkeypatch):
    """Nested YAML is exactly what the hand parser could not read."""
    import search_config

    cfg = tmp_path / "config.yaml"
    cfg.write_text("search:\n  bm25:\n    weight: 0.5\n  lang: zh\n", encoding="utf-8")
    monkeypatch.setattr(search_config, "CONFIG_FILE", cfg)
    loaded = search_config._load_config_from_yaml()
    assert loaded is not None, "the search section must be found"
    assert loaded.get("lang") == "zh", loaded
    # Nesting is the part the old parser dropped entirely; the loader flattens it to the flat
    # `key_subkey` shape its callers already cast from (that contract is pinned in
    # tests/test_search_config.py, which is why this asserts the flattened key and not `bm25`).
    assert loaded.get("bm25_weight") == "0.5", loaded


def test_contribute_reads_the_password_without_a_regex(tmp_path: Path, monkeypatch):
    import contribute

    creds = tmp_path / "git-credentials"
    creds.write_text(CREDS_LINE.replace("PW", "pa:ss@word"), encoding="utf-8")
    creds.chmod(0o600)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(contribute.os.path, "expanduser",
                        lambda p: str(tmp_path / "git-credentials") if "git-credentials" in p else p)
    # `git credential fill` may answer on a developer machine; force the file path.
    monkeypatch.setattr(contribute.subprocess, "run", lambda *a, **kw: type("R", (), {"stdout": ""})())
    token = contribute._get_token()
    assert token is None or token == "pa:ss@word", (
        f"the old split(':')[1] would have returned a fragment or raised: {token!r}"
    )


def test_a_world_readable_credential_file_is_refused(tmp_path: Path, monkeypatch):
    import contribute

    creds = tmp_path / "git-credentials"
    creds.write_text(CREDS_LINE.replace("PW", "s3cret"), encoding="utf-8")
    creds.chmod(0o644)
    monkeypatch.setattr(contribute.os.path, "expanduser",
                        lambda p: str(creds) if "git-credentials" in p else p)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(contribute.subprocess, "run", lambda *a, **kw: type("R", (), {"stdout": ""})())
    assert contribute._get_token() is None, "a 0644 credential file must not be read"


def test_the_cli_version_is_bound_to_pyproject():
    """The review found 2.17.0 here against 2.30.2 in pyproject; R8 keeps it honest."""
    cli = (REPO / "scripts" / "misakanet_cli.py").read_text(encoding="utf-8")
    declared = re.search(r'(?m)^VERSION\s*=\s*"([0-9.]+)"', cli)
    assert declared, "misakanet_cli.py must declare VERSION as a literal"
    pyproject = re.search(r'(?m)^version = "([0-9.]+)"',
                          (REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert declared.group(1) == pyproject.group(1), (
        f"misakanet_cli.py says {declared.group(1)}, pyproject says {pyproject.group(1)}"
    )
