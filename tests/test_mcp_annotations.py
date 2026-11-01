#!/usr/bin/env python3
"""Every stdio tool must say what it does to the world, and say the same thing as the worker.

Why this file exists (2026-11-01)
---------------------------------
`workers/register-proxy-sw.js` has carried the four MCP annotations since #3634.
`misakanet/server/tools.py` — the surface `pip install misakanet` serves — had none of them, on
any of its eleven tools. #4251 measured that gap from the outside (Glama's TDQS scores "Behavioral
Transparency" on exactly this: side effects, safety, destructiveness) and no gate here could see it,
because "a tool exists" and "a tool says whether it is destructive" are different claims.

A client uses these hints to decide what it may call without asking a human. `readOnlyHint` on a
tool that writes is not a cosmetic omission: it is the difference between an agent retrying freely
and an agent knowing it is about to change state.

Two invariants, and the second is the one that matters across surfaces:

* every tool declares all four hints, as booleans — a missing key is not "unknown", it is "whatever
  the client defaults to";
* for the eight names both surfaces serve, the two surfaces agree. A client that talks to the local
  stdio server and the hosted endpoint must not be told two different things about the same tool.

The worker half is parsed out of `workers/register-proxy-sw.js` rather than restated here: the
annotations live in that file as a JS object literal, and a second copy in this file is exactly how
two surfaces start disagreeing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.server.tools import ANNOTATIONS, TOOLS  # noqa: E402

WORKER = REPO / "workers" / "register-proxy-sw.js"
HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def worker_annotations() -> dict[str, dict[str, bool]]:
    """`{tool name: hints}` parsed from the worker's tool objects.

    Deliberately a parse and not an import: the worker is a single file Cloudflare runs, and the
    question here is what that file *says*, not what a Python re-implementation of it thinks.
    """
    text = WORKER.read_text(encoding="utf-8")
    found: dict[str, dict[str, bool]] = {}
    for match in re.finditer(r'\{\s*\n\s*name: "(misakanet_[a-z_]+)",', text):
        name = match.group(1)
        # The annotations object of *this* tool: the next `annotations: { ... }` after its name,
        # bounded by the end of the hints it declares.
        tail = text[match.start():]
        block = re.search(r"annotations: \{(.*?)\}", tail, re.S)
        if not block:
            continue
        hints = dict(re.findall(r"(\w+Hint):\s*(true|false)", block.group(1)))
        found[name] = {k: v == "true" for k, v in hints.items()}
    return found


def test_every_tool_declares_all_four_hints() -> None:
    problems = []
    for tool in TOOLS:
        annotations = tool.get("annotations")
        if not isinstance(annotations, dict):
            problems.append(f"{tool['name']}: no annotations at all")
            continue
        missing = [hint for hint in HINTS if hint not in annotations]
        if missing:
            problems.append(f"{tool['name']}: missing {missing}")
        wrong_type = [hint for hint, value in annotations.items() if not isinstance(value, bool)]
        if wrong_type:
            problems.append(f"{tool['name']}: non-boolean {wrong_type}")
    assert not problems, (
        "the stdio tools do not all declare their behaviour hints — a client reads these to decide "
        "what it may call without asking a human:\n  " + "\n  ".join(problems)
    )


def test_the_table_covers_every_tool_and_nothing_else() -> None:
    """A hint table that drifts from the tool list is a table about a different server."""
    declared = {tool["name"] for tool in TOOLS}
    assert set(ANNOTATIONS) == declared, (
        "ANNOTATIONS and TOOLS disagree: "
        f"extra={sorted(set(ANNOTATIONS) - declared)} missing={sorted(declared - set(ANNOTATIONS))}"
    )


def test_the_two_surfaces_describe_shared_tools_the_same_way() -> None:
    worker = worker_annotations()
    assert len(worker) >= 8, (
        f"parsed only {len(worker)} worker tools — the extraction stopped reading the file it guards"
    )
    shared = sorted(set(worker) & {tool["name"] for tool in TOOLS})
    assert len(shared) >= 8, f"expected the eight shared names, found {shared}"
    problems = []
    for name in shared:
        local = ANNOTATIONS[name]
        remote = worker[name]
        differing = {hint: (local.get(hint), remote.get(hint)) for hint in HINTS
                     if local.get(hint) != remote.get(hint)}
        if differing:
            problems.append(f"{name}: stdio vs worker disagree on {differing}")
    assert not problems, (
        "the two surfaces tell a client different things about the same tool "
        "(stdio, worker):\n  " + "\n  ".join(problems)
    )


def test_a_read_only_hint_is_not_used_to_describe_a_writing_tool() -> None:
    """The one mistake these hints exist to prevent, checked against the tool's own name.

    Crude on purpose: `write_`, `submit_`, `register` are the writing verbs in this surface, and a
    `readOnlyHint: true` on any of them is a contradiction no review should have to catch twice.
    """
    writing = [tool["name"] for tool in TOOLS
               if re.search(r"_(write|submit|register)", tool["name"])]
    assert writing, "the writing-verb extraction matched nothing — this check would pass vacuously"
    liars = [name for name in writing if ANNOTATIONS[name]["readOnlyHint"]]
    assert not liars, f"these tools write but claim to be read-only: {liars}"


def test_the_annotations_are_served_not_merely_declared() -> None:
    """The table has to reach the objects a client receives, through the filter that serves them."""
    from misakanet.server.tools import _filtered_tools

    for tool in _filtered_tools():
        assert "annotations" in tool, (
            f"{tool['name']} lost its annotations on the way to the wire — the table is declared "
            "but the served object is what the client reads"
        )
