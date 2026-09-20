#!/usr/bin/env python3
"""A failed probe is not proof that the endpoint is down.

`--verify` probes the endpoint with Node's `fetch`, and Node's fetch ignores `HTTP_PROXY` /
`HTTPS_PROXY` / `NO_PROXY` unless the runtime is told to honour them (`NODE_USE_ENV_PROXY=1` or
`--use-env-proxy`; fetch support in Node v22.21.0 / v24.0.0+ —
nodejs.org/learn/http/enterprise-network-configuration). In an enterprise-proxy environment that
makes the probe unreliable in one direction: `curl` and the user's agent can both reach
`https://misakanet.org/mcp` through a proxy this process never saw, while `--verify` reports
"端点不可达（网络受限？）" and sends the user to debug a network that works.

The installer's audience includes exactly those users — this repository's own corpus carries corporate
proxy lessons — so the fix is to say what is actually known:

* a proxy is configured and this Node will not use it → **inconclusive**, warn, do not fail the
  interactive verdict (the install itself is fine);
* the same situation under `--strict` / `--ci` → fail, because a gate that cannot tell must not pass
  silently;
* no proxy, or a proxy this Node honours → a failed probe is a failed probe, unchanged.

Everything below runs against `http://127.0.0.1:9/mcp` (a refused connection, no network) with
`--no-register`, so the outcome does not depend on the real endpoint being up.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CLI = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
DEAD_ENDPOINT = "http://127.0.0.1:9/mcp"
PROXY = "http://127.0.0.1:3128"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not CLI.exists(), reason="needs node and the setup CLI"
)

PROXY_VARS = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy",
              "NO_PROXY", "no_proxy", "NODE_USE_ENV_PROXY", "MISAKANET_ENDPOINT")


def _env(proxy: str = "", **extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in PROXY_VARS}
    env["MISAKANET_ENDPOINT"] = DEAD_ENDPOINT
    if proxy:
        env["HTTPS_PROXY"] = proxy
    env.update(extra)
    return env


def run(home: Path, *flags: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["node", str(CLI), "--home", str(home), *flags],
        capture_output=True, text=True, env=env, timeout=120,
    )


@pytest.fixture
def installed_home(tmp_path: Path) -> Path:
    """A home whose only problem is the endpoint: an agent is detected and wired, no token asked."""
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    result = run(home, "--only", "cursor", "--no-register", env=_env())
    assert result.returncode == 0, result.stdout + result.stderr
    return home


def test_a_proxy_this_node_ignores_makes_the_probe_inconclusive_not_fatal(installed_home: Path):
    verify = run(installed_home, "--verify", env=_env(proxy=PROXY))
    assert verify.returncode == 0, (
        "an install whose endpoint is reachable through the user's proxy must not be reported as "
        f"NOT READY:\n{verify.stdout}{verify.stderr}"
    )
    assert "端点探测不可信" in verify.stdout, verify.stdout
    assert "NODE_USE_ENV_PROXY=1" in verify.stdout, (
        "the warning must carry the fix, not just the doubt"
    )
    # The warning itself contains the words "不代表端点不可达", so match the failure line's own
    # wording instead of the phrase — the first version of this test failed on its own message.
    assert "网络受限？读课程会静默失败" not in verify.stdout, (
        "the endpoint was not shown to be unreachable, and saying so is the false negative"
    )


def test_strict_keeps_a_hard_verdict_for_a_probe_that_cannot_be_trusted(installed_home: Path):
    strict = run(installed_home, "--report", "--strict", env=_env(proxy=PROXY))
    assert strict.returncode == 1, (
        "--strict is the CI gate: 'we cannot tell' must not pass silently\n"
        + strict.stdout + strict.stderr
    )
    assert "endpoint-probe: inconclusive-proxy" in strict.stdout, strict.stdout


def test_the_report_says_why_the_boolean_is_not_meaningful(installed_home: Path):
    report = run(installed_home, "--report", env=_env(proxy=PROXY))
    assert "endpoint-probe: inconclusive-proxy" in report.stdout, report.stdout
    assert "endpoint-reachable: false" in report.stdout, (
        "the raw probe result stays in the report; the note is what says it means nothing"
    )


def test_a_failed_probe_without_a_proxy_is_still_a_failure(installed_home: Path):
    verify = run(installed_home, "--verify", env=_env())
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert f"端点不可达：{DEAD_ENDPOINT}" in verify.stdout, verify.stdout
    assert "端点探测不可信" not in verify.stdout, (
        "no proxy is configured, so there is nothing to be uncertain about"
    )


def test_once_node_is_told_to_use_the_proxy_the_probe_means_something_again(installed_home: Path):
    verify = run(installed_home, "--verify", env=_env(proxy=PROXY, NODE_USE_ENV_PROXY="1"))
    assert verify.returncode == 1, verify.stdout + verify.stderr
    assert f"端点不可达：{DEAD_ENDPOINT}" in verify.stdout, (
        "with the env proxy enabled the runtime could have used it, so the failure is real again:\n"
        + verify.stdout
    )


def test_a_lowercase_proxy_variable_counts_too(installed_home: Path):
    """`https_proxy` is the spelling many toolchains export; missing it would re-create the bug."""
    env = _env()
    env["https_proxy"] = PROXY
    verify = run(installed_home, "--verify", env=env)
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert "端点探测不可信" in verify.stdout, verify.stdout
