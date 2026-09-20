#!/usr/bin/env python3
"""Two installers, one contract — and nobody was checking they agreed.

`npx @misaka-net/misakanet-setup` (packages/misakanet-setup/bin/misakanet-setup.mjs) and the
bootstrap route (integrations/agent-autostart/install_misakanet_agent.py) write the same agent
configs, and they are maintained separately. Adding Cursor to the npm installer alone was the
obvious way to do it, and it would have left the offline/bootstrap user — the one whose network is
hostile enough to need a bootstrap script — without the target the README advertises.

The one intentional difference is `dsh`: the Python installer also drops a `SKILL.md` for the
DeepSeek Harness plugin channel, which is not an MCP config file and has no npm counterpart. So the
invariant is: the npm targets must all exist in the Python installer, and the only target the Python
installer may have beyond them is `dsh`.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
NPM = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
PY = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"

ALLOWED_PY_ONLY = {"dsh"}


def npm_targets() -> list[str]:
    match = re.search(r"^const AGENTS = \[([^\]]+)\]", NPM.read_text(encoding="utf-8"), re.M)
    assert match, "the npm installer's AGENTS array moved; fix this gate rather than deleting it"
    return re.findall(r"'([^']+)'", match.group(1))


def python_targets() -> list[str]:
    match = re.search(r"^AGENTS = \(([^)]+)\)", PY.read_text(encoding="utf-8"), re.M)
    assert match, "the python installer's AGENTS tuple moved; fix this gate rather than deleting it"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_the_two_installers_declare_the_same_targets():
    npm, py = set(npm_targets()), set(python_targets())
    missing = sorted(npm - py)
    extra = sorted(py - npm - ALLOWED_PY_ONLY)
    assert not missing, (
        f"the npm installer targets {missing} but the bootstrap installer does not: an offline "
        f"user would silently get fewer agents than the README advertises"
    )
    assert not extra, (
        f"the bootstrap installer targets {extra} with no npm counterpart. If that is intentional, "
        f"add it to ALLOWED_PY_ONLY with the reason; otherwise the two are drifting"
    )


def test_every_declared_target_is_actually_implemented_in_both():
    """A name in the list with no writer is worse than a missing name: it looks supported.

    Two implementation shapes are legitimate: a bespoke `installX()` function, or a row in the
    table-driven `MCP_ONLY_TARGETS` (one JSON file, one entry, no behaviour layer). Both installers
    must contain one or the other for every declared target.
    """
    npm_src = NPM.read_text(encoding="utf-8")
    py_src = PY.read_text(encoding="utf-8")
    problems = []
    for target in npm_targets():
        camel = "".join(part.title() for part in target.split("-"))
        npm_bespoke = f"async function install{camel}(" in npm_src
        npm_table = re.search(rf"^  {target}: \{{", npm_src, re.M) is not None
        if not (npm_bespoke or npm_table):
            problems.append(f"npm: neither install{camel}() nor an MCP_ONLY_TARGETS row")
        py_bespoke = f"def install_{target}(" in py_src
        py_table = f'"{target}": {{' in py_src
        if not (py_bespoke or py_table):
            problems.append(f"python: neither install_{target}() nor an MCP_ONLY_TARGETS row")
        if f"'{target}': install_" not in py_src and f'"{target}": install_' not in py_src \
                and f"partial(install_mcp_only, agent=a) for a in MCP_ONLY_TARGETS" not in py_src:
            problems.append(f"python: INSTALLERS has no {target} entry")
    assert not problems, "; ".join(problems)


SHAPES = [
    # agent, npm marker, python marker — the two installers must not disagree about a vendor's shape.
    # Cursor and Kiro take a bare `url`; the entry must carry no `type` key for either (that is the
    # Claude Code entry's shape, and Cursor's docs show none) — the node/pytest suites assert the
    # written files themselves, this only pins that both installers declare the same intent.
    ("cursor", "urlField: 'url'", '"url_field": "url"'),
    ("gemini", "urlField: 'httpUrl'", '"url_field": "httpUrl"'),
    ("copilot", "{ type: 'http', url: ENDPOINT", 'entry["type"] = "http"'),
    ("opencode", "container: 'mcp',", '"container": "mcp",'),
    ("kiro", "urlField: 'url'", '"url_field": "url"'),
]


@pytest.mark.parametrize("agent,npm_marker,py_marker", SHAPES)
def test_both_installers_agree_on_every_vendor_shape(agent, npm_marker, py_marker):
    """The shapes are the point: `httpUrl` vs `url`, `mcp` vs `mcpServers`, `type` or not.

    Two installers writing the same client differently is the failure this catches — and a wrong key
    is silent (the server never appears), so nothing else would notice.
    """
    npm_src = NPM.read_text(encoding="utf-8")
    py_src = PY.read_text(encoding="utf-8")
    assert f"  {agent}: {{" in npm_src, f"npm: no MCP_ONLY_TARGETS row for {agent}"
    assert npm_marker in npm_src, f"npm: {agent} is missing {npm_marker!r}"
    assert f'"{agent}": {{' in py_src, f"python: no MCP_ONLY_TARGETS row for {agent}"
    assert py_marker in py_src, f"python: {agent} is missing {py_marker!r}"
