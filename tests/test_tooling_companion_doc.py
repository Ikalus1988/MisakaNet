#!/usr/bin/env python3
"""The companion-server page must stay advice, not an installation.

`docs/agents/tooling-companions.md` tells agents how to read a repository alongside MisakaNet. Two things
could make it worse than nothing, and both are cheap to assert:

* it drifts into "we install it" — this repository must not configure, bundle or ship another MCP server.
  The installer it does ship is ours, with our endpoint; a second server means a user's GitHub token in
  our install path.
* it recommends a *write*-capable setup. Read-only is the whole safety story of that page: without
  `GITHUB_READ_ONLY=1`, the toolsets it lists include merging and closing.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "docs" / "agents" / "tooling-companions.md"
INSTALLER = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"


def test_the_page_exists_and_is_linked_from_the_mcp_doc():
    assert PAGE.is_file()
    mcp = (REPO / "docs" / "mcp.md").read_text(encoding="utf-8")
    assert "agents/tooling-companions.md" in mcp, "docs/mcp.md no longer points at the companion page"


def test_the_recommended_configuration_is_read_only():
    text = PAGE.read_text(encoding="utf-8")
    assert "GITHUB_READ_ONLY=1" in text, "the snippet dropped read-only mode"
    assert "GITHUB_TOOLSETS=context,repos,issues,pull_requests,actions" in text


def test_the_page_says_this_repository_does_not_ship_it():
    text = PAGE.read_text(encoding="utf-8")
    assert "does not install, bundle or ship it" in text


def test_the_installer_does_not_configure_a_second_server():
    """Measured on the file, not on prose: the installer must not mention the GitHub server at all."""
    source = INSTALLER.read_text(encoding="utf-8").lower()
    assert "github-mcp-server" not in source
    assert "githubcopilot.com/mcp" not in source


def test_writes_are_routed_away_from_the_mcp_server():
    text = PAGE.read_text(encoding="utf-8")
    assert "use `gh`/REST" in text, "the page must keep writes in an auditable path"
