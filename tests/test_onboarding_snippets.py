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


# Live *usages* of the deleted legacy worker — not the historical mentions in
# comments and handoffs, which are what document why it is gone.
LEGACY_USAGE_PATTERNS = (
    re.compile(r'href="[^"]*register-proxy\.js"'),          # site source link
    re.compile(r"""from\s+['"]\./register-proxy\.js['"]"""),  # node test import
    re.compile(r"(read_text|Path)\([^)]*register-proxy\.js"),  # pytest source read
    re.compile(r'^\s*-\s*"workers/register-proxy\.js"', re.M),  # workflow path filter
)

SKIP_DIRS = {".git", ".pnpm-store", "node_modules", ".archify-tool", ".tools", "reports"}


def test_the_deleted_legacy_worker_has_no_live_references():
    """`workers/register-proxy.js` was a 658-line copy nothing deploys (2026-09-12).

    Docs presented it as "the worker", tests imported it, and the site linked to it as
    the source — so it was misleading *and* green-while-untested. It is deleted; these
    patterns would bring it back.
    """
    offenders = []
    for path in REPO.rglob("*"):
        if not path.is_file() or path.suffix not in (".md", ".html", ".yml", ".yaml", ".js", ".mjs", ".py", ".json", ".jsonc"):
            continue
        if SKIP_DIRS & set(path.parts):
            continue
        if path.name.startswith("handoff-") or path.name == "hardening-field-report.md":
            continue  # dated snapshots keep their own history
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern in LEGACY_USAGE_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(REPO)}:{line}: {match.group(0)[:60]}")
    assert offenders == [], (
        "live references to the deleted legacy worker (use workers/register-proxy-sw.js, "
        "the wrangler entry):\n  - " + "\n  - ".join(offenders)
    )


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
