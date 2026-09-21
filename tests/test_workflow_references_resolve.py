#!/usr/bin/env python3
"""A document that claims an automation exists must name one that exists (#1984, extended to prose).

Deleting `sync-data.yml`, `ci-self-heal.yml` and `manual-audit.yml` left live claims behind that no
gate could see, because the gates written for that change read `.github/workflows/` and `docs/CI.md`
— not the documents that *describe* the automation:

* `ARCHITECTURE.md` listed `sync-data.yml` in its automation table ("Syncs lessons.json and feed
  data") and promised "**Self-healing** — `ci-self-heal.yml` can auto-fix known CI failures".
* `tests/test_workflow_yaml_validity.py` explained its own reason for existing by pointing at
  `ci-self-heal.yml`'s runs as a current fact, and `tests/test_classify_failure_action.py` said the
  maintainer "gets notified" through that workflow.

Three things this rule deliberately does NOT do, each because a measurement said so:

* **It is scoped** to the documents whose job is to enumerate this repository's automation. A
  tree-wide scan of every `*.yml` token is mostly false positives: the test suite is full of synthetic
  fixtures (`a.yml`, `lib.yml`, `user.yml`) and the docs are full of examples. Measured across the
  whole repository: 36 unresolved tokens, of which 2 were real.
* **It skips fenced code blocks.** Examples live in fences; `docs/agents/repo-operations.md` shows
  `.github/workflows/x.yml` as the *shape* of a command, and that is correct.
* **It excuses a few phrasings**, on the mention's line or an adjacent one: "this was removed" and
  "this is an example". Without them the rule would flag the sentences that document the deletions —
  and a rule that has to be weakened the first time it fires is not a rule (#1963).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# The documents whose job is to describe this repository's own automation.
ENUMERATING_DOCS = (
    "ARCHITECTURE.md",
    "AGENTS.md",
    "README.md",
    "README.zh-CN.md",
    "README.ja.md",
    "docs/CI.md",
    "docs/maintenance.md",
    "docs/agents/repo-operations.md",
)

# Said on the mention's line or an adjacent one, these make the sentence true either way.
HATCHES = ("删除", "已停", "不再", "曾是", "示例", "例如", "比如", "已被", "取代",
           "example", "deleted", "removed", "no longer", "New CI gate")

# `.github/workflows/name.yml` / `.github/actions/name`, or a bare `name.yml` inside backticks.
QUALIFIED = re.compile(r"\.github/(?:workflows|actions)/([A-Za-z0-9_.-]+?)(?=[\s`)\]>,。，、;:]|$)")
BARE = re.compile(r"`([A-Za-z0-9_.-]+\.ya?ml)`")


def automation_names(repo: Path = REPO) -> set[str]:
    """Every workflow and action basename that actually exists."""
    names = {p.name for p in (repo / ".github" / "workflows").glob("*.y*ml")}
    names |= {p.name for p in (repo / ".github" / "actions").rglob("*.y*ml")}
    return names


def lines_without_fences(text: str) -> list[tuple[int, str]]:
    """(1-based line number, line) with fenced code blocks removed."""
    kept, inside = [], False
    for index, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            kept.append((index, line))
    return kept


def unresolved_claims(text: str, names: set[str]) -> list[str]:
    """`line N: name` for every claim in a document that nothing under `.github/` answers to."""
    lines = lines_without_fences(text)
    problems = []
    for position, (number, line) in enumerate(lines):
        candidates = set(QUALIFIED.findall(line)) | set(BARE.findall(line))
        for name in sorted(candidates):
            if name in names or not re.search(r"\.ya?ml$|^[a-z0-9-]+$", name):
                continue
            # A dotted stem is a derived artifact, not a workflow: `cordis.patch.yml` is a local
            # patch file that `docs/maintenance.md` names on purpose, and workflow filenames in this
            # repository never contain a second dot.
            if Path(name).stem.count("."):
                continue
            neighbourhood = "\n".join(
                text_line for _, text_line in lines[max(0, position - 1):position + 2])
            if any(hatch in neighbourhood for hatch in HATCHES):
                continue
            problems.append(f"line {number}: {name}")
    return problems


def test_the_documents_that_enumerate_automation_only_name_automation_that_exists():
    names = automation_names()
    problems = {}
    for doc in ENUMERATING_DOCS:
        path = REPO / doc
        if not path.exists():
            continue
        found = unresolved_claims(path.read_text(encoding="utf-8"), names)
        if found:
            problems[doc] = found
    assert not problems, (
        "these documents promise automation that does not exist — a deleted workflow described as a "
        f"live one is worse than no description: {problems}")


# ── guard the guard ─────────────────────────────────────────────────────────────────────────────

def test_a_deleted_workflow_described_as_a_live_fact_is_caught():
    """The real leftover: `ARCHITECTURE.md` promised self-healing via a file that had been deleted."""
    names = automation_names()
    assert "ci-self-heal.yml" not in names, "the fixture assumes the file is gone"
    assert unresolved_claims("- **Self-healing** — `ci-self-heal.yml` can auto-fix known CI failures",
                             names) == ["line 1: ci-self-heal.yml"]


def test_the_legitimate_phrasings_are_not_flagged():
    """The sentences that document the deletion, and the example — the rule must tell them apart."""
    names = automation_names()
    assert unresolved_claims("`ci-self-heal.yml` 已于 2026-09-21 删除（无调用者）", names) == []
    assert unresolved_claims(
        "| **New CI gate** | Add to `.github/workflows/` | 例如 `pr-benchmark.yml`（示例）|", names) == []
    assert unresolved_claims("The `manual-audit.yml` workflow was removed; see #1984.", names) == []
    assert unresolved_claims("`manual-audit.yml` 的功能由 `pr-checks.yml` 取代。", names) == []


def test_the_exemption_is_by_mention_not_by_document():
    """A document does not inherit an exemption because one of its lines is historical."""
    names = automation_names()
    text = ("我们删除了 `ci-self-heal.yml`（历史）。\n"
            "\n"
            "\n"
            "\n"
            "现在由 `manual-audit.yml` 负责，它在 main 上。\n")
    assert unresolved_claims(text, names) == ["line 5: manual-audit.yml"]


def test_examples_inside_code_fences_are_ignored():
    """`.github/workflows/x.yml` is the *shape* of a command in repo-operations.md, not a claim."""
    names = automation_names()
    text = "```bash\npython3 -c \"import yaml; yaml.safe_load(open('.github/workflows/x.yml'))\"\n```\n"
    assert unresolved_claims(text, names) == []


def test_a_sentence_final_period_is_not_swallowed_into_the_name():
    """`[A-Za-z0-9_.-]+` used to absorb the full stop, so a valid path was reported as a missing
    workflow named `lesson-security.yml.`. The capture is anchored now."""
    names = automation_names()
    text = ("See `.github/workflows/lesson-security.yml`. "
            "And `.github/workflows/no-such-workflow.yml` for the failure case.\n")
    assert unresolved_claims(text, names) == ["line 1: no-such-workflow.yml"]


def test_the_qualified_form_is_matched_without_backticks():
    """A table cell or a bare path counts too — an example table row is how CI.md is written."""
    names = automation_names()
    assert unresolved_claims("| gate | .github/workflows/ghost.yml | x |", names) == [
        "line 1: ghost.yml"]


@pytest.mark.parametrize("doc", ["ARCHITECTURE.md", "docs/CI.md"])
def test_the_two_documents_that_bit_us_are_in_scope(doc):
    assert doc in ENUMERATING_DOCS
