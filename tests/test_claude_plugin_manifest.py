#!/usr/bin/env python3
"""MisakaNet must be installable where its users already are — including Claude Code.

Why this file exists
--------------------
Of the last 100 intakes, **codex (38%) and claude-code (27%)** are two thirds of everyone who reports a
failure. Codex has a native plugin channel here (`.codex-plugin/plugin.json`, shipped in the npm bundle) —
Claude Code had none, so its users were served only by the installer (`npx @misaka-net/misakanet-setup`),
which is why the installer's downloads sat an order of magnitude below the plugin's. The fix is a channel,
not a download campaign.

The shape is taken from working plugins rather than invented (`exa-labs/exa-mcp-server`,
`cloudflare/skills`, `mozilla-ai/cq` — all measured 2026-09-30): a repository-root `.claude-plugin/plugin.json`
declaring `mcpServers`, plus a `.claude-plugin/marketplace.json` whose one entry points at `"./"`.

Four rules, all of them the "documented pattern must still hold" kind:

1. both manifests parse, and the marketplace's single entry resolves to the plugin manifest;
2. the endpoint the plugin registers is **the** endpoint (`docs/mcp.md`), not a copy that can drift;
3. the two channels (Codex, Claude Code) register the *same* endpoint — two front doors to different servers
   would be worse than one front door;
4. no credential ships in either manifest: they are published artifacts, and anonymous reads are unlimited.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / ".claude-plugin" / "plugin.json"
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
MCP_DOC = REPO / "docs" / "mcp.md"
CODEX = REPO / ".codex-plugin" / "plugin.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def documented_endpoint(text: str | None = None) -> str:
    """The endpoint `docs/mcp.md` publishes. Lifted from the document so the two cannot disagree."""
    body = text if text is not None else MCP_DOC.read_text(encoding="utf-8")
    found = re.search(r"https://misakanet\.org/mcp\b", body)
    assert found, "docs/mcp.md no longer names the endpoint — this rule must follow the document"
    return found.group(0)


def manifest_problems(marketplace_text: str, plugin_text: str | None, endpoint: str) -> list[str]:
    """Broken linkage, a wrong endpoint, or a credential — as a list, so a fixture can drive it."""
    problems: list[str] = []
    try:
        market = json.loads(marketplace_text)
    except json.JSONDecodeError as exc:
        return [f"marketplace.json is not JSON: {exc}"]
    plugins = market.get("plugins") or []
    if len(plugins) != 1:
        problems.append(f"the marketplace lists {len(plugins)} plugins; this repository is one")
        return problems
    entry = plugins[0]
    if entry.get("name") != market.get("name"):
        problems.append(f"the plugin is named {entry.get('name')!r} inside marketplace "
                        f"{market.get('name')!r}; `install <plugin>@<marketplace>` needs both")
    if entry.get("source") != "./":
        problems.append(f"the plugin source is {entry.get('source')!r}; a root plugin is './'")
    if plugin_text is None:
        problems.append("the marketplace points at a source that has no .claude-plugin/plugin.json")
        return problems
    try:
        plugin = json.loads(plugin_text)
    except json.JSONDecodeError as exc:
        return [f"plugin.json is not JSON: {exc}"]
    servers = plugin.get("mcpServers") or {}
    if not servers:
        problems.append("plugin.json declares no mcpServers, so the plugin adds no tools")
    for name, spec in servers.items():
        if spec.get("url") != endpoint:
            problems.append(f"mcpServers.{name}.url is {spec.get('url')!r}, not {endpoint!r}")
        if spec.get("type") != "http":
            problems.append(f"mcpServers.{name}.type is {spec.get('type')!r}; the hosted endpoint is http")
    if re.search(r"Bearer\s|mcp_[A-Za-z0-9]", json.dumps(plugin) + marketplace_text):
        problems.append("a credential appears in a published manifest — anonymous reads need no token")
    return problems


def test_the_marketplace_resolves_to_this_repositorys_plugin():
    assert manifest_problems(MARKETPLACE.read_text(encoding="utf-8"), PLUGIN.read_text(encoding="utf-8"),
                             documented_endpoint()) == []


def test_the_plugin_registers_the_documented_endpoint_over_http():
    plugin = _load(PLUGIN)
    spec = (plugin.get("mcpServers") or {}).get("misakanet") or {}
    assert spec.get("url") == documented_endpoint(), (
        "the plugin must register the endpoint docs/mcp.md publishes, not a second copy of the URL")
    assert spec.get("type") == "http"


def test_both_agent_channels_point_at_the_same_server():
    """Codex and Claude Code are two front doors; two doors to different servers is worse than one."""
    codex = _load(CODEX)
    claude = _load(PLUGIN)
    codex_urls = set(re.findall(r"https://misakanet\.org/mcp", json.dumps(codex)))
    claude_urls = set(re.findall(r"https://misakanet\.org/mcp", json.dumps(claude)))
    assert codex_urls or (REPO / "cordis.patch.yml").read_text(encoding="utf-8").count(
        "https://misakanet.org/mcp"), "the Codex channel registers no endpoint at all"
    assert claude_urls, "the Claude Code channel registers no endpoint"
    assert documented_endpoint() in json.dumps(claude)


def test_no_manifest_ships_a_credential():
    for path in (PLUGIN, MARKETPLACE):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"Bearer\s|mcp_[A-Za-z0-9]{8,}", text), (
            f"{path.name} carries a credential; both are published artifacts")


def test_the_linkage_rule_notices_a_marketplace_pointing_nowhere():
    """Guard: the rule reads real files, so its red case needs fixtures."""
    broken = json.dumps({"name": "misakanet", "plugins": [{"name": "misakanet", "source": "./plugins/nope"}]})
    assert manifest_problems(broken, None, documented_endpoint()), "an unresolvable source must be reported"
    good = _load(MARKETPLACE).copy()
    good["plugins"] = [{"name": "other", "source": "./"}]
    assert any("install" in problem for problem in
               manifest_problems(json.dumps(good), PLUGIN.read_text(encoding="utf-8"), documented_endpoint()))
