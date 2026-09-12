#!/usr/bin/env python3
"""Onboarding snippets must stay copy-pasteable, MCP-first (2026-09-12, #1622).

The join-welcome comment is the *first* thing a new node executes, so a stale one
costs every new arrival: until this change it asked the new node to download the
1.1 MB `data/lessons.json` and search it locally, and never mentioned the remote
MCP endpoint — even though one HTTP call does the same job in ~1s and is the same
interface they will use to contribute.

Two facts verified against production on 2026-09-12 and encoded here:

* `Origin` is **not** required — absent is 200 OK, and only an *invalid* value gets
  `403 Forbidden: invalid Origin` (AGENTS.md and the troubleshooting table said
  "缺了会失败", which sent people hunting a non-existent failure);
* the anonymous read quota is 5/day/IP, which shared egress IPs (corporate NAT, CI
  runners) exhaust immediately — so the welcome has to hand over the
  `misakanet_register` call, not just mention that it exists.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENDPOINT = "https://misakanet.org/mcp"
PROTOCOL_HEADER = "MCP-Protocol-Version: 2025-06-18"
ORIGIN_HEADER = "Origin: https://misakanet.org"

WELCOME_WORKFLOWS = (
    ".github/workflows/register.yml",          # the join flow (#1622's comment)
    ".github/workflows/newbie-welcome.yml",
    ".github/workflows/pr-welcome.yml",
)


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_every_onboarding_snippet_uses_the_remote_endpoint():
    offenders = []
    for rel in WELCOME_WORKFLOWS:
        text = _read(rel)
        for needle, label in ((ENDPOINT, "endpoint"), (PROTOCOL_HEADER, "protocol header"),
                              (ORIGIN_HEADER, "Origin header")):
            if needle not in text:
                offenders.append(f"{rel}: missing {label} ({needle})")
    assert offenders == [], "\n  - ".join(["copy-pasteable MCP snippets are required:"] + offenders)


def test_join_welcome_puts_mcp_before_the_download():
    """MCP-first ordering, not just presence: the download is the fallback."""
    text = _read(".github/workflows/register.yml")
    assert ENDPOINT in text and "lessons.json" in text
    assert text.index(ENDPOINT) < text.index("lessons.json"), (
        "the join welcome must lead with the remote MCP call; the local index "
        "download belongs in the offline fallback (it is ~1.1 MB and needs the "
        "agent to implement its own search)"
    )


def test_join_welcome_covers_read_contribute_and_the_quota_escape():
    text = _read(".github/workflows/register.yml")
    for tool in ("misakanet_search", "misakanet_submit_intake", "misakanet_register"):
        assert tool in text, f"join welcome must mention {tool}"


def test_worker_welcome_comment_points_at_the_endpoint():
    text = _read("workers/register-proxy.js")
    assert ENDPOINT in text, "the MCP-side welcome comment must give the endpoint"
    assert "misakanet_register" in text, "…and the quota escape hatch"


def test_docs_describe_the_origin_header_accurately():
    """Absent Origin is accepted; only an invalid value is rejected."""
    agents = _read("AGENTS.md")
    assert "invalid Origin" in agents
    assert "缺了会失败" not in agents, (
        "AGENTS.md claimed the Origin header is mandatory; production returns 200 "
        "without it, so the claim sends people hunting a failure that cannot happen"
    )
    troubleshooting = _read("docs/agents/repo-operations.md")
    assert "缺席=200" in troubleshooting, (
        "the 403 troubleshooting row must say that a missing Origin is fine and an "
        "invalid value is what fails"
    )
