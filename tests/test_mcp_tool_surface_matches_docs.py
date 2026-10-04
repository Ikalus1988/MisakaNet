#!/usr/bin/env python3
"""The number of tools the hosted worker serves is a public claim; this pins it to our own words.

Measured 2026-10-04: `https://misakanet.org/mcp` answers `tools/list` with 7 tools while the Glama
registry listing advertised 12, and five of the extras cannot work — `misakanet_cli` was never an
MCP tool at all (it is a Python module, `scripts/misakanet_cli.py`), `misakanet_get_my_events` was
renamed to `misakanet_me_events` in c31640c67 ("disambiguate tool descriptions per Glama TDQS
review") and the registry kept the old name, and `misakanet_memory_context` /
`misakanet_submit_usage` / `misakanet_usage_status` exist only in the Python stdio server
(`misakanet/server/tools.py`, 10 tools), never in the worker. So a user installing MisakaNet
through Glama saw five tools that do not work.

The detector for the registry half of that already existed and had **no caller**:
`scripts/verify-glama-listing.py` exits 1 and prints the stale list, and nothing in `.github/` or
`tests/` invoked it. It needs the network, so it cannot sit in the merge path;
`.github/workflows/registry-drift-watch.yml` runs it on a schedule instead.

This file is the half that can block, and it is deliberately network-free: the count of tools the
worker actually exposes must equal the count our documentation asserts. Both numbers are **read**,
never hardcoded, so adding an eighth tool together with the sentence describing it keeps this green
while adding the tool alone turns it red and names the sentence that was left behind.

This is a different invariant from the two that already exist, not a fourth copy of one of them:
`tests/test_install_smoke.py` holds a hardcoded floor (`scripts/install_smoke.py`'s
`SETUP_MIN_ENDPOINT_TOOLS = 7`) measured against the *live* endpoint, and `install-smoke.yml` runs
it on a schedule; `docs/mcp.md`'s stdio row is checked tool-by-tool against the Python server. A
floor passes when a tool is added and nothing else has to move, and neither of those can see the
worker and this repository's own documentation disagreeing inside a single commit.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
STATUS_DOC = REPO / "docs" / "integrations" / "status.md"
DETECTOR = REPO / "scripts" / "verify-glama-listing.py"

# Path spellings relative to the repo root, because a gate message is read in a CI log where a
# bare filename is not clickable and cannot be opened.
WORKER_REL = "workers/register-proxy-sw.js"
DOC_REL = "docs/integrations/status.md"

# The claim this gate reads out of the documentation, tolerant of the markdown around it: the
# backticks on `tools/list`, and `**7**` as well as `7`. Anchored on `tools/list` because the same
# document mentions "7 tools" in three other table rows about *other* clients (the Claude Code,
# Hermes and Codewhale field reports) — matching a bare "N tools" would read whichever row it hit
# first and compare the wrong number.
DOC_CLAIM = re.compile(r"tools/list`?\s*with\s*\**(\d+)\**\s+tools?\b")


def _load_detector() -> ModuleType:
    """`scripts/verify-glama-listing.py` as a module.

    The filename is not importable the ordinary way (hyphens), and the extraction it owns is the
    authoritative one: `re.findall(r'name:\\s*"misakanet_(\\w+)"', text)` over the worker. A second
    copy of that regex in a test file is how two parsers start disagreeing about what the worker
    serves. Its `main()` is behind `if __name__ == "__main__"`, so loading it has no side effect.
    """
    spec = importlib.util.spec_from_file_location("verify_glama_listing", DETECTOR)
    assert spec and spec.loader, f"{DETECTOR} could not be loaded as a module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker_tool_names() -> list[str]:
    """The tool names the hosted worker exposes, fully qualified.

    Taken from the detector's own extraction so the two can never disagree about what the worker
    serves; it returns the suffix after `misakanet_`, which is what makes the prefix explicit here.
    """
    return [f"misakanet_{suffix}" for suffix in _load_detector().get_local_tools()]


def documented_tool_count(text: str) -> int:
    """The number of tools the documentation asserts the live endpoint serves.

    Fails loudly rather than skipping when the assertion cannot be found, or when the document
    asserts two different numbers. A gate that quietly stops looking is the exact failure class
    this repository keeps getting bitten by — a check that cannot answer must not answer "fine".
    """
    claims: dict[int, list[int]] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in DOC_CLAIM.finditer(line):
            claims.setdefault(int(match.group(1)), []).append(lineno)

    assert claims, (
        f"no tool-count assertion found in {DOC_REL}. This gate reads the sentence that says the "
        f"endpoint's `tools/list` count, and it has to keep reading it — the shape it expects is "
        f"`answers `tools/list` with N tools`. If the sentence was reworded, restore the count "
        f"here rather than deleting the gate: a claim that is not checked is a claim that rots."
    )
    assert len(claims) == 1, (
        f"{DOC_REL} asserts {len(claims)} different tool counts: "
        + "; ".join(
            f"{n} (line {', '.join(map(str, lines))})" for n, lines in sorted(claims.items())
        )
        + ". A reader cannot tell which one is the claim, so neither can this gate — keep one."
    )
    return next(iter(claims))


def surface_drift(worker_names: list[str], documented: int) -> str:
    """Why the served surface and the documented claim disagree, or `""` when they agree.

    Both numbers, and which of the two is out of date, because a gate message that only says
    "mismatch" costs the reader the whole investigation.
    """
    served = len(worker_names)
    if served == documented:
        return ""
    direction = (
        "the document is behind the worker" if documented < served
        else "the document claims more tools than the worker serves"
    )
    return (
        f"the hosted worker serves {served} tools but {DOC_REL} asserts {documented} — "
        f"{direction}. The number is written in `{DOC_REL}`; the served set is `{WORKER_REL}` "
        f"({', '.join(worker_names)}). If the new tool is real, it belongs in `{WORKER_REL}` and "
        f"the sentence needs rewriting; if it was removed, the sentence is simply wrong. Letting "
        f"the two disagree silently is how five unusable tools reached the Glama listing."
    )


# ── the invariant ─────────────────────────────────────────────────────────────────────────────────

def test_the_tools_the_worker_serves_are_the_tools_the_docs_say_it_serves():
    drift = surface_drift(
        worker_tool_names(),
        documented_tool_count(STATUS_DOC.read_text(encoding="utf-8")),
    )
    assert not drift, drift


def test_the_worker_exposes_tools_the_extraction_can_see():
    """Guard the guard: the count comes from a regex over the worker source.

    If the tool definitions are ever restructured so the pattern stops matching, the extraction
    returns an empty list and the comparison above becomes 0 against whatever the document says.
    That fails today only by luck; this makes the empty case say so.
    """
    names = worker_tool_names()
    assert names, (
        f"no `misakanet_` tool names were found in {WORKER_REL}. The MCP tool definitions moved, "
        f"so the extraction in scripts/verify-glama-listing.py no longer sees them — update the "
        f"pattern there rather than in one place, or every count derived from it is silently zero."
    )
    assert all(name.startswith("misakanet_") for name in names), names
    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"{WORKER_REL} declares these tool names more than once: {duplicates}"


# ── the rules can go red ──────────────────────────────────────────────────────────────────────────

_FIXTURE_TOOLS = [
    "misakanet_register",
    "misakanet_search",
    "misakanet_get_lesson",
    "misakanet_submit_intake",
    "misakanet_write_lesson",
    "misakanet_preflight",
    "misakanet_me_events",
]


def test_a_wrong_number_in_the_document_is_reported_as_drift():
    """The positive control, on the real comparator.

    The numbers are the measured ones: 7 served, 12 advertised on Glama. Without this, "no drift"
    above could just mean a comparison that never fires.
    """
    assert not surface_drift(_FIXTURE_TOOLS, 7), "the equal case must not report drift"
    for wrong in (6, 9, 12):
        report = surface_drift(_FIXTURE_TOOLS, wrong)
        assert report, f"a document asserting {wrong} against 7 served tools must be reported"
        assert str(wrong) in report and "7" in report, (
            f"the report must name both numbers, or the reader has to re-derive the gate: {report}"
        )
        assert DOC_REL in report, f"the report must name the file to edit: {report}"


def test_a_document_without_the_claim_fails_loudly_instead_of_skipping():
    """No assertion found is a failure, never a pass."""
    with pytest.raises(AssertionError, match="no tool-count assertion found"):
        documented_tool_count("| Any other MCP client | speaks Streamable HTTP | | |\n")


def test_a_document_claiming_two_different_counts_is_rejected():
    with pytest.raises(AssertionError, match="different tool counts"):
        documented_tool_count(
            "| a | answers `tools/list` with 7 tools |\n"
            "| b | answers `tools/list` with 9 tools |\n"
        )


def test_the_claim_is_read_through_surrounding_markdown():
    """Tolerant of the markdown, not of the sentence: the other rows' "7 tools" must not be read."""
    assert documented_tool_count(
        "| Any other MCP client | `https://misakanet.org/mcp` speaks Streamable HTTP and answers "
        "`tools/list` with 7 tools; reads are anonymous |  |\n"
    ) == 7
    assert documented_tool_count("answers tools/list with **8** tools\n") == 8
    # The same number twice is one claim, not a contradiction.
    assert documented_tool_count(
        "answers `tools/list` with 7 tools\nand elsewhere, `tools/list` with 7 tools\n"
    ) == 7
    # Three other rows in the real document mention 7 tools without making the claim.
    assert not DOC_CLAIM.search(
        "| **Claude Code** | verified (installer + field report: 7 tools, called) |\n"
    )
