#!/usr/bin/env python3
"""The hosted MCP tool count must be measured against something other than itself (#1822).

`update-badges.yml` computed the "MCP tools" badge with
``grep -cE 'name: "misakanet_' workers/register-proxy-sw.js``. The expected value and the measured
value read the same file, so the number could not be wrong — it could only prove the file had not been
deleted. Two other counts in that same job had already been routed through
``scripts/sync_lesson_count``'s ``canonical_*`` readers for exactly this reason (domains in #1687,
nodes in #1683); the tool count was the one left counting itself.

There are three copies of this list: the `AGENTS.md` §3.2 table (what an agent reads), `docs/mcp.md`'s
hosted row (the same set described by derivation from the stdio list), and the worker (what answers
`tools/list`). Nothing compared them. `canonical_mcp_tools()` now takes its expectation from the first
and its measurement from the third, and **raises** on disagreement; these tests pin all three legs.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.sync_lesson_count import (  # noqa: E402
    canonical_mcp_tools,
    documented_hosted_tools,
    registered_hosted_tools,
)

NAME_RE = re.compile(r"misakanet_[a-z_]+")
WORKFLOW = REPO / ".github" / "workflows" / "update-badges.yml"


def _mcp_doc_row(label: str) -> str:
    """The `docs/mcp.md` surface-table row for one surface."""
    for line in (REPO / "docs" / "mcp.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and label in line:
            return line
    raise AssertionError(f"docs/mcp.md has no surface row containing {label!r}")


# ── the three copies ────────────────────────────────────────────────────────────────
def test_the_documented_and_registered_sets_are_identical():
    documented, registered = documented_hosted_tools(), registered_hosted_tools()
    assert documented == registered, {
        "documented only": sorted(documented - registered),
        "registered only": sorted(registered - documented),
    }
    assert len(documented) == 7, sorted(documented)


def test_the_heading_count_in_agents_matches_its_own_table():
    """`### 3.2 工具清单（7 个）` — a number a human retypes. The reader parses the table instead, and
    this makes the heading answerable to it."""
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    heading = re.search(r"(?m)^###\s+3\.2\s+工具清单（(\d+)\s*个）", text)
    assert heading, "the AGENTS.md §3.2 heading stopped naming a count — update this test with it"
    assert int(heading.group(1)) == len(documented_hosted_tools()), (
        f"the heading says {heading.group(1)} and the table lists {len(documented_hosted_tools())}"
    )


def test_the_docs_page_derives_the_same_set_from_the_stdio_list():
    """`docs/mcp.md` never lists the hosted names: it describes them as "the stdio set minus … plus
    `misakanet_me_events`". Recomputing that derivation is the only way the third copy can be checked."""
    stdio = set(NAME_RE.findall(_mcp_doc_row("**local stdio**")))
    assert len(stdio) == 9, sorted(stdio)

    hosted = _mcp_doc_row("**hosted**")
    derivation = hosted.split("**minus**")[1]
    minus, plus = derivation.split("**plus**")[0], derivation.split("**plus**")[1]
    derived = (stdio - set(NAME_RE.findall(minus))) | set(NAME_RE.findall(plus))

    assert derived == documented_hosted_tools(), {
        "docs/mcp.md derivation only": sorted(derived - documented_hosted_tools()),
        "AGENTS.md table only": sorted(documented_hosted_tools() - derived),
    }


def test_the_reader_returns_the_count_the_worker_serves():
    assert canonical_mcp_tools() == len(registered_hosted_tools())


# ── the badge job must stop measuring itself ────────────────────────────────────────
def _run_commands(path: Path) -> list[str]:
    """Every `run:` block in a workflow, with shell comments stripped.

    Comments have to go: the step now *quotes* the old grep to explain why it was wrong, and the first
    version of this test matched that quotation and failed on its own explanation.
    """
    import yaml

    blocks = []
    for job in (yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs") or {}).values():
        for step in job.get("steps") or []:
            run = step.get("run")
            if not run:
                continue
            blocks.append("\n".join(
                line for line in run.splitlines() if not line.lstrip().startswith("#")
            ))
    return blocks


def test_the_badge_job_no_longer_greps_the_file_it_badges():
    commands = "\n".join(_run_commands(WORKFLOW))
    assert "canonical_mcp_tools" in commands, "the badge job is not using the cross-checking reader"
    assert not re.search(r"grep -cE? '[^']*name: \"misakanet_", commands), (
        "the self-referential grep is back: an expectation read from the file it measures cannot fail"
    )


def test_the_badge_step_can_go_red(monkeypatch, capsys):
    """The whole point: a documented tool that is not registered must fail the job, not print a
    number. Simulated through the reader rather than by editing the worker."""
    def fake_documented(root=REPO):
        return frozenset({"misakanet_search", "misakanet_imaginary"})

    def fake_registered(root=REPO):
        return frozenset({"misakanet_search"})

    monkeypatch.setattr("scripts.sync_lesson_count.documented_hosted_tools", fake_documented)
    monkeypatch.setattr("scripts.sync_lesson_count.registered_hosted_tools", fake_registered)
    with pytest.raises(ValueError) as excinfo:
        canonical_mcp_tools()
    message = str(excinfo.value)
    assert "misakanet_imaginary" in message and "#1822" in message, message


# ── the reader's own failure modes ─────────────────────────────────────────────────
@pytest.fixture()
def fake_root(tmp_path: Path) -> Path:
    """A repo-shaped root with real copies of the two files the reader compares."""
    shutil.copytree(REPO / "workers", tmp_path / "workers",
                    ignore=shutil.ignore_patterns("node_modules", "*.test.mjs"))
    shutil.copy(REPO / "AGENTS.md", tmp_path / "AGENTS.md")
    return tmp_path


def test_an_undocumented_registration_is_reported(fake_root):
    worker = fake_root / "workers" / "register-proxy-sw.js"
    worker.write_text(worker.read_text(encoding="utf-8").replace(
        'name: "misakanet_me_events"', 'name: "misakanet_secret_tool"', 1), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        canonical_mcp_tools(fake_root)
    assert "misakanet_secret_tool" in str(excinfo.value)


def test_an_unregistered_documentation_row_is_reported(fake_root):
    agents = fake_root / "AGENTS.md"
    agents.write_text(agents.read_text(encoding="utf-8").replace(
        "| `misakanet_preflight` |",
        "| `misakanet_promised_only` | nope | nope |\n| `misakanet_preflight` |", 1), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        canonical_mcp_tools(fake_root)
    assert "misakanet_promised_only" in str(excinfo.value)


def test_a_missing_table_is_an_error_not_an_empty_set(fake_root):
    """A reader that silently finds nothing is how a gate stops existing — the failure this whole
    issue is about. Both legs raise instead."""
    (fake_root / "AGENTS.md").write_text("# no tool table here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="§3.2"):
        documented_hosted_tools(fake_root)


def test_the_reader_is_not_fooled_by_a_number_in_the_prose(fake_root):
    """The row's `（7 个）` is quoted in several places; only table rows may contribute names."""
    agents = fake_root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    agents.write_text(text.replace("### 3.2 工具清单（7 个）",
                                   "### 3.2 工具清单（7 个）——`misakanet_prose_only` 不算", 1),
                      encoding="utf-8")
    assert "misakanet_prose_only" not in documented_hosted_tools(fake_root)
