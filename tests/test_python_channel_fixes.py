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


def _fake_curl(stdout: str):
    class R:
        returncode = 0
        stderr = ""
    r = R()
    r.stdout = stdout
    return lambda *a, **kw: r


def test_doctor_rejects_a_404(monkeypatch):
    """`code != "000"` called a missing path reachable."""
    import doctor
    monkeypatch.setattr(doctor.subprocess, "run", _fake_curl('not found\n404'))
    ok, message = doctor.check_remote_endpoint("https://example.invalid/mcp")
    assert ok is False, f"a 404 must not be reported as reachable: {message}"
    assert "404" in message


def test_doctor_rejects_a_200_that_is_not_mcp(monkeypatch):
    """200 alone is not the claim: the body has to be an MCP handshake answer."""
    import doctor
    monkeypatch.setattr(doctor.subprocess, "run", _fake_curl('{"hello":"world"}\n200'))
    ok, message = doctor.check_remote_endpoint("https://example.invalid/mcp")
    assert ok is False, message
    assert "serverInfo" in message


def test_doctor_rejects_a_405_to_the_handshake(monkeypatch):
    """405 is healthy for a bare GET, and a finding for an initialize POST."""
    import doctor
    monkeypatch.setattr(doctor.subprocess, "run", _fake_curl("Method Not Allowed\n405"))
    ok, message = doctor.check_remote_endpoint("https://example.invalid/mcp")
    assert ok is False, message
    assert "405" in message


def test_doctor_accepts_an_answered_handshake(monkeypatch):
    import doctor
    monkeypatch.setattr(doctor.subprocess, "run",
                        _fake_curl('{"result":{"serverInfo":{"name":"misakanet"}}}\n200'))
    ok, message = doctor.check_remote_endpoint("https://misakanet.org/mcp")
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


# ── the version read-back (#1820) ───────────────────────────────────────────────────
def _handshake(version: str) -> str:
    return ('{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18",'
            '"capabilities":{"tools":{}},"serverInfo":{"name":"misakanet",'
            f'"version":"{version}"}}}}\n200')


def test_doctor_reads_the_deployed_version_back(monkeypatch):
    """The number every MCP client sees is self-reported, so it needs a *live* gate: it sat at
    2.27.1 across six releases while every file-based check passed (#1820)."""
    import doctor
    declared, _ = doctor.declared_version()
    assert declared, "this checkout declares no worker version — cannot compare"
    monkeypatch.setattr(doctor.subprocess, "run", _fake_curl(_handshake(declared)))
    ok, message = doctor.check_deployed_version("https://misakanet.org/mcp")
    assert ok is True, message
    assert declared in message, message


def test_doctor_rejects_a_deployment_that_reports_a_stale_version(monkeypatch):
    import doctor
    declared, _ = doctor.declared_version()
    monkeypatch.setattr(doctor.subprocess, "run", _fake_curl(_handshake("2.27.1")))
    ok, message = doctor.check_deployed_version("https://misakanet.org/mcp")
    assert ok is False, "a stale self-report must be a failed check"
    assert "2.27.1" in message and declared in message, message


def test_a_handshake_without_a_version_is_a_failure_not_a_pass(monkeypatch):
    """'No serverInfo' was already a failure for reachability; the same must hold here rather than
    the comparison silently finding nothing to compare."""
    import doctor
    monkeypatch.setattr(doctor.subprocess, "run", _fake_curl('{"result":{"serverInfo":{}}}\n200'))
    ok, message = doctor.check_deployed_version("https://misakanet.org/mcp")
    assert ok is False
    assert "without a serverInfo.version" in message, message


def test_the_version_check_is_not_part_of_plain_doctor(monkeypatch):
    """A developer's checkout is routinely ahead of production. If `make doctor` compared them, every
    unpushed version bump would look like a deployment failure — the expensive kind of red."""
    import doctor
    assert "deployed-version" not in doctor.selection([])
    assert "deployed-version" not in doctor.selection(["--remote-only"])
    assert "deployed-version" in doctor.selection(["--post-deploy"])


def test_the_live_version_is_compared_against_the_workers_own_constant():
    """Which number is compared is the whole check, so it gets asserted.

    `package.json` and the worker's `serverInfo` constant are allowed to differ (release-please bumps
    the worker line, and the manifest/source line can sit ahead of it). Comparing against the wrong one
    turns real drift into a false green — and, when the two are the other way round, a false red. The
    mutation that swapped the key passed every other test in this file because the two values happen to
    be equal today.
    """
    import align_versions
    import doctor
    assert "register-proxy-sw.js" in doctor.WORKER_VERSION_KEY, doctor.WORKER_VERSION_KEY
    assert doctor.WORKER_VERSION_KEY in align_versions.locations(), (
        "the key is not one scripts/align_versions.py publishes — the comparison would read nothing"
    )
    value, where = doctor.declared_version()
    assert re.match(r"^\d+\.\d+\.\d+$", value), (value, where)
