#!/usr/bin/env python3
"""Three rules that keep "what this repository automates" equal to what it actually does (#1984).

Measured on 2026-09-21 across all 75 workflow records and their run histories, three ways the
Actions list drifted from reality:

* **`ci-lesson-search.yml` had run 100 times and executed its steps zero times.** Its only entry was
  `workflow_run` on a failing `Cross-Platform Tests`, and that workflow is 100/100 success — so a
  capability the repository advertises had never been exercised, and the only way to exercise it was
  to break CI on purpose. A path nobody can trigger is not a tested path.
* **`ci-self-heal.yml` was an orphaned library.** It is a reusable workflow (`workflow_call`) whose
  last invocation was 2026-06-07 and whose four runs all failed; nothing in the repository called it,
  and `docs/CI.md` described it as "被调用" (called). Code search across GitHub for
  `Ikalus1988/MisakaNet/.github/workflows` returns **0** results, so no external repository calls it
  either — measured before deleting, the same way §23.2 measured the intake bot before moving it.
* **`docs/CI.md` listed 54 of 70 workflow files.** No row described a file that does not exist, but
  eighteen real automations were absent from the only page that claims to enumerate them.

Each rule is a function over a mapping of path → workflow text, so the mutation cases below run a
mutated copy through the same code the repository is judged by.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the trigger blocks")

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / ".github" / "workflows"
CI_DOC = REPO / "docs" / "CI.md"


def _on_block(workflow: dict) -> dict:
    """The `on:` mapping. PyYAML resolves the bare key `on` to the boolean True (YAML 1.1)."""
    return workflow.get("on") or workflow.get(True) or {}


def _triggers(text: str) -> set[str]:
    block = _on_block(yaml.safe_load(text))
    return set(block.keys()) if isinstance(block, dict) else {str(block)}


def load_workflows() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(WF_DIR.glob("*.yml"))}


# ── rule 1: a path that only a failure can start must also be startable by hand ──────────────────

def unverifiable_paths(workflows: dict[str, str]) -> list[str]:
    problems = []
    for name, text in workflows.items():
        triggers = _triggers(text)
        if "workflow_run" in triggers and "workflow_dispatch" not in triggers:
            problems.append(
                f"{name}: starts only from `workflow_run`, so the only way to test it is to make "
                f"another workflow fail — add `workflow_dispatch`")
    return problems


# ── rule 2: a reusable workflow nobody calls is a capability that does not exist ─────────────────

def orphaned_libraries(workflows: dict[str, str]) -> list[str]:
    """A `workflow_call`-only file must be referenced by another workflow in this repository."""
    problems = []
    all_text = "\n".join(workflows.values())
    for name, text in workflows.items():
        triggers = _triggers(text)
        if triggers != {"workflow_call"}:
            continue
        # `uses: ./.github/workflows/<name>` is how a local reusable workflow is invoked.
        referenced = f".github/workflows/{name}" in all_text.replace(text, "", 1)
        if not referenced:
            problems.append(
                f"{name}: declares only `workflow_call` (a library) and no workflow in this "
                f"repository calls it. Either wire it up or delete it — an uncalled library shows up "
                f"in the Actions list as a capability (#1984: ci-self-heal.yml)")
    return problems


# ── rule 3: the inventory page must equal the directory ──────────────────────────────────────────

def inventory_problems(workflows: dict[str, str], doc_text: str) -> list[str]:
    listed = set(re.findall(r"^\| `([^`]+\.ya?ml)` \|", doc_text, re.M))
    actual = set(workflows)
    problems = []
    for missing in sorted(actual - listed):
        problems.append(f"{missing} exists but docs/CI.md does not list it")
    for ghost in sorted(listed - actual):
        problems.append(f"docs/CI.md lists {ghost}, which does not exist")
    return problems


def test_every_path_that_only_a_failure_can_start_is_also_startable_by_hand():
    problems = unverifiable_paths(load_workflows())
    assert not problems, "\n  ".join(problems)


def test_no_reusable_workflow_is_left_uncalled():
    problems = orphaned_libraries(load_workflows())
    assert not problems, "\n  ".join(problems)


def test_the_ci_inventory_equals_the_workflow_directory():
    problems = inventory_problems(load_workflows(), CI_DOC.read_text(encoding="utf-8"))
    assert not problems, "\n  ".join(problems)


# ── guard the guards: a rule that cannot fail is not a rule ──────────────────────────────────────

def test_a_workflow_run_without_dispatch_is_caught():
    fixture = {"x.yml": "name: X\non:\n  workflow_run:\n    workflows: [CI]\n    types: [completed]\n"}
    assert unverifiable_paths(fixture), "the rule must flag a failure-only path"


def test_an_uncalled_library_is_caught():
    fixture = {
        "lib.yml": "name: L\non:\n  workflow_call:\n    inputs:\n      x:\n        type: string\n",
        "user.yml": "name: U\non:\n  push:\njobs:\n  a:\n    runs-on: ubuntu-latest\n",
    }
    assert orphaned_libraries(fixture), "the rule must flag a reusable workflow nobody calls"
    # …and must accept the same file once something calls it.
    fixture["user.yml"] += "    steps:\n      - uses: ./.github/workflows/lib.yml\n"
    assert orphaned_libraries(fixture) == []


def test_a_missing_or_ghost_inventory_row_is_caught():
    workflows = {"a.yml": "name: A\non:\n  push:\n"}
    assert inventory_problems(workflows, "| `a.yml` | A | push |  |\n") == []
    assert inventory_problems(workflows, "") == ["a.yml exists but docs/CI.md does not list it"]
    # Both directions at once: `b.yml` is a ghost *and* `a.yml` is unlisted. The first version of this
    # expectation listed only the ghost — the rule was right and the assertion was wrong.
    assert inventory_problems(workflows, "| `b.yml` | B | push |  |\n") == [
        "a.yml exists but docs/CI.md does not list it",
        "docs/CI.md lists b.yml, which does not exist"]
    assert inventory_problems(workflows, "| `a.yml` | A | push |  |\n| `b.yml` | B | push |  |\n") == [
        "docs/CI.md lists b.yml, which does not exist"]


def test_the_orphan_rule_would_have_caught_the_file_this_issue_deleted():
    """The deleted case, replayed: it was `workflow_call`-only and nothing referenced it."""
    deleted = REPO / ".github" / "workflows" / "ci-self-heal.yml"
    assert not deleted.exists(), "ci-self-heal.yml was deleted by #1984; this test is its tombstone"
    fixture = dict(load_workflows())
    fixture["ci-self-heal.yml"] = "name: CI Self-Heal\non:\n  workflow_call:\n    inputs:\n      command:\n        type: string\n"
    problems = orphaned_libraries(fixture)
    assert any("ci-self-heal.yml" in p for p in problems), (
        "re-adding the file without a caller must turn the rule red")
