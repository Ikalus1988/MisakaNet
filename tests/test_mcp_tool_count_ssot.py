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

Those three legs were still not the whole surface. A fourth kind of copy **retypes** the number in
prose instead of deriving it: `README.md`'s interface line, its `ja` / `zh-CN` translations, the
"which surface" note in the two `SKILL.md` copies, `docs/quickstart.md`'s install check, and the
`B` criterion in `docs/agents/mcp-only-client-verification.md`. None of them was read by any gate,
so while the endpoint served 8 they sat at 7 — and the skill's second claim ("those same 7 plus
three") with them. Unpinned prose rots, which is the point of this file, so those surfaces are read
here too: the extraction fails loudly when its phrase disappears, and a surface that asserts two
different numbers fails with both numbers and their lines named.

What is deliberately *not* read: occurrences that record a measurement rather than make a claim —
`CHANGELOG.md`, the dated handoffs under `docs/maintainer/`, the Claude Code / Hermes rows of
`docs/integrations/status.md` (what *those clients* reported at the time), the Glama status line in
`docs/mcp-quickstart.md` (a third party's surface, which `scripts/verify-glama-listing.py` owns),
and RFCs marked 历史文档. Rewriting those would not be a fix, it would be a fake measurement.

The `docs/mcp.md` row reader now refuses a *duplicated* surface label for the same reason. The table
really did carry two `| **local stdio** |` rows — the first with 11 tools, a stale second with 10 and
no `misakanet_me_events` — and because the reader returned the first match, every assertion here could
pass while a reader scrolling the table saw a contradiction.
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

# Surfaces whose prose *retypes* the hosted count instead of deriving it. Each entry is
# (path, pattern, where); the pattern must find at least one number (otherwise the gate is reading
# nothing) and every number it finds on that surface must be the same one. A surface can legitimately
# state the count twice (the skill says "8 tools" and then "those same 8"), so the rule is
# "one distinct number", not "one match".
HOSTED_COUNT_CLAIM = re.compile(r"(?:\*\*hosted\*\*\s+exposes|those same)\s+(\d+)\b")
HOSTED_COUNT_SURFACES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("README.md", re.compile(r"\[MCP server\]\(https://misakanet\.org/mcp\)\s*\((\d+)\s+tools?\)"),
     "the interface line in the lead block"),
    ("README.ja.md", re.compile(r"\[MCP サーバー\]\(https://misakanet\.org/mcp\)（(\d+)\s*ツール）"),
     "the interface line in the lead block"),
    # Added 2026-10-17 with the README rework: the zh-CN lead block now mirrors the English one, so the
    # count it retypes is pinned here rather than sitting in prose the gate cannot see.
    ("README.zh-CN.md", re.compile(r"\[MCP 服务器\]\(https://misakanet\.org/mcp\)（(\d+)\s*个工具）"),
     "the interface line in the lead block"),
    ("README.zh-CN.md", re.compile(r"Streamable HTTP，(\d+)\s*个工具"),
     "the service row of the three-layer table"),
    ("README.zh-CN.md", re.compile(r"\*\*(\d+)\s*个\s*`misakanet_\*`\s*工具"),
     "the self-check item 'you get N tools'"),
    ("README.zh-CN.md", re.compile(r"且\s*(\d+)\s*个工具"),
     "the evidence column of the self-check item"),
    ("SKILL.md", HOSTED_COUNT_CLAIM, "the surface note under Tools"),
    ("skills/misakanet/SKILL.md", HOSTED_COUNT_CLAIM, "the surface note under Tools"),
    ("docs/quickstart.md", re.compile(r"lists\s+`misakanet`\s+with\s+(\d+)\s+tools"),
     "the install check in Track A"),
    ("docs/agents/mcp-only-client-verification.md", re.compile(r"Does the client see\s+(\d+)\s+tools"),
     "the 'B' criterion row"),
)


def _mcp_doc_rows(text: str, label: str) -> list[str]:
    """Every `docs/mcp.md` surface-table row that carries `label`."""
    return [line for line in text.splitlines() if line.startswith("|") and label in line]


def _mcp_doc_row(label: str, root: Path = REPO) -> str:
    """The one `docs/mcp.md` surface-table row for one surface.

    A duplicated label is an error, not a first match. The table carried two
    `| **local stdio** — what this page installs |` rows — the correct one with 11 tools, and a
    stale second with 10 that omitted `misakanet_me_events` — and returning the first made the
    contradiction invisible to every assertion in this file: whichever row was stale, the gate read
    the other one and passed. A label that names two rows is a label a reader cannot resolve either.
    """
    rows = _mcp_doc_rows((root / "docs" / "mcp.md").read_text(encoding="utf-8"), label)
    if not rows:
        raise AssertionError(f"docs/mcp.md has no surface row containing {label!r}")
    if len(rows) > 1:
        raise AssertionError(
            f"docs/mcp.md has {len(rows)} surface rows containing {label!r} — a duplicated surface "
            f"label makes the pinned row ambiguous (returning the first match is how a stale second "
            f"row contradicts the pinned one unnoticed). Keep one row per surface:\n"
            + "\n".join(rows)
        )
    return rows[0]


def _retyped_hosted_count(text: str, pattern: re.Pattern[str], surface: str) -> int:
    """The hosted tool count a surface retypes in prose, or a failure that says why it cannot answer.

    Two rules, both learned from this defect:

    * the phrase has to be found — a pattern that stops matching would leave the surface unpinned
      again, and "a gate that quietly stops looking" is the failure class this file is about;
    * one surface may repeat the *same* number, but two *different* numbers mean a reader cannot
      tell which is the claim, so the gate names both numbers and their lines instead of picking one.
    """
    claims: dict[int, list[int]] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in pattern.finditer(line):
            claims.setdefault(int(match.group(1)), []).append(lineno)
    if not claims:
        raise ValueError(
            f"{surface} no longer contains the phrase this gate reads its hosted tool count from "
            f"({pattern.pattern!r}). Restore the count rather than dropping the gate: this surface "
            f"was unpinned once and sat at 7 while the endpoint served 8."
        )
    if len(claims) > 1:
        raise ValueError(
            f"{surface} asserts {len(claims)} different hosted tool counts: "
            + "; ".join(
                f"{n} (line {', '.join(map(str, lines))})" for n, lines in sorted(claims.items())
            )
            + " — a reader cannot tell which one is the claim, so neither can this gate."
        )
    return next(iter(claims))


def assert_hosted_count_surface(root: Path, relpath: str, pattern: re.Pattern[str], where: str) -> None:
    """A retyped hosted count must equal the set `AGENTS.md` §3.2 lists — the canonical one."""
    count = _retyped_hosted_count((root / relpath).read_text(encoding="utf-8"), pattern, relpath)
    canonical = len(documented_hosted_tools(root))
    if count != canonical:
        raise ValueError(
            f"{relpath} says the hosted MCP server has {count} tools ({where}) and the documented, "
            f"served set has {canonical}. This line retypes the count instead of deriving it, which "
            f"is why nothing noticed it sitting at 7 — update it, or stop quoting a second number."
        )


# ── the three copies ────────────────────────────────────────────────────────────────
def test_the_documented_and_registered_sets_are_identical():
    documented, registered = documented_hosted_tools(), registered_hosted_tools()
    assert documented == registered, {
        "documented only": sorted(documented - registered),
        "registered only": sorted(registered - documented),
    }
    assert len(documented) == 8, sorted(documented)


def test_the_heading_count_in_agents_matches_its_own_table():
    """`### 3.2 工具清单（8 个）` — a number a human retypes. The reader parses the table instead, and
    this makes the heading answerable to it."""
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    heading = re.search(r"(?m)^###\s+3\.2\s+工具清单（(\d+)\s*个）", text)
    assert heading, "the AGENTS.md §3.2 heading stopped naming a count — update this test with it"
    assert int(heading.group(1)) == len(documented_hosted_tools()), (
        f"the heading says {heading.group(1)} and the table lists {len(documented_hosted_tools())}"
    )


def test_the_docs_page_derives_the_same_set_from_the_stdio_list():
    """`docs/mcp.md` never lists the hosted names: it describes them as "the stdio set minus …".

    Since 2026-09-30 (D4=A, #2000) the hosted set *is* the stdio set minus the three local-only
    tools, so the row no longer needs a `**plus**` leg — the reader accepts either form, because the
    derivation it can express is exactly what the surfaces must agree on."""
    stdio = set(NAME_RE.findall(_mcp_doc_row("**local stdio**")))
    # 11: 10 on 2026-09-30 (`misakanet_me_events`, proxied so the skill's reuse-evidence step works
    # on either surface, D4=A / #2000), plus `misakanet_me_inbox` from #2494.
    assert len(stdio) == 11, sorted(stdio)

    hosted = _mcp_doc_row("**hosted**")
    derivation = hosted.split("**minus**")[1]
    derived = stdio - set(NAME_RE.findall(derivation.split("**plus**")[0]))
    if "**plus**" in derivation:
        derived |= set(NAME_RE.findall(derivation.split("**plus**")[1]))

    assert derived == documented_hosted_tools(), {
        "docs/mcp.md derivation only": sorted(derived - documented_hosted_tools()),
        "AGENTS.md table only": sorted(documented_hosted_tools() - derived),
    }


def test_the_reader_returns_the_count_the_worker_serves():
    assert canonical_mcp_tools() == len(registered_hosted_tools())


# ── the surfaces that retype the count ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "relpath,pattern,where", HOSTED_COUNT_SURFACES,
    ids=[f"{relpath}: {where}" for relpath, _pattern, where in HOSTED_COUNT_SURFACES],
)
def test_a_retyped_hosted_count_matches_the_canonical_one(relpath, pattern, where):
    """The sentences a reader meets *before* `docs/mcp.md`, pinned to the same number.

    `canonical_mcp_tools()` pins the count against the worker; nothing pinned the README or the
    skill, which is why both sat at 7 while the endpoint answered `tools/list` with 8.
    """
    assert_hosted_count_surface(REPO, relpath, pattern, where)


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
    """A repo-shaped root with real copies of the files the readers compare."""
    shutil.copytree(REPO / "workers", tmp_path / "workers",
                    ignore=shutil.ignore_patterns("node_modules", "*.test.mjs"))
    shutil.copy(REPO / "AGENTS.md", tmp_path / "AGENTS.md")
    shutil.copy(REPO / "README.md", tmp_path / "README.md")
    shutil.copy(REPO / "SKILL.md", tmp_path / "SKILL.md")
    (tmp_path / "docs").mkdir()
    shutil.copy(REPO / "docs" / "mcp.md", tmp_path / "docs" / "mcp.md")
    (tmp_path / "skills" / "misakanet").mkdir(parents=True)
    shutil.copy(REPO / "skills" / "misakanet" / "SKILL.md",
                tmp_path / "skills" / "misakanet" / "SKILL.md")
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
    """The §3.2 heading is prose: a tool name next to its `（N 个）` must not enter the set.

    The fixture has to *make* its mutation. The first version replaced the heading as it read when
    it was written (`（7 个）`) and, once the heading became `（8 个）`, the replace silently matched
    nothing — the test passed without testing anything, which is the same rot this file gates.
    """
    agents = fake_root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    heading = re.search(r"(?m)^###\s+3\.2\s+工具清单（\d+\s*个）", text)
    assert heading, "the §3.2 heading no longer names a count — this fixture mutates it"
    mutated = text[:heading.end()] + "——`misakanet_prose_only` 不算" + text[heading.end():]
    assert mutated != text
    agents.write_text(mutated, encoding="utf-8")
    assert "misakanet_prose_only" not in documented_hosted_tools(fake_root)


# ── the retyped surfaces can go red ─────────────────────────────────────────────────
def _retype_to_seven(path: Path, pattern: re.Pattern[str]) -> None:
    """Rewrite every claim `pattern` finds in `path` to the stale 7 this branch fixes."""
    text = path.read_text(encoding="utf-8")
    mutated = pattern.sub(lambda match: match.group(0).replace(match.group(1), "7"), text)
    assert mutated != text, f"{path.name} no longer carries the phrase this fixture mutates"
    path.write_text(mutated, encoding="utf-8")


def test_a_readme_left_at_seven_is_reported(fake_root):
    """Red fixture for the README rule — the README really did say 7 while the endpoint served 8."""
    _retype_to_seven(fake_root / "README.md", HOSTED_COUNT_SURFACES[0][1])
    with pytest.raises(ValueError) as excinfo:
        assert_hosted_count_surface(fake_root, *HOSTED_COUNT_SURFACES[0])
    message = str(excinfo.value)
    assert "README.md" in message and "7" in message and "8" in message, message


@pytest.mark.parametrize("relpath", ("SKILL.md", "skills/misakanet/SKILL.md"))
def test_a_skill_left_at_seven_is_reported(fake_root, relpath):
    """Both `SKILL.md` copies taught the stale number, so both are pinned and both can go red."""
    _retype_to_seven(fake_root / relpath, HOSTED_COUNT_CLAIM)
    with pytest.raises(ValueError) as excinfo:
        assert_hosted_count_surface(
            fake_root, relpath, HOSTED_COUNT_CLAIM, "the surface note under Tools")
    message = str(excinfo.value)
    assert relpath in message and "7" in message and "8" in message, message


def test_a_surface_asserting_two_hosted_counts_is_rejected():
    """Two numbers, both named with their lines — the reader must not be left to pick one."""
    text = (
        "> * **hosted** exposes 8 tools, `misakanet_me_events` among them;\n"
        "> * a **local stdio** install exposes those same 7 **plus three**;\n"
    )
    with pytest.raises(ValueError) as excinfo:
        _retyped_hosted_count(text, HOSTED_COUNT_CLAIM, "SKILL.md")
    message = str(excinfo.value)
    assert "2 different hosted tool counts" in message, message
    assert "8 (line 1)" in message and "7 (line 2)" in message, message


def test_the_same_number_twice_is_one_claim_not_a_contradiction():
    """Positive control for the rule above: repetition is how the skill is actually written."""
    text = (
        "> * **hosted** exposes 8 tools, `misakanet_me_events` among them;\n"
        "> * a **local stdio** install exposes those same 8 **plus three**;\n"
    )
    assert _retyped_hosted_count(text, HOSTED_COUNT_CLAIM, "SKILL.md") == 8


def test_a_hosted_count_phrase_that_disappeared_is_an_error_not_a_skip():
    """A reworded surface fails loudly rather than leaving the gate asserting nothing."""
    with pytest.raises(ValueError) as excinfo:
        _retyped_hosted_count("Agent-native interfaces: the MCP server, WebMCP\n",
                              HOSTED_COUNT_SURFACES[0][1], "README.md")
    assert "README.md" in str(excinfo.value)


def test_a_duplicated_surface_row_is_rejected(fake_root):
    """Red fixture for the duplicate-label rule, on the row the table actually duplicated.

    `docs/mcp.md` carried `| **local stdio** |` twice: the correct 11-tool row, then a stale 10-tool
    row without `misakanet_me_events`. The old reader returned the first match, so the stale row
    could contradict the pinned one with every assertion in this file still green.
    """
    doc = fake_root / "docs" / "mcp.md"
    row = _mcp_doc_row("**local stdio**", fake_root)
    doc.write_text(doc.read_text(encoding="utf-8").replace(row, row + "\n" + row, 1),
                   encoding="utf-8")
    assert len(_mcp_doc_rows(doc.read_text(encoding="utf-8"), "**local stdio**")) == 2
    with pytest.raises(AssertionError, match="2 surface rows"):
        _mcp_doc_row("**local stdio**", fake_root)

