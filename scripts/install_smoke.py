#!/usr/bin/env python3
"""Two *real install* probes, so "install verified" can be a measured, dated fact (owner D3 = A, 2026-09-30).

Why this script exists
----------------------
Until today every green thing about installing MisakaNet came from metadata: npm's `dist-tags`, the MCP
registry read-back in `publish-mcp-registry.yml`, and our own CI. None of them installs anything. A reader
reported the consequence directly (intake #2486, point 3): they read "automatic check passed" as "it
works". The install guide already said the static layer proves only that the catalogue is current; this
script is the other layer, the one that actually packs/installs and then *calls a tool*.

Two forms, because they are different products (docs/dsh-installation.md):

* ``npm-form`` — `misakanet` on npm is the DSH/Codex bundle: `SKILL.md`, `index.js`,
  `cordis.patch.yml`, and **no `scripts/`** by design (no `bin`, no local server). Its MCP row points at
  the hosted endpoint ``https://misakanet.org/mcp``, so the probe calls *that*.
* ``git-stdio`` — a git+/checkout install gets the repository too, including the local stdio server
  ``scripts/mcp_server.py``. The probe speaks JSON-RPC to it over stdin/stdout and checks the tool set
  against the one `docs/mcp.md` documents.

Design notes
------------
* **No third-party imports.** `tarfile`, `urllib` and `subprocess` are stdlib, so the probes run on a
  runner with nothing installed — the same **stdlib-only** claim the package makes (AGENTS.md §6). The
  interpreter itself is still the prerequisite, which is why the git+ probe asserts `python3 >= 3.10`.
* **The probe always writes its JSON**, including when it fails. A crash that left no artifact would be
  indistinguishable from "the probe never ran", and `scripts/update_install_badge.py` refuses to publish
  from absent evidence. So every failure path funnels through ``_result``/``run`` and still writes `--out`.
* **Structural assertions only** (tarball member names, a parsed URL, a measured tool set, a result
  count). No assertion here reads prose.
* Failure messages name the *possibility* they cannot distinguish: the hosted call is anonymous and
  burst-limited, so a 429/403/timeout on a runner is at least as likely to be rate limiting as a broken
  install. Saying so is the difference between a useful red and a red someone learns to ignore.

Usage:
    python3 scripts/install_smoke.py dsh-client --repo . --out /tmp/install-dsh.json
    python3 scripts/install_smoke.py dsh-client --serve        # throwaway host to click, then Ctrl-C
    python3 scripts/install_smoke.py npm-form  --repo . --out /tmp/install-npm.json
    python3 scripts/install_smoke.py git-stdio --repo . --out /tmp/install-git.json
    python3 scripts/install_smoke.py git-stdio --dry-run      # interpreter/tool-set only, no server
    python3 scripts/install_smoke.py setup-installer --out /tmp/install-setup.json
"""
from __future__ import annotations

import argparse
import datetime as _datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO_FALLBACK = Path(__file__).resolve().parent.parent

# The hosted endpoint the npm bundle's row must name, and the one this probe calls.
HOSTED_URL = "https://misakanet.org/mcp"
# Fixed query: deterministic enough that "0 results" means something broke rather than "the corpus moved".
SMOKE_QUERY = "pip install timeout"
PROTOCOL_VERSION = "2025-06-18"
ORIGIN = "https://misakanet.org"
# Explicit UA, always: the edge answers 403 to urllib's default UA (measured 2026-09-28, recorded in
# docs/agents/repo-operations.md §4 and reused in scripts/update_retrieval_badge.py). A probe that
# forgets this reads as an outage.
USER_AGENT = "misakanet-install-smoke/1.0 (+https://misakanet.org)"

# `npm pack` names everything under this prefix, so "the tarball has scripts/" is a prefix test.
NPM_REQUIRED_MEMBERS = ("package/SKILL.md", "package/index.js", "package/cordis.patch.yml")
NPM_FORBIDDEN_PREFIX = "package/scripts/"
# The tool the git+ probe must be able to call, and the row it must be told about by docs/mcp.md.
REQUIRED_TOOL = "misakanet_search"
STDIO_DOC_ROW = "**local stdio**"

# A failed hosted call is ambiguous on purpose-built evidence: an anonymous public endpoint with a burst
# window. Print the ambiguity, so nobody turns a throttled minute into "the install is broken".
RATE_LIMIT_HINT = (
    "the hosted endpoint refused or stalled this probe; its anonymous burst window is shared by every "
    "caller, so a 429/403/timeout on a CI runner may be rate limiting rather than a broken install — "
    f"re-run the job, or check {HOSTED_URL} by hand, before treating this as a regression"
)

TOOL_NAME_RE = re.compile(r"misakanet_[a-z_]+")
# `url: https://…` at the start of a line: the shape of the row in cordis.patch.yml and of
# `DEFAULT_MCP_CONFIG.url` in index.js. Comments carry neither in either file (checked 2026-09-30).
ROW_URL_RE = re.compile(r"(?m)^\s*url:\s*[\"']?(https?://[^\s\"',]+)")
# A local row would name a process to spawn. The bundle must not: the npm form has no server to spawn.
ROW_COMMAND_RE = re.compile(r"(?m)^\s*command:\s*\S")
PY_VERSION_RE = re.compile(r"Python\s+(\d+)\.(\d+)")
MIN_PYTHON = (3, 10)


def _now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── pure helpers (the parts a test can mutate) ────────────────────────────────────────────────────

def tarball_problems(members: list[str]) -> list[str]:
    """What is wrong with a packed npm tarball's member list.

    Two facts, both structural: the files the bundle advertises are present, and the repository's
    `scripts/` (including the local stdio server) is not. The second half is the intake #2486 confusion —
    an npm install that silently shipped the server would make the two install forms look equivalent.
    """
    problems = [f"the packed tarball is missing {member}" for member in NPM_REQUIRED_MEMBERS
                if member not in members]
    leaked = sorted(member for member in members if member.startswith(NPM_FORBIDDEN_PREFIX))
    if leaked:
        problems.append(
            f"the packed tarball ships {len(leaked)} file(s) under {NPM_FORBIDDEN_PREFIX} "
            f"(first: {leaked[0]}) — the npm bundle must stay skill-only; the local stdio server is the "
            "git+ form's difference (tests/test_dsh_plugin_manifest.py pins the same fact)")
    return problems


def mcp_row_problems(patch_text: str, index_text: str) -> list[str]:
    """What is wrong with the MCP row the bundle wires (patch row + index.js default).

    The npm install's only route to tools is this URL, so a row that names anything else — a local
    command, a stale host — installs a skill with no working tools and every metadata check stays green.
    """
    problems = []
    for label, text in (("cordis.patch.yml", patch_text), ("index.js", index_text)):
        urls = ROW_URL_RE.findall(text)
        if HOSTED_URL not in urls:
            problems.append(
                f"{label} does not wire the hosted endpoint {HOSTED_URL} (urls found: {urls or 'none'}) "
                "— an npm install has no local server to reach")
    if ROW_COMMAND_RE.search(patch_text):
        problems.append(
            "cordis.patch.yml declares a local `command:` row, so the npm form depends on a process the "
            "tarball does not ship (issue #1734)")
    return problems


def documented_stdio_tools(mcp_md_text: str) -> frozenset[str]:
    """The stdio tool set `docs/mcp.md` documents — the expectation for ``tools/list``.

    Read from the document, not from ``misakanet/server/TOOLS``: an expectation taken from the file under
    test cannot disagree with it (the same mistake `canonical_mcp_tools` was written to fix, #1822). A
    missing row raises instead of returning an empty set — a reader that quietly finds nothing is how a
    gate stops existing.
    """
    for line in mcp_md_text.splitlines():
        if line.startswith("|") and STDIO_DOC_ROW in line:
            names = frozenset(TOOL_NAME_RE.findall(line))
            if names:
                return names
    raise ValueError(
        f"docs/mcp.md has no `{STDIO_DOC_ROW}` surface row carrying tool names — moving that table means "
        "updating this reader (and the gate would otherwise compare against nothing)")


def search_result_count(result: dict) -> int:
    """How many ranked results a `misakanet_search` result carries.

    Reads `structuredContent` first (the machine-readable half) and falls back to parsing `content[0].text`,
    because both shapes are served and a probe that only understood one would report 0 successes.
    """
    structured = result.get("structuredContent")
    if isinstance(structured, dict) and isinstance(structured.get("results"), list):
        return len(structured["results"])
    for part in result.get("content") or []:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        try:
            payload = json.loads(part.get("text") or "")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            return len(payload["results"])
    return 0


# ── transports ────────────────────────────────────────────────────────────────────────────────────

class HostedCallError(RuntimeError):
    """A hosted JSON-RPC call that could not be completed or answered with an error."""


def hosted_jsonrpc(url: str, method: str, params: dict, *, request_id: int, timeout: int) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}).encode()
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
        "Origin": ORIGIN,
        "User-Agent": USER_AGENT,
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:                       # includes 429/403: see RATE_LIMIT_HINT
        detail = error.read()[:300].decode("utf-8", errors="replace")
        raise HostedCallError(f"{method} → HTTP {error.code} from {url}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise HostedCallError(f"{method} → {type(error).__name__} from {url}: {error}") from error
    try:
        payload = json.loads(raw)
    except ValueError as error:
        raise HostedCallError(f"{method} → non-JSON response from {url} ({raw[:200]!r})") from error
    if "error" in payload:
        raise HostedCallError(f"{method} → JSON-RPC error from {url}: {payload['error']}")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise HostedCallError(f"{method} → response from {url} has no `result` object: {payload}")
    return result


def stdio_jsonrpc(repo: Path, requests: list[dict], *, timeout: int) -> tuple[dict[int, dict], str, str]:
    """Speak JSON-RPC to the local server and return ({id: result}, stdout, stderr).

    Requests are written up front and stdin is closed: the server answers each request and exits at EOF
    (measured 2026-09-30 with the same shape as the manual probe in the PR evidence), so no timeout logic
    beyond the process deadline is needed.
    """
    script = repo / "scripts" / "mcp_server.py"
    if not script.is_file():
        raise HostedCallError(f"{script} does not exist — the git+ form's local server is missing")
    payload = "".join(json.dumps(request) + "\n" for request in requests)
    try:
        completed = subprocess.run(
            ["python3", "scripts/mcp_server.py"], cwd=str(repo), input=payload,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise HostedCallError(
            f"scripts/mcp_server.py did not answer within {timeout}s — the local search may be building "
            "its index; raise --timeout before calling this a failure") from error
    results: dict[int, dict] = {}
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if isinstance(message.get("id"), int) and isinstance(message.get("result"), dict):
            results[message["id"]] = message["result"]
    return results, completed.stdout, completed.stderr


# ── the two probes ────────────────────────────────────────────────────────────────────────────────

# ── the installer form (2026-09-30) ─────────────────────────────────────────────────────────────────
# The two forms above probe the *plugin* (what dsh and Codex install). But most people do not arrive that
# way: of the last 100 intakes, codex (38%) and claude-code (27%) account for two thirds, and Codex has its
# own plugin channel (`.codex-plugin/plugin.json`) while Claude Code has none — so Claude Code users are
# served by this installer, which no daily probe covered. It is a different failure surface too: the
# installer writes into a *user's own* client config, so "does it register and can it verify itself" is the
# question, and both are answerable without a human.
#
# Measured before writing this (2026-09-30, published 0.5.6 + the repo's bin, temp `--home`):
#   * `--report-json --silent` alone is the MDM *report-only* form (#1784) — it writes nothing, which is
#     correct and was the first thing this probe got wrong by assuming otherwise;
#   * a real install (`--silent`) then a report gives `verify: READY`, `install-scope: full`,
#     `hook: present`, `endpoint-reachable: true`, `endpoint-tools: 7`;
#   * the install mints a **real bearer token** into the client config, so the probe asserts shape and
#     never copies the file (the artifact must not carry a credential — this repository's own rule).
SETUP_ENDPOINT = "https://misakanet.org/mcp"
SETUP_REPORT_SCHEMA = "misakanet-setup-report/1"
# The hosted tool set (`docs/mcp.md`). A shrink is a regression; growth is fine, so this is a floor.
SETUP_MIN_ENDPOINT_TOOLS = 7


def setup_config_problems(config_text: str) -> list[str]:
    """What the installer promises to write: one `misakanet` MCP row pointing at the hosted endpoint."""
    problems: list[str] = []
    try:
        doc = json.loads(config_text)
    except json.JSONDecodeError as exc:
        return [f"the client config is not JSON after install: {exc}"]
    entry = ((doc.get("mcpServers") or {}).get("misakanet")) or None
    if not isinstance(entry, dict):
        return ["the installer did not register an `mcpServers.misakanet` entry"]
    if entry.get("url") != SETUP_ENDPOINT:
        problems.append(f"the registered url is {entry.get('url')!r}, not {SETUP_ENDPOINT!r}")
    if entry.get("type") != "http":
        problems.append(f"the registered transport is {entry.get('type')!r}, not 'http'")
    return problems


def setup_report_problems(report: dict) -> list[str]:
    """The installer's own verdict, read from its machine-readable report."""
    problems: list[str] = []
    if report.get("schema") != SETUP_REPORT_SCHEMA:
        problems.append(f"report schema is {report.get('schema')!r}, not {SETUP_REPORT_SCHEMA!r}")
    if report.get("verify") != "READY":
        problems.append(
            f"the installer's own verdict is {report.get('verify')!r}, not 'READY' "
            f"(open-items={report.get('open-items')}: {report.get('open-items-detail')})")
    if report.get("install-scope") != "full":
        problems.append(f"install-scope is {report.get('install-scope')!r}, not 'full'")
    if report.get("endpoint-reachable") is not True:
        problems.append("the installer could not reach the endpoint it registers")
    tools = report.get("endpoint-tools")
    if not isinstance(tools, int) or tools < SETUP_MIN_ENDPOINT_TOOLS:
        problems.append(f"endpoint-tools is {tools!r}; the hosted set is {SETUP_MIN_ENDPOINT_TOOLS} or more")
    return problems


def probe_setup_installer(repo: Path, *, timeout: int, dry_run: bool) -> dict:
    """Install the **published** installer into a throwaway HOME, then read its own report.

    The published package is the point: this is the path a Claude Code user takes
    (`npx @misaka-net/misakanet-setup`), so probing the repository's own bin would test something nobody
    runs. `--home` plus `HOME=` keep the probe hermetic — both are needed, because detection reads
    `$HOME` while the writes follow `--home`.
    """
    fails: list[str] = []
    checks: list[str] = []
    detail: dict = {}
    home = Path(tempfile.mkdtemp(prefix="misakanet-setup-smoke-home-"))
    env = dict(os.environ, npm_config_cache=str(home / "npm-cache"), HOME=str(home))
    # Claude Code's detection marker: the installer acts on clients it can see, and a machine with no
    # client at all legitimately installs nothing (measured: `detected-agents: []` → `install-scope: none`).
    (home / ".claude.json").write_text("{}\n", encoding="utf-8")

    def run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)

    pkg = "@misaka-net/misakanet-setup@latest"
    if dry_run:
        # No install, no report: the flags exist and the package resolves at all.
        probe = run(["npx", "--yes", pkg, "--help"])
        checks.append(f"`{pkg} --help` exits {probe.returncode}")
        if probe.returncode != 0:
            fails.append(f"npx could not run {pkg} (exit {probe.returncode}): {probe.stderr.strip()[:200]}")
        shutil.rmtree(home, ignore_errors=True)
        return _result("setup-installer", checks, fails, detail, tools_seen=[], result_count=0)

    install = run(["npx", "--yes", pkg, "--home", str(home), "--silent"])
    detail["install_exit"] = install.returncode
    if install.returncode != 0:
        fails.append(f"`npx {pkg} --home … --silent` exited {install.returncode}: "
                     f"{(install.stderr or install.stdout).strip()[:200]}")
    else:
        checks.append("install exited 0")

    config = home / ".claude.json"
    if config.is_file():
        problems = setup_config_problems(config.read_text(encoding="utf-8"))
        # Never copy the file: it carries the bearer token the install minted.
        if problems:
            fails.extend(problems)
        else:
            checks.append("registered mcpServers.misakanet → the hosted endpoint over http")
    else:
        fails.append("the install wrote no client config at all")
    detail["client_config_written"] = config.is_file()
    detail["hook_written"] = (home / ".claude" / "settings.json").is_file()
    if not detail["hook_written"]:
        fails.append("no behaviour layer: `.claude/settings.json` was not written")
    else:
        checks.append("wrote the behaviour layer (.claude/settings.json)")

    report_proc = run(["npx", "--yes", pkg, "--home", str(home), "--report-json", "--silent"])
    report: dict = {}
    try:
        report = json.loads(report_proc.stdout)
    except json.JSONDecodeError as exc:
        fails.append(f"the report is not JSON (exit {report_proc.returncode}): {exc}; "
                     f"stderr={report_proc.stderr.strip()[:160]}")
    if report:
        detail["report"] = {k: report.get(k) for k in
                            ("schema", "setup-version", "detected-agents", "verify", "install-scope",
                             "endpoint-reachable", "endpoint-tools", "hook", "open-items")}
        problems = setup_report_problems(report)
        if problems:
            fails.extend(problems)
        else:
            checks.append(f"the installer reports verify=READY with {report.get('endpoint-tools')} "
                          "endpoint tools")

    # Its own promise: `--uninstall` removes exactly what was added.
    uninstall = run(["npx", "--yes", pkg, "--home", str(home), "--uninstall", "--silent"])
    detail["uninstall_exit"] = uninstall.returncode
    if uninstall.returncode != 0:
        fails.append(f"`--uninstall` exited {uninstall.returncode}")
    else:
        left = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
        if "misakanet" in json.dumps(left):
            fails.append("`--uninstall` left the misakanet entry in the client config")
        else:
            checks.append("`--uninstall` removed the registered entry")

    shutil.rmtree(home, ignore_errors=True)   # the temp HOME holds a minted token
    return _result("setup-installer", checks, fails, detail, tools_seen=[], result_count=0)


def probe_npm_form(repo: Path, *, timeout: int, dry_run: bool) -> dict:
    """Pack the bundle, assert its shape and row, then call the hosted endpoint for real."""
    fails: list[str] = []
    checks: list[str] = []
    detail: dict = {}
    workdir = Path(tempfile.mkdtemp(prefix="misakanet-install-smoke-"))
    # npm writes its logs under the cache dir (`$cache/_logs`), and a sandboxed local run failed with
    # "Log files were not written ... /home/<user>/.npm/_logs" (measured 2026-09-30). Pointing the cache at
    # the probe's own temp dir makes the probe work wherever it is run, including this repo's own docs
    # workflow sandboxes.
    env = dict(os.environ, npm_config_cache=str(workdir / "npm-cache"))

    packed = subprocess.run(
        ["npm", "pack", "--pack-destination", str(workdir), "--loglevel=error"],
        cwd=str(repo), env=env, capture_output=True, text=True, timeout=timeout,
    )
    if packed.returncode != 0:
        fails.append(f"`npm pack` exited {packed.returncode}: {(packed.stderr or '').strip()[-400:]}")
        return _result("npm", checks, fails, detail, tools_seen=[], result_count=0)
    tarballs = sorted(workdir.glob("*.tgz"))
    if not tarballs:
        fails.append(f"`npm pack` printed no tarball and left none in {workdir}: {packed.stdout.strip()!r}")
        return _result("npm", checks, fails, detail, tools_seen=[], result_count=0)
    tarball = tarballs[-1]
    detail["tarball"] = tarball.name

    with tarfile.open(tarball) as archive:
        members = archive.getnames()
        detail["members"] = members
        shape_problems = tarball_problems(members)
        if shape_problems:
            fails.extend(shape_problems)
        else:
            checks.append(f"tarball shape: {len(NPM_REQUIRED_MEMBERS)} required members present, "
                          f"no {NPM_FORBIDDEN_PREFIX}*")
        # Parse the row out of the *packed* files, not the checkout: what a consumer installs is the
        # tarball, and a stale build could wire something the working tree no longer does.
        patch = _tar_member(archive, "package/cordis.patch.yml")
        index = _tar_member(archive, "package/index.js")
    if patch is None or index is None:
        if patch is None:
            fails.append("package/cordis.patch.yml is not readable in the tarball")
        if index is None:
            fails.append("package/index.js is not readable in the tarball")
    else:
        row_problems = mcp_row_problems(patch, index)
        if row_problems:
            fails.extend(row_problems)
        else:
            checks.append(f"MCP row in the packed bundle names {HOSTED_URL} and no local command")

    if dry_run:
        checks.append("dry run: hosted call skipped")
        return _result("npm", checks, fails, detail, tools_seen=[], result_count=0)

    tools_seen: list[str] = []
    result_count = 0
    if fails:
        # The install shape is wrong, so calling the endpoint would prove nothing about the install.
        checks.append("hosted call skipped: the packed bundle failed its own shape checks")
    else:
        try:
            initialize = hosted_jsonrpc(HOSTED_URL, "initialize", {
                "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "misakanet-install-smoke", "version": "1.0"},
            }, request_id=1, timeout=timeout)
            detail["server_info"] = initialize.get("serverInfo")
            listing = hosted_jsonrpc(HOSTED_URL, "tools/list", {}, request_id=2, timeout=timeout)
            tools_seen = sorted(str(tool.get("name")) for tool in listing.get("tools") or []
                                if isinstance(tool, dict))
            call = hosted_jsonrpc(HOSTED_URL, "tools/call", {
                "name": REQUIRED_TOOL, "arguments": {"query": SMOKE_QUERY, "top": 3},
            }, request_id=3, timeout=timeout)
            result_count = search_result_count(call)
            if REQUIRED_TOOL not in tools_seen:
                fails.append(f"the hosted endpoint does not list {REQUIRED_TOOL} (saw {tools_seen})")
            elif result_count < 1:
                fails.append(f"{REQUIRED_TOOL}({SMOKE_QUERY!r}) returned 0 results through the hosted "
                             "endpoint")
            else:
                checks.append(f"hosted {REQUIRED_TOOL}({SMOKE_QUERY!r}) → {result_count} result(s)")
                checks.append(f"hosted initialize → {detail.get('server_info')}")
        except HostedCallError as error:
            fails.append(str(error))
            detail["hint"] = RATE_LIMIT_HINT
    return _result("npm", checks, fails, detail, tools_seen=tools_seen, result_count=result_count)


def probe_git_stdio(repo: Path, *, timeout: int, dry_run: bool) -> dict:
    """Assert the interpreter floor, then handshake the local stdio server and call search."""
    fails: list[str] = []
    checks: list[str] = []
    detail: dict = {}

    version = subprocess.run(["python3", "--version"], capture_output=True, text=True)
    version_text = (version.stdout or version.stderr).strip()
    detail["python"] = version_text
    match = PY_VERSION_RE.search(version_text)
    if not match:
        fails.append(f"cannot read a version out of `python3 --version` → {version_text!r}")
    else:
        found = (int(match.group(1)), int(match.group(2)))
        if found < MIN_PYTHON:
            fails.append(f"`python3 --version` is {version_text}, below the documented prerequisite "
                         f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} (docs/dsh-installation.md)")
        else:
            checks.append(f"interpreter prerequisite: {version_text} ≥ {MIN_PYTHON[0]}.{MIN_PYTHON[1]}")

    guide = repo / "docs" / "mcp.md"
    try:
        expected_tools = documented_stdio_tools(guide.read_text(encoding="utf-8"))
        detail["documented_tools"] = sorted(expected_tools)
    except (OSError, ValueError) as error:
        return _result("git", checks, fails + [str(error)], detail, tools_seen=[], result_count=0)

    if dry_run:
        checks.append("dry run: stdio server not spawned")
        return _result("git", checks, fails, detail, tools_seen=[], result_count=0)

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                    "clientInfo": {"name": "misakanet-install-smoke", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": REQUIRED_TOOL, "arguments": {"query": SMOKE_QUERY, "top": 3}}},
    ]
    try:
        results, stdout, stderr = stdio_jsonrpc(repo, requests, timeout=timeout)
    except HostedCallError as error:
        return _result("git", checks, fails + [str(error)], detail, tools_seen=[], result_count=0)
    detail["stderr_tail"] = "\n".join(stderr.strip().splitlines()[-3:])

    initialize = results.get(1)
    if initialize is None:
        fails.append("the stdio server did not answer `initialize` (see stdout/stderr in the artifact)")
        detail["stdout_tail"] = "\n".join(stdout.strip().splitlines()[-3:])
    else:
        detail["server_info"] = initialize.get("serverInfo")
        checks.append(f"stdio initialize → {detail.get('server_info')}")

    listing = results.get(2) or {}
    tools_seen = sorted(str(tool.get("name")) for tool in listing.get("tools") or []
                        if isinstance(tool, dict))
    if not tools_seen:
        fails.append("the stdio server answered `tools/list` with no tools")
    else:
        measured = frozenset(tools_seen)
        if measured != expected_tools:
            fails.append(
                f"the stdio tool set disagrees with docs/mcp.md: only in the server: "
                f"{sorted(measured - expected_tools)}; only in the document: "
                f"{sorted(expected_tools - measured)}")
        else:
            checks.append(f"stdio tools/list → {len(tools_seen)} tools, equal to docs/mcp.md "
                          f"({STDIO_DOC_ROW})")
        if REQUIRED_TOOL not in measured:
            fails.append(f"the stdio server does not register {REQUIRED_TOOL}, so the call below is "
                         "impossible")

    result_count = 0
    call = results.get(3)
    if call is None:
        fails.append(f"the stdio server did not answer `tools/call {REQUIRED_TOOL}`")
    else:
        result_count = search_result_count(call)
        if result_count < 1:
            fails.append(f"{REQUIRED_TOOL}({SMOKE_QUERY!r}) returned 0 results from the local server — "
                         "the checkout's `lessons/` index may be unreadable")
        else:
            checks.append(f"stdio {REQUIRED_TOOL}({SMOKE_QUERY!r}) → {result_count} result(s)")
    return _result("git", checks, fails, detail, tools_seen=tools_seen, result_count=result_count)


def _tar_member(archive: tarfile.TarFile, name: str) -> str | None:
    try:
        handle = archive.extractfile(name)
    except KeyError:
        return None
    if handle is None:
        return None
    return handle.read().decode("utf-8", errors="replace")


# ── dsh-client: boot a real host, in a home that is not yours ─────────────────────────────────────
#
# The other three forms probe a *package*. This one probes what the package does inside a running host,
# because that is where the interesting failure lives: an activation error in a profile bundle is not a
# local failure — the host prints `dsh: startup failed: N required plugins did not activate` and **refuses
# to start**, taking every unrelated plugin in that profile with it (observed live on 2026-10-01).
#
# Two rules make this probe safe to run on a machine someone is using:
#
# 1. **It never touches a real `DSH_HOME`.** The home is a fresh temp directory and the guard below
#    refuses anything else, so a profile the owner is running cannot be mutated — which is exactly how
#    the incident above started (a CLI `dsh plugin add` against a *live* profile).
# 2. **Startup is an assertion, not a precondition.** The probe fails if the host does not come up, so a
#    bundle that can break boot is caught here rather than on the owner's daily driver.

WEB_URL = re.compile(r"dsh web:\s*(http://[^\s]+)")
BOOT_GRAPH = re.compile(r'globalThis\["__DSH_BOOT__"\]\s*=\s*(\{.*?\})\s*</script>', re.S)
# The panel's own registrations: if the bundle were served but the panel missing, these would be absent.
CLIENT_MARKERS = ("conversation.view", "sidebar.right.pane.tab", "sidebarRightTabs")


def assert_disposable_home(home: Path) -> None:
    """Refuse to run against anything that looks like a real DSH home.

    A probe that can mutate the owner's profile is worse than no probe: that is the mistake this whole
    function exists to make impossible (2026-10-01, a live `~/.dsh` rewritten from the CLI while its host
    was running, after which the plugin stopped loading).
    """
    resolved = home.resolve()
    real = (Path.home() / ".dsh").resolve()
    if resolved == real or real in resolved.parents:
        raise RuntimeError(f"refusing to run against a real DSH home: {resolved}")
    tmp = Path(tempfile.gettempdir()).resolve()
    if tmp not in resolved.parents and resolved != tmp:
        raise RuntimeError(f"refusing a home outside the temporary directory: {resolved}")


def parse_web_url(stdout: str) -> str | None:
    """The URL the host prints once it is listening — its presence *is* the startup check."""
    match = WEB_URL.search(stdout)
    return match.group(1).strip() if match else None


def parse_boot_graph(html: str) -> dict:
    """The composed client entry graph the shell injects as `window.__DSH_BOOT__`."""
    match = BOOT_GRAPH.search(html)
    if match is None:
        raise ValueError("the served page carries no __DSH_BOOT__ graph")
    raw = match.group(1).replace("\\u003c", "<").replace('\\"', '"')
    return json.loads(raw)


def _get(url: str, *, cookies: Path, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "misakanet-install-smoke/1.0"})
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar(cookies)))
    with opener.open(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def _cookie_jar(path: Path):
    import http.cookiejar  # stdlib, and only needed on this path
    return http.cookiejar.MozillaCookieJar(str(path))


def probe_dsh_client(repo: Path, *, timeout: int, dry_run: bool = False,
                     keep: bool = False, serve: bool = False,
                     check_uninstall: bool = False, dsh: str | None = None) -> dict:
    """Install into a throwaway profile, boot the host, and read the graph it composes."""
    checks: list[str] = []
    fails: list[str] = []
    detail: dict = {"home": None, "url": None, "package": None, "host_pid": None}
    package = json.loads((repo / "package.json").read_text(encoding="utf-8"))
    detail["package"] = package.get("name")
    declared_inject = list((package.get("dsh", {}).get("client", {}) or {}).get("inject", []))

    binary = dsh or shutil.which("dsh")
    if binary is None:
        fails.append("`dsh` is not on PATH, so no host can be booted; install the harness first")
        return _result("dsh-client", checks, fails, detail, tools_seen=[], result_count=0)

    home = Path(tempfile.mkdtemp(prefix="misakanet-dsh-smoke-"))
    try:
        assert_disposable_home(home)
        detail["home"] = str(home)
        checks.append(f"empty DSH_HOME at {home} (never the owner's)")

        env = dict(os.environ, DSH_HOME=str(home), DSH_PROFILE="web",
                   npm_config_cache=str(home / "npm-cache"))
        add = subprocess.run([binary, "plugin", "--profile", "web", "add", str(repo)],
                             capture_output=True, text=True, env=env, timeout=timeout)
        profile = json.loads((home / "profiles" / "web" / "package.json").read_text(encoding="utf-8"))
        bundles = profile.get("dsh", {}).get("profile", {}).get("bundles", [])
        if package["name"] in bundles:
            checks.append(f"`dsh plugin add` put {package['name']} in dsh.profile.bundles")
        else:
            fails.append(f"the profile did not gain the bundle: {bundles} (add exited {add.returncode})")

        if dry_run:
            detail["hint"] = "dry-run: the host was never booted; the startup check did not run"
            return _result("dsh-client", checks, fails, detail, tools_seen=[], result_count=0)

        port = _free_port()
        # `start_new_session` matters for --serve: without it the host is in this process's group and dies
        # with the shell that ran the probe, which is the opposite of "left running for a human look".
        process = subprocess.Popen([binary, "--profile", "web", "--no-open", "--port", str(port)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
                                   start_new_session=serve)
        detail["host_pid"] = process.pid
        url = _wait_for_url(process, timeout=timeout)
        if url is None:
            output = process.stdout.read() if process.stdout else ""
            process.kill()
            fails.append("the host did not come up: no `dsh web:` line. **Startup is the thing that "
                         f"breaks** when an activation fails; output was: {output.strip()[-600:]}")
            return _result("dsh-client", checks, fails, detail, tools_seen=[], result_count=0)
        checks.append(f"host booted on {url.split('?')[0]} (startup check passed)")
        detail["url"] = url

        index = _get(url, cookies=home / "cookies.txt", timeout=timeout)
        graph = parse_boot_graph(index)
        entry = next((row for row in graph.get("entries", []) if row.get("id") == package["name"]), None)
        if entry is None:
            fails.append(f"the boot graph has no {package['name']} entry "
                         f"({len(graph.get('entries', []))} entries)")
        else:
            checks.append(f"boot graph entry: {json.dumps(entry)}")
            if list(entry.get("inject", [])) == declared_inject:
                checks.append(f"the host echoed the declared inject order ({len(declared_inject)} packages)")
            else:
                fails.append(f"inject mismatch: declared {declared_inject}, host said {entry.get('inject')}")
            # `base` keeps its trailing slash and the entry url is document-relative, so this is
            # `http://host:port/plugins/??…`. Joining with an extra slash (`//plugins/…`) makes the host
            # answer with its SPA fallback — a **200 carrying the index HTML** — which reads exactly like
            # "the bundle is not served". That false alarm cost a real debugging round on 2026-10-01, so
            # the assertion below also checks the content type, not just the bytes.
            base = url.split("?", 1)[0]
            served = _get(base + entry["url"], cookies=home / "cookies.txt", timeout=timeout)
            source = (repo / "lib" / "client.js").read_text(encoding="utf-8")
            if served.lstrip().startswith("<!doctype") or served.lstrip().startswith("<html"):
                fails.append("the combo route answered with HTML (looks like the SPA fallback, not a "
                             "bundle) — check the request URL before believing the bundle is missing")
            elif source.strip() in served:
                checks.append("the combo route serves lib/client.js verbatim (no build step, no chunk)")
            else:
                fails.append("the served bundle differs from lib/client.js")
            missing = [marker for marker in CLIENT_MARKERS if marker not in served]
            if missing:
                fails.append(f"the served bundle does not register the panel: missing {missing}")
            else:
                checks.append("the served bundle registers the panel in both seats")

        if check_uninstall:
            process.kill()
            subprocess.run([binary, "plugin", "--profile", "web", "remove", package["name"]],
                           capture_output=True, text=True, env=env, timeout=timeout)
            after = json.loads((home / "profiles" / "web" / "package.json").read_text(encoding="utf-8"))
            if package["name"] in after.get("dsh", {}).get("profile", {}).get("bundles", []):
                fails.append("remove left the bundle in the profile")
            else:
                checks.append("remove takes the bundle out of the profile")

        if serve:
            detail["hint"] = (f"left running for a human look (pid {process.pid}): {url}\n"
                              "  this is a throwaway DSH_HOME; your own profile was never touched")
        else:
            process.kill()
    finally:
        if not (keep or serve):
            shutil.rmtree(home, ignore_errors=True)
    return _result("dsh-client", checks, fails, detail, tools_seen=[], result_count=0)


def _free_port() -> int:
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_url(process: subprocess.Popen, *, timeout: int) -> str | None:
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return None
        line = process.stdout.readline() if process.stdout else ""
        url = parse_web_url(line)
        if url:
            return url
    return None


def _result(form: str, checks: list[str], fails: list[str], detail: dict,
            *, tools_seen: list[str], result_count: int) -> dict:
    """The artifact's shape: per-form detail a human or agent can read without prose.

    `checks` is what was measured and passed; `failures` is what failed. Both are lists of facts (names,
    counts, exit codes), because a reader of a *red* artifact needs the measurement, not the narrative.
    """
    return {
        "form": form,
        "ok": not fails,
        "timestamp": _now(),
        "query": SMOKE_QUERY,
        "tools_seen": tools_seen,
        "tool_count": len(tools_seen),
        "result_count": result_count,
        "checks": checks,
        "failures": fails,
        "detail": detail,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("form", choices=["npm-form", "git-stdio", "setup-installer", "dsh-client"],
                        help="which install form to exercise (dsh-client boots a throwaway host)")
    parser.add_argument("--repo", type=Path, default=REPO_FALLBACK,
                        help="checkout to pack / spawn the server from (default: this repository)")
    parser.add_argument("--out", type=Path, help="write the per-form JSON here (always written)")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--serve", action="store_true",
                        help="dsh-client: leave the throwaway host running and print its URL")
    parser.add_argument("--keep", action="store_true",
                        help="dsh-client: keep the throwaway DSH_HOME for inspection")
    parser.add_argument("--check-uninstall", action="store_true",
                        help="dsh-client: also assert that `remove` takes the bundle back out")
    parser.add_argument("--dry-run", action="store_true",
                        help="stop before the call: pack+shape checks for npm-form, interpreter+tool-set "
                             "for git-stdio (no network, no server spawn)")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    try:
        if args.form == "npm-form":
            result = probe_npm_form(repo, timeout=args.timeout, dry_run=args.dry_run)
        elif args.form == "setup-installer":
            result = probe_setup_installer(repo, timeout=args.timeout, dry_run=args.dry_run)
        elif args.form == "dsh-client":
            result = probe_dsh_client(repo, timeout=args.timeout, dry_run=args.dry_run,
                                      keep=args.keep, serve=args.serve,
                                      check_uninstall=args.check_uninstall)
        else:
            result = probe_git_stdio(repo, timeout=args.timeout, dry_run=args.dry_run)
    except Exception as error:   # noqa: BLE001 — a crash must still leave evidence, see the module docstring
        result = _result("npm" if args.form == "npm-form" else "git", [], [
            f"the probe crashed before it could measure anything: {type(error).__name__}: {error}"],
            {"traceback_form": args.form}, tools_seen=[], result_count=0)

    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    for failure in result["failures"]:
        print(f"install-smoke[{result['form']}]: FAIL {failure}", file=sys.stderr)
    if result["detail"].get("hint"):
        print(f"install-smoke[{result['form']}]: note {result['detail']['hint']}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
