#!/usr/bin/env python3
"""The published contracts an agent reads first: tool arguments, open tools, and what may be crawled.

Three errors found by a live architecture review (2026-09-29), each verified against the running service
before it was fixed:

* `API.md` documented `misakanet_get_lesson`'s argument as `path_or_id`. The tool's schema has `id` and
  `path`; calling it the documented way returns `invalid_lesson_path` on the first call an agent makes.
* `docs/.well-known/agent.json` listed four `publicTools`, while `misakanet_search`,
  `misakanet_get_lesson` and `misakanet_me_events` all answer anonymously (the repository's own AGENTS.md
  §3.3 says so). A machine-readable card that understates the open surface makes a client ask permission
  it does not need.
* `docs/robots.txt` disallowed `/api/` for `User-agent: *` and then allowed it back for ten named AI
  crawlers, which is how robots.txt groups work: the most specific group wins, so the named ones could
  fetch `/api/analytics` — the endpoint that serves search text and per-client counts.

Each rule here can fail, and each has a fixture-driven guard where the repository itself is the input.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROBOTS = REPO / "docs" / "robots.txt"
CARD = REPO / "docs" / ".well-known" / "agent.json"
API_MD = REPO / "API.md"


def robots_groups(text: str) -> list[tuple[str, list[str]]]:
    """`(user-agent, directives)` for every group in a robots.txt body."""
    groups: list[tuple[str, list[str]]] = []
    agent, directives = None, []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            if agent is not None:
                groups.append((agent, directives))
            agent, directives = value, []
        elif agent is not None:
            directives.append(f"{key}: {value}".lower())
    if agent is not None:
        groups.append((agent, directives))
    return groups


def api_paths_that_named_groups_reopen(text: str) -> list[str]:
    """Named agents whose group allows `/` without re-disallowing `/api/`."""
    offenders = []
    for agent, directives in robots_groups(text):
        if agent == "*":
            continue
        if "allow: /" in directives and "disallow: /api/" not in directives:
            offenders.append(agent)
    return offenders


def test_no_named_crawler_group_reopens_the_api_paths():
    offenders = api_paths_that_named_groups_reopen(ROBOTS.read_text(encoding="utf-8"))
    assert not offenders, (
        "these robots.txt groups allow `/` for a named crawler without the `Disallow: /api/` the `*` "
        f"group applies, so the more specific group wins and they may crawl the API: {offenders}")


def test_the_robots_rule_notices_a_reopened_group():
    """Guard: the rule reads the real file, so its failure mode needs a fixture."""
    reopened = "User-agent: *\nAllow: /\nDisallow: /api/\n\nUser-agent: GPTBot\nAllow: /\n"
    assert api_paths_that_named_groups_reopen(reopened) == ["GPTBot"], api_paths_that_named_groups_reopen(reopened)
    closed = "User-agent: *\nDisallow: /api/\n\nUser-agent: GPTBot\nAllow: /\nDisallow: /api/\n"
    assert api_paths_that_named_groups_reopen(closed) == [], "a group that re-disallows is fine"
    assert api_paths_that_named_groups_reopen("User-agent: *\nDisallow: /api/\n") == [], (
        "the `*` group is not this rule's business — it is where the rule comes from")


def test_the_agent_card_lists_every_anonymously_readable_tool():
    """The card is what a client reads to decide whether it needs a token."""
    card = json.loads(CARD.read_text(encoding="utf-8"))
    public = set(card.get("authentication", {}).get("publicTools") or [])
    # The three read paths AGENTS.md §3.3 documents as anonymous, plus the protocol handshake.
    for name in ("misakanet_search", "misakanet_get_lesson", "misakanet_me_events",
                 "initialize", "tools/list"):
        assert name in public, f"{name} answers anonymously but the agent card omits it: {sorted(public)}"
    # …and the card must not promise a write tool for free: those still need a Bearer token.
    for name in ("misakanet_write_lesson", "misakanet_preflight"):
        assert name not in public, f"{name} needs a token and must not be advertised as public"


def test_api_md_names_the_arguments_the_tool_actually_has():
    """`API.md` is the reference an agent follows; a wrong argument name is an error on the first call."""
    text = API_MD.read_text(encoding="utf-8")
    row = next((line for line in text.splitlines() if "misakanet_get_lesson`" in line and "|" in line), None)
    assert row, "API.md no longer tabulates misakanet_get_lesson — this rule must move with it"
    assert "path_or_id" not in row, (
        "`path_or_id` is not an argument: the tool takes `id` or `path`, and the documented call fails")
    assert re.search(r"\bid\b", row) and re.search(r"\bpath\b", row), row
