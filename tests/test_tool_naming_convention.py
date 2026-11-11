#!/usr/bin/env python3
"""Tool names are a public protocol surface: the convention applies to new tools, the old names stay.

#4409 measured the set as eleven names in three shapes (verb_noun, bare noun phrases, and the `me_`
family) and the owner chose option (b): **freeze the names, apply one convention to new tools, and
declare the difference instead of "fixing" it**. A rename would touch clients, agent prompts, both
surfaces, the plugins, the installer and the registry entry for a fraction of a directory's score.

This test is the declaration's gate: a new tool must either follow the convention or be added to
`FROZEN_NAMES` **and** to the list in `docs/mcp.md`, so an undeclared deviation cannot ship quietly.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.server.tools import TOOLS as LOCAL_TOOLS  # noqa: E402

#: Reads: `get_<noun>` / `search_<noun>` (node-scoped: `get_my_<noun>`). Writes: `write_<noun>` /
#: `submit_<noun>`.
CONVENTION = re.compile(r"^misakanet_(get|search|write|submit)_[a-z0-9_]+$")

#: The names that predate the convention and stay. Each one is in `docs/mcp.md` § Tool naming.
FROZEN_NAMES = {
    "misakanet_search",
    "misakanet_register",
    "misakanet_preflight",
    "misakanet_usage_status",
    "misakanet_memory_context",
    "misakanet_me_events",
    "misakanet_me_inbox",
}


def local_names() -> set[str]:
    return {tool["name"] for tool in LOCAL_TOOLS}


def hosted_names() -> set[str]:
    source = (REPO / "workers" / "register-proxy-sw.js").read_text(encoding="utf-8")
    block = source.split("const MCP_TOOLS = [", 1)[1].split("];", 1)[0]
    return set(re.findall(r'name:\s*"([a-z0-9_]+)"', block))


def test_every_tool_either_follows_the_convention_or_is_declared_frozen():
    for surface, names in (("stdio", local_names()), ("hosted", hosted_names())):
        undeclared = {n for n in names if not CONVENTION.match(n)} - FROZEN_NAMES
        assert not undeclared, (
            f"{surface}: {sorted(undeclared)} deviates from the naming convention and is not in "
            "FROZEN_NAMES. Rename it to misakanet_<get|search|write|submit>_<noun>, or add it to "
            "FROZEN_NAMES and to docs/mcp.md § Tool naming with the reason."
        )


def test_the_frozen_set_matches_the_documented_list():
    doc = (REPO / "docs" / "mcp.md").read_text(encoding="utf-8")
    section = doc.split("## Tool naming", 1)[1].split("## Available Tools", 1)[0]
    missing = sorted(name for name in FROZEN_NAMES if name not in section)
    assert not missing, f"docs/mcp.md § Tool naming does not name {missing}; the gate and the doc drifted"


def test_the_declaration_is_still_the_whole_deviation():
    """If a frozen name is renamed to fit the convention, the exemption must go with it."""
    stale = sorted(FROZEN_NAMES - local_names())
    assert not stale, (
        f"{stale} is listed as frozen but no longer exists; remove it from FROZEN_NAMES and from "
        "docs/mcp.md § Tool naming"
    )
