#!/usr/bin/env python3
"""The intake form must ask for the sections a lesson needs.

Why this test exists (2026-11-02)
---------------------------------
`docs/maintainer/intake-flywheel.md` measured the queue: **172 open intakes, 128 with a `## Problem`
section, 37 with `## Root Cause`, 110 with a `## Fix`, and 0 with all three.** The lesson converter
requires Problem + Root Cause + Fix, so it could convert exactly **one** of them, the queue grew at
100-150 reports a week, and the receipts step that would have closed the loop had been a no-op since
it was written (it read a frontmatter field no lesson carries).

Every one of those is now fixed *except* the cause: a converter can partition prose, it cannot supply
the observation the reporter made. The only way the queue drains is if the form asks for the section
while the reporter still remembers it — and "asks" means the two descriptions an agent actually reads:
the hosted worker's and the stdio server's.

So this test pins the guidance on both surfaces, the same way `test_mcp_annotations.py` pins the
annotations: a description that stops asking is a queue that starts growing again, and nothing else in
this repository would notice.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

import sys  # noqa: E402

sys.path.insert(0, str(REPO))

from misakanet.server.tools import TOOLS  # noqa: E402

WORKER = REPO / "workers" / "register-proxy-sw.js"
GUIDE = REPO / "docs" / "mcp-intake-guide.md"
TOOL = "misakanet_submit_intake"


def local_tool() -> dict:
    return next(tool for tool in TOOLS if tool["name"] == TOOL)


def hosted_description() -> str:
    """The worker's `submit_intake` description, read out of its template literal."""
    text = WORKER.read_text(encoding="utf-8")
    match = re.search(r'name: "misakanet_submit_intake",\s*\n\s*description:\s*"((?:[^"\\]|\\.)*)"', text)
    if not match:
        # Some descriptions in this worker are template literals; fall back to the `[OPEN TRIAGE`
        # opener so the test fails on content, not on a quoting style change.
        match = re.search(r'description: "(\[OPEN TRIAGE / INTAKE\][\s\S]*?)(?<!\\)"', text)
    assert match, "the hosted submit_intake description could not be read — the extraction is stale"
    return match.group(1)


@pytest.mark.parametrize("surface", ["hosted", "stdio"])
def test_the_form_asks_for_a_root_cause_section(surface: str) -> None:
    description = hosted_description() if surface == "hosted" else local_tool()["description"]
    assert "## Root Cause" in description, (
        f"the {surface} description no longer asks for a `## Root Cause` section. That sentence is "
        "the only thing that makes an intake convertible: measured 2026-11-02, 0 of 172 open intakes "
        "carried one, and the batch converter could convert one report. See "
        "docs/maintainer/intake-flywheel.md §4.")


@pytest.mark.parametrize("surface", ["hosted", "stdio"])
def test_the_form_says_what_happens_without_one(surface: str) -> None:
    """Not just "please add a cause" — the consequence, so an agent can choose."""
    description = (hosted_description() if surface == "hosted" else local_tool()["description"]).lower()
    assert "cannot become a lesson" in description or "cannot be turned into a lesson" in description, (
        f"the {surface} description asks for the section but not why: an agent that does not know the "
        "consequence will keep submitting a bare paragraph")


def test_the_problem_parameter_carries_the_same_shape() -> None:
    """An agent may read the parameter description without ever reading the tool description."""
    prop = local_tool()["inputSchema"]["properties"]["problem"]["description"]
    assert "## Root Cause" in prop, (
        "the `problem` parameter description is where a caller looks when it is actually writing the "
        "text; it has to name the sections too")
    worker = WORKER.read_text(encoding="utf-8")
    assert "## Root Cause" in worker, "the hosted `problem` parameter no longer names the sections"


def test_the_guide_teaches_the_same_shape() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "## Root Cause" in guide and "## Fix" in guide, (
        "docs/mcp-intake-guide.md is what a human integrator reads; it has to show the same shape the "
        "tool descriptions ask for, or the two surfaces teach different behaviour")


def test_the_converter_accepts_the_shape_the_form_asks_for() -> None:
    """The contract is only worth asking for if the thing on the other end reads it.

    Builds a body exactly the way the worker does (`## Problem` + the agent's text) with the sections
    inside the text, and asserts `convert()` produces a lesson. If a future change to either side
    breaks this, the queue starts growing again silently.
    """
    import json  # noqa: PLC0415

    sys.path.insert(0, str(REPO / "scripts"))
    import intake_lesson_to_file as conv  # noqa: PLC0415

    body = (
        "**Kind:** missing_lesson\n**Source:** mcp\n\n"
        "## Problem\n"
        "The build fails on a clean checkout.\n\n"
        "## Root Cause\n"
        "The lockfile names a registry the runner cannot reach.\n\n"
        "## Fix\n"
        "Point `npm_config_registry` at the public registry before installing.\n"
    )
    canonical = set(json.loads((REPO / "data" / "domains.json").read_text(encoding="utf-8"))["canonical"])
    record, notes = conv.convert({"number": 1, "title": "[Intake] build fails on a clean checkout",
                                  "body": body}, canonical, {"domain": "devops"})
    assert record is not None, f"the converter refused the shape the form asks for: {notes}"
    assert "## Root Cause" in record["content"]
