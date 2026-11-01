#!/usr/bin/env python3
"""The three retrieval tools must say which one to call instead of the others.

Why this file exists (2026-11-01)
---------------------------------
Glama's tool-description audit scores a **Disambiguation** dimension, and it has been 3/5 on this
server while every other dimension sat at 4 or 5. Its note named the cause: `misakanet_search`,
`misakanet_memory_context` and `misakanet_preflight` all take a free-text string about what you are
doing and all return lesson-shaped material, so an agent reading the tool list has three plausible
choices and no rule. The descriptions each mentioned a sibling somewhere, but none of them stated
the decision.

That is a user-facing defect before it is a score: picking `search` at the start of a task, or
`memory_context` when you already have an error, returns something — it just returns the wrong kind
of thing, quietly.

So each of the three carries, in the same words on both MCP surfaces:

* the **decision rule** (what you have → which tool), and
* a **"Not for:"** clause naming the sibling it must not be used as.

The rule is deliberately one sentence: a longer one would cost the Conciseness dimension that is
currently 5/5, which is trading one point for another.

Both surfaces are checked because a client sees exactly one of them: the hosted worker serves
`search` and `preflight` (not `memory_context`), and the stdio server serves all three.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.server.tools import TOOLS  # noqa: E402

WORKER = REPO / "workers" / "register-proxy-sw.js"
LOCAL = {tool["name"]: tool["description"] for tool in TOOLS}
PAIR = ("misakanet_search", "misakanet_preflight", "misakanet_memory_context")
#: The one sentence every surface must carry, verbatim. Changing it is a copy decision; changing it
#: in *one* place is a bug, which is what this constant exists to catch.
RULE = ("Choosing among the three retrieval tools: no error yet and a task about to start → "
        "memory_context; an actual error or keyword in hand → search; something risky about to run "
        "and no error yet → preflight.")


def worker_descriptions() -> dict[str, str]:
    """Tool descriptions as the worker serves them (template literals, so parsed loosely)."""
    text = WORKER.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for name in PAIR:
        match = re.search(rf'name: "{name}",\s*\n\s*description: "(.*?)(?<!\\)`', text, re.S)
        if match:
            out[name] = match.group(1)
    return out


def test_the_local_pair_states_the_rule_verbatim() -> None:
    missing = [name for name in PAIR if RULE not in LOCAL[name]]
    assert not missing, (
        f"these tools lost the decision rule: {missing}. Three retrieval tools that do not say which "
        "one to call are three guesses — that is the whole of the Disambiguation score.")


def test_each_tool_says_what_it_is_not_for() -> None:
    problems = []
    for name in PAIR:
        description = LOCAL[name]
        if "Not for:" not in description:
            problems.append(f"{name}: no 'Not for:' clause")
            continue
        clause = description.split("Not for:", 1)[1].split("\n", 1)[0]
        if not any(sibling.split("_", 1)[1] in clause for sibling in PAIR if sibling != name):
            problems.append(f"{name}: the 'Not for:' clause names no sibling — {clause[:80]!r}")
    assert not problems, (
        "'Not for' has to point at the other tool by name; a prohibition that does not say what to "
        "use instead leaves the reader where they started:\n  " + "\n  ".join(problems))


def test_the_hosted_surface_carries_the_same_decision() -> None:
    hosted = worker_descriptions()
    assert set(hosted) == {"misakanet_search", "misakanet_preflight"}, (
        f"parsed {sorted(hosted)} from the worker — the extraction stopped reading the file it guards")
    for name, description in hosted.items():
        assert "Choosing among the retrieval tools" in description, (
            f"{name} on the hosted surface has no decision rule; a client that only talks to "
            "https://misakanet.org/mcp never sees the stdio text")
        assert "misakanet_" in description.split("Choosing among", 1)[1][:400], (
            f"{name}: the hosted rule names no sibling tool")


def test_the_hosted_rule_names_the_tool_it_cannot_offer() -> None:
    """`memory_context` is stdio-only; the hosted rule has to say so rather than point at nothing."""
    hosted = worker_descriptions()
    for name, description in hosted.items():
        if "memory_context" in description:
            assert "stdio" in description, (
                f"{name} points at misakanet_memory_context without saying it is stdio-only — a "
                "hosted client would try to call a tool that is not in its list")


def test_the_rule_stays_one_sentence() -> None:
    """Conciseness is 5/5; the fix for Disambiguation must not buy it from that dimension."""
    for name in PAIR:
        rule_block = LOCAL[name].split("Choosing among", 1)[1].split("Not for:", 1)[0]
        assert rule_block.count(".") <= 2, (
            f"{name}: the rule grew to {rule_block.count('.')} sentences — it is one decision, keep "
            "it as one; description length is scored too")
