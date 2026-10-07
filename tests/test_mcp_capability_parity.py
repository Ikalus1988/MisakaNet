#!/usr/bin/env python3
"""The two install forms must expose *one declared* tool surface (owner decision D4=A).

The defect this gate exists for (#2000, reported again as #2486)
--------------------------------------------------------------
`misakanet_me_events` was hosted-only. A local stdio install
(`python3 scripts/mcp_server.py`) did not register it, so the skill's own reuse-evidence step —
the one flow that asks an agent to verify its contribution was actually reused — answered
`Unknown tool: misakanet_me_events`. Worse, neither set contained the other: hosted was missing
three stdio-only tools and stdio was missing the one hosted-only tool, so "which tools do I have?"
had no single answer an agent could carry between installs.

What is pinned here
-------------------
1. `.codex-plugin/plugin.json` declares both transports and **both tool sets** — the manifest is
   what a plugin market (and an agent reading the install channel) can read without a checkout;
2. the declared hosted set equals the worker's registered set *and* the `AGENTS.md` §3.2 table
   (the same two legs `scripts/sync_lesson_count.canonical_mcp_tools()` cross-checks, so the
   manifest cannot introduce a third, private opinion);
3. the declared local set equals what `scripts/mcp_server.py` actually registers
   (`misakanet/server/tools.py`) and what `protocol.py` can dispatch — a tool that is listed but
   not dispatchable is the same "Unknown tool" failure wearing a different hat;
4. the two surfaces now agree on `misakanet_me_events`, schema included, because the local server
   proxies the hosted definition rather than inventing a second one;
5. `docs/dsh-installation.md`'s three-forms table states counts and the local-only names that the
   manifest and the server agree with;
6. the local `misakanet_me_events` answers offline with a stated error instead of raising.

Structural, not prose: every assertion reads a JSON field, a parsed table cell, a registered tool
name, or a JSON-RPC response.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.mcp_server import TOOLS as LOCAL_TOOLS  # noqa: E402
from scripts.mcp_server import handle_request  # noqa: E402
from scripts.sync_lesson_count import (  # noqa: E402
    documented_hosted_tools,
    registered_hosted_tools,
)

PLUGIN = REPO / ".codex-plugin" / "plugin.json"
WORKER = REPO / "workers" / "register-proxy-sw.js"
TOOLS_PY = REPO / "misakanet" / "server" / "tools.py"
PROTOCOL = REPO / "misakanet" / "server" / "protocol.py"
GUIDE = REPO / "docs" / "dsh-installation.md"
SKILL_FILES = (REPO / "SKILL.md", REPO / "skills" / "misakanet" / "SKILL.md")

ME_EVENTS = "misakanet_me_events"
# Tools the local stdio server is *allowed* to have and the hosted endpoint is not: they read this
# checkout's own usage meter and `lessons/` corpus, so there is nothing for a hosted endpoint to
# answer. The direction that caused #2000 was the opposite one (hosted-only tools), and it is now
# empty — see `test_the_hosted_set_is_a_subset_of_the_local_set`.
LOCAL_ONLY = {
    "misakanet_submit_usage",
    "misakanet_usage_status",
    "misakanet_memory_context",
}
HOSTED_ENDPOINT = "https://misakanet.org/mcp"


# ── readers: the files, not the prose ────────────────────────────────────────────────────────────

def _manifest() -> dict:
    return json.loads(PLUGIN.read_text(encoding="utf-8"))


def _local_tool_names() -> set[str]:
    return {tool["name"] for tool in LOCAL_TOOLS}


def _dispatchable_tool_names() -> set[str]:
    """Tools `handle_request` can route — parsed from the JSON-RPC dispatch table."""
    return set(re.findall(
        r'"(misakanet_[a-z_]+)":\s*handle_', PROTOCOL.read_text(encoding="utf-8")
    ))


def _hosted_tool_definitions() -> dict[str, dict]:
    """The worker's `MCP_TOOLS` array, parsed from source (the offline source of truth).

    Parsed rather than evaluated: running the worker module would execute the whole edge handler.
    `MCP_TOOLS` is an array of plain object literals, so a string-aware pass that quotes the bare
    keys and drops the trailing commas turns it into JSON. This is the same file
    `scripts/sync_lesson_count.registered_hosted_tools()` reads for the *names*; the definitions are
    needed here because the local proxy must not drift from the hosted schema.
    """
    text = WORKER.read_text(encoding="utf-8")
    start = text.index("const MCP_TOOLS = [")
    cursor = text.index("[", start)
    depth, in_string, escaped = 0, False, False
    while cursor < len(text):
        char = text[cursor]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                break
        cursor += 1
    source = text[text.index("[", start):cursor + 1]

    out: list[str] = []
    index, in_string, escaped = 0, False, False
    while index < len(source):
        char = source[index]
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        # A `//` comment inside `MCP_TOOLS`. This pass was string-aware but not comment-aware, so
        # a comment explaining a schema — the natural thing to add next to one — broke
        # `json.loads` with an error pointing at the comment rather than at the schema. Comments
        # are not JSON; drop them the way a JS parser would, and only outside strings.
        if char == "/" and source[index + 1:index + 2] == "/":
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline
            continue
        if char == ",":  # JS allows a trailing comma; JSON does not
            if source[index + 1:].lstrip()[:1] in ("}", "]"):
                index += 1
                continue
            out.append(char)
            index += 1
            continue
        if char.isalpha() or char == "_":
            ident = re.match(r"[A-Za-z_][A-Za-z0-9_]*", source[index:])
            if ident and source[index + len(ident.group(0)):].lstrip().startswith(":"):
                out.append(f'"{ident.group(0)}"')
                index += len(ident.group(0))
                continue
        out.append(char)
        index += 1

    tools = json.loads("".join(out))
    return {tool["name"]: tool for tool in tools}


def _guide_form_rows() -> dict[str, str]:
    """The three install-form rows of `docs/dsh-installation.md`, keyed by form.

    Scoped to the `## Choosing an install form` section so a `misakanet_*` token elsewhere on the
    page cannot satisfy these assertions.

    The install command is matched by *shape*, not by a literal string (2026-10-02). It used to look
    for `dsh plugin add misakanet`, which pinned a command that cannot run — `--profile` is required —
    and so broke the moment the guide was corrected. `(?:--profile \\S+ )?` accepts the flag and any
    profile name, so fixing or renaming a profile can no longer red a test that is about tool counts.
    """
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("## Choosing an install form")
    end = text.find("\n## ", start + 1)
    body = text[start:end if end != -1 else len(text)]
    rows = {}
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        if re.search(r"dsh plugin (?:--profile \S+ )?add misakanet\b", line):
            rows["npm"] = line
        elif re.search(r"dsh plugin (?:--profile \S+ )?add github:Ikalus1988/MisakaNet\b", line):
            rows["git+"] = line
        elif "cp -r skills/misakanet" in line:
            rows["manual"] = line
    return rows


def _declared_count(row: str) -> int | None:
    """The bold **N** in a row's "MCP tools you get" cell, if it states one."""
    found = re.search(r"\*\*(\d+)\*\*", row)
    return int(found.group(1)) if found else None


# ── the manifest declares both surfaces ──────────────────────────────────────────────────────────

def test_the_manifest_declares_the_hosted_transport_and_the_local_variant():
    data = _manifest()
    mcp = data.get("mcp")
    assert mcp, (
        ".codex-plugin/plugin.json has no `mcp` capability block, so the two install forms' tool "
        "surfaces are not machine-readable (D4=A, intake #2486)"
    )
    assert mcp.get("transport") == "http", mcp
    assert mcp.get("url") == HOSTED_ENDPOINT, mcp

    local = mcp.get("local")
    assert local, "the manifest declares only the hosted surface; the local stdio one is undocumented"
    assert local.get("transport") == "stdio", local
    assert "scripts/mcp_server.py" in " ".join(local.get("args") or []), local


def test_the_manifest_keeps_the_keys_the_plugin_contract_already_reads():
    """The capability block is an addition, not a rewrite: #1677's discovery fields stay put."""
    data = _manifest()
    assert data.get("name") == "misakanet"
    assert data.get("skills") == "./skills/"
    assert isinstance(data.get("interface"), dict)
    assert isinstance(data.get("keywords"), list)
    assert data.get("version"), "the version key scripts/align_versions.py compares is gone"


# ── the declared sets equal the real ones ────────────────────────────────────────────────────────

def test_the_manifest_hosted_tools_are_the_workers_and_the_agents_md_table():
    mcp = _manifest()["mcp"]
    declared = set(mcp.get("tools") or [])
    assert declared, "mcp.tools is empty"
    assert declared == registered_hosted_tools(), {
        "manifest only": sorted(declared - registered_hosted_tools()),
        "worker only": sorted(registered_hosted_tools() - declared),
    }
    assert declared == documented_hosted_tools(), {
        "manifest only": sorted(declared - documented_hosted_tools()),
        "AGENTS.md §3.2 only": sorted(documented_hosted_tools() - declared),
    }
    assert len(declared) == 7, sorted(declared)


def test_the_manifest_local_tools_are_what_the_stdio_server_registers():
    local = _manifest()["mcp"]["local"]
    declared = set(local.get("tools") or [])
    assert declared, "mcp.local.tools is empty"
    assert declared == _local_tool_names(), {
        "manifest only": sorted(declared - _local_tool_names()),
        "misakanet/server/tools.py only": sorted(_local_tool_names() - declared),
    }
    assert len(declared) == 10, sorted(declared)


def test_every_declared_local_tool_is_dispatchable():
    """A name in `tools/list` that `tools/call` cannot route is the #2000 failure again."""
    dispatchable = _dispatchable_tool_names()
    declared = set(_manifest()["mcp"]["local"]["tools"])
    assert declared - dispatchable == set(), (
        f"{sorted(declared - dispatchable)} are declared and registered but missing from "
        "misakanet/server/protocol.py `_HANDLERS`, so calling them answers 'Unknown tool'"
    )
    assert dispatchable - _local_tool_names() == set(), (
        f"{sorted(dispatchable - _local_tool_names())} are dispatchable but absent from tools.py"
    )


# ── D4=A: the hosted set is now a subset of the local set ────────────────────────────────────────

def test_the_hosted_set_is_a_subset_of_the_local_set():
    """The owner decision: align the surfaces, and declare the difference in one direction only.

    Before this change neither set contained the other (`me_events` hosted-only, three tools
    stdio-only). Now the only difference is the three genuinely local tools, and every tool the
    hosted endpoint teaches is callable on a local install — which is what makes the skill's
    reuse-evidence step work on both.
    """
    hosted = set(_manifest()["mcp"]["tools"])
    local = set(_manifest()["mcp"]["local"]["tools"])
    assert hosted - local == set(), f"still hosted-only: {sorted(hosted - local)} (#2000)"
    assert local - hosted == LOCAL_ONLY, {
        "unexpected local-only": sorted((local - hosted) - LOCAL_ONLY),
        "declared local-only but now hosted": sorted(LOCAL_ONLY - (local - hosted)),
    }
    assert ME_EVENTS in hosted and ME_EVENTS in local


def test_the_local_me_events_definition_matches_the_hosted_one():
    """The proxy must not invent its own argument names or output contract."""
    hosted = _hosted_tool_definitions()[ME_EVENTS]
    local = next(tool for tool in LOCAL_TOOLS if tool["name"] == ME_EVENTS)
    assert local["inputSchema"] == hosted["inputSchema"], {
        "local": local["inputSchema"],
        "hosted": hosted["inputSchema"],
    }
    assert hosted["description"] in local["description"], (
        "the local description no longer carries the hosted definition's own words, so the two "
        "surfaces can teach different behaviour for the same tool name"
    )


# ── the local server answers, offline-safely ─────────────────────────────────────────────────────

def _call_local(name: str, arguments: dict) -> dict:
    return handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


def test_tools_list_advertises_me_events_locally():
    response = handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert ME_EVENTS in names, (
        "the local stdio server does not advertise misakanet_me_events — the skill's reuse-evidence "
        "step fails with 'Unknown tool' here (intake #2000)"
    )


def test_the_local_server_can_route_a_me_events_call():
    """Red before the fix: this was a JSON-RPC `-32601 Unknown tool`."""
    response = _call_local(ME_EVENTS, {"lesson_id": "dco-auto-fix-workflow"})
    assert "error" not in response, (
        "misakanet_me_events is not routable on the local stdio server: "
        f"{response.get('error')}"
    )
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload.get("code") != "unknown_tool"
    assert "lesson_id" in payload or payload.get("error"), payload


def test_a_missing_reference_is_refused_without_a_network_call(monkeypatch):
    """Mirrors the hosted schema (`oneOf`: at least one of the two) before spending a round-trip."""
    called = []

    def fail_if_called(*args, **kwargs):  # pragma: no cover - only runs on a regression
        called.append(args)
        raise AssertionError("the proxy went to the network for an empty reference")

    monkeypatch.setattr("misakanet.remote.call", fail_if_called)
    payload = json.loads(
        _call_local(ME_EVENTS, {})["result"]["content"][0]["text"]
    )
    assert payload["error"], payload
    assert payload["code"] == "missing_lesson_reference", payload
    assert called == []


def test_the_proxy_passes_the_reference_through(monkeypatch):
    seen = {}

    def fake_call(tool, arguments, **kwargs):
        seen["tool"] = tool
        seen["arguments"] = arguments
        return {"lesson_id": "dco-auto-fix-workflow", "events": [], "evidence": "E0", "note": "ok"}

    monkeypatch.setattr("misakanet.remote.call", fake_call)
    payload = json.loads(
        _call_local(ME_EVENTS, {"lesson_path": "lessons/core/dco-auto-fix-workflow.md"})
        ["result"]["content"][0]["text"]
    )
    assert seen["tool"] == ME_EVENTS, seen
    assert seen["arguments"] == {"lesson_path": "lessons/core/dco-auto-fix-workflow.md"}, seen
    assert payload["evidence"] == "E0", payload


def test_no_network_is_an_error_not_a_crash(monkeypatch):
    """The hosted service owns this evidence; the local server must say so, not fall over.

    `protocol.main` turns a raising handler into a JSON-RPC internal error and keeps serving, but an
    agent reading `{events: []}` would conclude "no reuse evidence" — a different and false claim.
    """
    from misakanet import remote

    def offline(*args, **kwargs):
        raise remote.RemoteError("https://misakanet.org/mcp unreachable (network is down)")

    monkeypatch.setattr("misakanet.remote.call", offline)
    payload = json.loads(
        _call_local(ME_EVENTS, {"lesson_id": "dco-auto-fix-workflow"})["result"]["content"][0]["text"]
    )
    assert payload["code"] == "hosted_endpoint_unavailable", payload
    assert "unreachable" in payload["error"], payload
    assert "events" not in payload, (
        "an offline proxy returned an events list — 'no evidence' and 'could not read the evidence' "
        "are not the same answer"
    )


# ── the install guide and the skill copies state the aligned surfaces ────────────────────────────

def test_the_install_guide_counts_match_the_manifest():
    rows = _guide_form_rows()
    assert set(rows) == {"npm", "git+", "manual"}, sorted(rows)
    mcp = _manifest()["mcp"]

    assert _declared_count(rows["npm"]) == len(mcp["tools"]), (
        f"npm row says {_declared_count(rows['npm'])} tools, manifest declares {len(mcp['tools'])}"
    )
    assert _declared_count(rows["git+"]) == len(mcp["local"]["tools"]), (
        f"git+ row says {_declared_count(rows['git+'])} tools, manifest declares "
        f"{len(mcp['local']['tools'])}"
    )
    assert _declared_count(rows["manual"]) is None, (
        "the manual skill install wires no MCP row, so it must not promise a tool count"
    )


def test_the_install_guide_names_only_tools_the_form_actually_has():
    rows = _guide_form_rows()
    mcp = _manifest()["mcp"]
    named_npm = set(re.findall(r"misakanet_[a-z_]+", rows["npm"]))
    named_git = set(re.findall(r"misakanet_[a-z_]+", rows["git+"]))
    assert named_npm <= set(mcp["tools"]), (
        f"the npm row names {sorted(named_npm - set(mcp['tools']))}, which the hosted form lacks"
    )
    assert named_git <= set(mcp["local"]["tools"]), (
        f"the git+ row names {sorted(named_git - set(mcp['local']['tools']))}, which the local form "
        "lacks — this is the stale 'local does not have me_events' claim (intake #2000)"
    )
    # The local-only difference is *declared*, not implied: the git+ row must name all three.
    assert LOCAL_ONLY <= named_git, f"the git+ row does not name {sorted(LOCAL_ONLY - named_git)}"


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.as_posix())
def test_a_skill_no_longer_claims_the_local_install_lacks_me_events(path):
    """The statement that was true until 2026-09-30 and is now false about the *fact* it fixes."""
    text = path.read_text(encoding="utf-8")
    # The false claim was a sentence pairing me_events with "does not have". The replacement claim
    # names the three tools that genuinely are local-only; assert on that fact instead.
    for tool in LOCAL_ONLY:
        assert tool in text, (
            f"{path.name} does not name {tool}, so a reader cannot tell which tools are local-only "
            "now that misakanet_me_events exists on both surfaces (intake #2000)"
        )
    assert not re.search(r"does\s+\*{0,2}not\*{0,2}\s+have\s+`?misakanet_me_events", text), (
        f"{path.name} still says the local install lacks misakanet_me_events — it now proxies it"
    )
