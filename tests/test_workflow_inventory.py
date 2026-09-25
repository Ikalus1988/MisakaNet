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
    # GitHub accepts both spellings; the rules above match `\.ya?ml`, so the loader must too.
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted(list(WF_DIR.glob("*.yml")) + list(WF_DIR.glob("*.yaml")))}


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
    others = {n: t for n, t in workflows.items()}
    for name, text in workflows.items():
        triggers = _triggers(text)
        if triggers != {"workflow_call"}:
            continue
        # The reference has to be an invocation. A bare substring match is satisfied by a comment, a
        # `paths:` filter or an `echo` that happens to name the file — the rule would be green while
        # nothing calls it, which is the state it exists to catch.
        pattern = re.compile(rf"uses:\s*(\./)?\.github/workflows/{re.escape(name)}")
        referenced = any(pattern.search(t) for n, t in others.items() if n != name)
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


# `retry` is called by cite-lesson.yml and lesson-notify.yml. `classify-failure` is not called by any
# workflow: it is kept as a tested library (its test encodes "a real bug is not a flaky one"), and it
# is listed here so its state is a decision rather than an oversight. Anything else must be called.
UNWIRED_ACTIONS = {"classify-failure": "kept as a tested library; no workflow calls it yet"}


def uncalled_actions(workflows: dict[str, str], actions: dict[str, str],
                     unwired: dict[str, str] = None) -> list[str]:
    """An action under `.github/actions/` that no workflow invokes."""
    unwired = UNWIRED_ACTIONS if unwired is None else unwired
    all_text = "\n".join(workflows.values())
    problems = []
    for name in actions:
        if name in unwired:
            assert unwired[name].strip(), f"{name} is exempt with an empty reason"
            continue
        if not re.search(rf"uses:\s*(\./)?\.github/actions/{re.escape(name)}(/|\s|$)", all_text):
            problems.append(
                f".github/actions/{name} is invoked by no workflow — an action nothing calls is a "
                f"capability that exists only in the file list (#1994 review); wire it up, delete it, "
                f"or add it to UNWIRED_ACTIONS with the reason")
    return problems


def _actions() -> dict[str, str]:
    out = {}
    for path in sorted((REPO / ".github" / "actions").glob("*/action.yml")):
        out[path.parent.name] = path.read_text(encoding="utf-8")
    return out


def test_no_composite_action_is_left_uncalled():
    problems = uncalled_actions(load_workflows(), _actions())
    assert not problems, "\n  ".join(problems)


def test_the_uncalled_action_rule_catches_the_one_this_review_deleted():
    """`notify-failure` was invoked by exactly one workflow — the one deleted as an orphan (#1984),
    which left the action behind with no caller and no test."""
    assert not (REPO / ".github" / "actions" / "notify-failure").exists()
    fixture_workflows = {"a.yml": "name: A\non:\n  push:\njobs:\n  a:\n    runs-on: x\n"}
    fixture_actions = {"ghost": "name: Ghost\n"}
    assert uncalled_actions(fixture_workflows, fixture_actions) == [
        ".github/actions/ghost is invoked by no workflow — an action nothing calls is a capability "
        "that exists only in the file list (#1994 review); wire it up, delete it, or add it to "
        "UNWIRED_ACTIONS with the reason"]
    # …and a real invocation satisfies it.
    fixture_workflows["a.yml"] += "    steps:\n      - uses: ./.github/actions/ghost\n"
    assert uncalled_actions(fixture_workflows, fixture_actions) == []


def test_a_comment_naming_a_workflow_does_not_count_as_calling_it():
    """The substring hole the first version had: an echo is not an invocation."""
    fixture = {
        "lib.yml": "name: L\non:\n  workflow_call:\n    inputs:\n      x:\n        type: string\n",
        "user.yml": "name: U\non:\n  push:\njobs:\n  a:\n    runs-on: x\n    steps:\n"
                    "      - run: echo \"see .github/workflows/lib.yml\"\n",
    }
    assert orphaned_libraries(fixture), "a mention is not a call"


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


# ── the heading counts are claims about the table under them ─────────────────────────────────────
#
# Measured 2026-09-26: every section heading in `docs/CI.md` understated its own table — 17 rows were
# announced as 3 in 基础设施, 21 as 17 in 质量门禁, 22 as 16 in 数据/索引, 12 as 8, 15 as 12. Five
# headings, five wrong numbers, and the page's opening line invites the reader to trust them ("本页为
# 其完整索引"). A hand-maintained count with no gate is the same shape as the workflow inventory that
# rule 3 above exists to fix: it drifts silently, and the drift is invisible precisely because the
# number looks authoritative.
SECTION_HEADING = re.compile(r"^## +(.+?)（(\d+)）\s*$")


def section_count_problems(doc_text: str) -> list[str]:
    """Every `## 标题（N）` must have exactly N workflow rows under it."""
    problems: list[str] = []
    heading, declared, rows = None, None, 0

    def flush() -> None:
        if heading is not None and declared != rows:
            problems.append(
                f"docs/CI.md section {heading!r} announces {declared} workflow(s) but its table has "
                f"{rows} — the count is the first thing a reader believes about this page")

    for line in doc_text.splitlines() + ["## "]:
        match = SECTION_HEADING.match(line)
        if line.startswith("## "):
            flush()
            heading, declared, rows = (
                (match.group(1), int(match.group(2)), 0) if match else (None, None, 0))
            continue
        if heading is not None and re.match(r"^\| `[^`]+\.ya?ml` \|", line):
            rows += 1
    return problems


def test_every_section_heading_declares_the_number_of_rows_it_has():
    problems = section_count_problems(CI_DOC.read_text(encoding="utf-8"))
    assert not problems, "\n  ".join(problems)


def test_the_heading_count_rule_can_go_red():
    """Replayed on the real document with the numbers it actually had on 2026-09-26."""
    stale = CI_DOC.read_text(encoding="utf-8").replace("## 基础设施（6）", "## 基础设施（3）", 1)
    problems = section_count_problems(stale)
    assert len(problems) == 1 and "基础设施" in problems[0], problems


def test_the_heading_count_rule_ignores_headings_that_declare_no_count():
    """`## 说明与边界` and the quiet-automation table are not inventory counts; a rule that demanded
    one from every heading would be red for a reason nobody agreed to."""
    assert section_count_problems("## 说明与边界\n\n| `a.yml` | A | push |  |\n") == []


# ── an approval queue must not accumulate superseded runs (#2006's sibling, 2026-09-21) ───────────
#
# `deploy-worker.yml` is gated by the `release` environment's required reviewer, so every push that
# touches the worker creates a run that *waits*. Four were waiting when this was noticed, the oldest
# 22 hours old, while production reported `serverInfo.version 2.31.0` and `main` said 2.33.0 —
# approving the oldest would have deployed a stale worker.
#
# `cancel-in-progress: true` is safe exactly where the work is idempotent (a deploy publishes the
# commit it checked out; newest wins) and dangerous where it is not: `misakanet-publish`,
# `release-pypi` and `publish-mcp-registry` carry a *version*, so two waiting runs are two releases
# that must both happen. This rule encodes that distinction rather than a blanket "add concurrency".
IDEMPOTENT_APPROVAL_WORKFLOWS = {".github/workflows/deploy-worker.yml": "the newest commit is the one you want live"}
NON_IDEMPOTENT_APPROVAL_WORKFLOWS = {
    ".github/workflows/misakanet-publish.yml": "each dispatch names a version that must be published",
    ".github/workflows/release-pypi.yml": "each run publishes a version",
    ".github/workflows/publish-mcp-registry.yml": "each run publishes a version",
}


def approval_queue_problems(workflows: dict[str, str], repo: Path = REPO) -> list[str]:
    problems = []
    for rel, reason in IDEMPOTENT_APPROVAL_WORKFLOWS.items():
        name = Path(rel).name
        text = workflows.get(name)
        if text is None:
            continue
        if "cancel-in-progress: true" not in text:
            problems.append(
                f"{name} waits for an approval on every push and has no `cancel-in-progress: true`, "
                f"so superseded runs pile up and the queue shows production as current when it is "
                f"not ({reason})")
    for rel, reason in NON_IDEMPOTENT_APPROVAL_WORKFLOWS.items():
        name = Path(rel).name
        text = workflows.get(name)
        if text is None:
            continue
        if re.search(r"cancel-in-progress:\s*true", text):
            problems.append(
                f"{name} set `cancel-in-progress: true`, but {reason} — cancelling by workflow group "
                f"would silently drop a release")
    return problems


def test_the_approval_queue_does_not_accumulate_superseded_runs():
    problems = approval_queue_problems(load_workflows())
    assert not problems, "\n  ".join(problems)


def test_the_queue_rule_tells_the_two_kinds_apart():
    idempotent = {"deploy-worker.yml": "name: D\non:\n  push:\n"}
    assert approval_queue_problems(idempotent), "a deploy without cancel-in-progress must be caught"
    idempotent["deploy-worker.yml"] += "concurrency:\n  group: deploy-worker\n  cancel-in-progress: true\n"
    assert approval_queue_problems(idempotent) == []
    publisher = {"misakanet-publish.yml": "name: P\non:\n  workflow_dispatch:\nconcurrency:\n  group: p\n  cancel-in-progress: true\n"}
    problems = approval_queue_problems(publisher)
    assert problems and "would silently drop a release" in problems[0], problems


# ── rule: a matrix that fans out across operating systems must be bounded and supersedable ───────
#
# Measured 2026-09-21: five `Cross-Platform Tests` runs were alive at once. Two had been running for
# over 90 minutes because their jobs were started before `timeout-minutes` existed, and the nine
# windows jobs inside them held the account's runners. Thirty-odd runs then sat queued behind them —
# and because the queue was saturated, even the ubuntu legs, which normally finish in about two
# minutes, could not start at all. The hung jobs were the symptom; the reason the queue could pile up
# in the first place was that a superseded push had no way to cancel the run it replaced.
#
# So: a workflow whose job fans out over several operating systems must (a) declare a concurrency
# group it can cancel, and (b) bound each such job. Both halves are needed — a bound without a
# concurrency group still allows N superseded runs to hold N× the runners until the bound expires.

OS_FAMILIES = ("ubuntu", "windows", "macos")


def _os_families(job: dict) -> set[str]:
    matrix = ((job or {}).get("strategy") or {}).get("matrix") or {}
    values = matrix.get("os") if isinstance(matrix, dict) else None
    if not isinstance(values, list):
        return set()
    return {family for value in values if isinstance(value, str)
            for family in OS_FAMILIES if value.startswith(family)}


def unbounded_matrix_workflows(workflows: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for name, text in workflows.items():
        try:
            data = yaml.safe_load(text) or {}
        except Exception:
            continue  # malformed YAML is somebody else's rule
        jobs = data.get("jobs") or {}
        fanned = {job_name: job for job_name, job in jobs.items()
                  if len(_os_families(job)) >= 2}
        if not fanned:
            continue

        concurrency = data.get("concurrency")
        if not isinstance(concurrency, dict) or not concurrency.get("group"):
            problems.append(
                f"{name}: its job(s) {sorted(fanned)} fan out across operating systems but the "
                "workflow declares no concurrency group — a superseded push cannot cancel the run it "
                "replaced, and those runners keep being held while the new one waits")
        elif "cancel-in-progress" not in concurrency:
            problems.append(
                f"{name}: concurrency declares a group but no `cancel-in-progress`, so superseded "
                "runs queue instead of being cancelled")

        for job_name, job in sorted(fanned.items()):
            timeout = job.get("timeout-minutes")
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                problems.append(
                    f"{name}: job '{job_name}' fans out across operating systems with no positive "
                    "`timeout-minutes` — a hung leg then holds its runner for the default six hours")
    return problems


def test_a_multi_os_matrix_is_bounded_and_cancellable():
    problems = unbounded_matrix_workflows(load_workflows())
    assert not problems, (
        "these workflows can starve the runner pool (see the note above the rule):\n  "
        + "\n  ".join(problems))


def _matrix_workflow(concurrency: str = "", timeout: str = "timeout-minutes: 30") -> str:
    return (
        "name: sample\non:\n  pull_request:\n"
        + concurrency
        + "jobs:\n  test:\n    runs-on: ${{ matrix.os }}\n    "
        + timeout + "\n    strategy:\n      matrix:\n        os: [ubuntu-latest, windows-latest]\n"
    )


def test_the_matrix_rule_catches_a_missing_concurrency_group():
    assert unbounded_matrix_workflows({"sample.yml": _matrix_workflow()}), (
        "a fan-out with no concurrency group is exactly how superseded runs piled up")


def test_the_matrix_rule_catches_a_group_that_cannot_cancel():
    workflow = _matrix_workflow("concurrency:\n  group: sample-${{ github.ref }}\n")
    assert unbounded_matrix_workflows({"sample.yml": workflow}), (
        "declaring a group without `cancel-in-progress` still queues every superseded run")


def test_the_matrix_rule_catches_a_missing_timeout():
    workflow = _matrix_workflow("concurrency:\n  group: g\n  cancel-in-progress: true\n", timeout="")
    problems = unbounded_matrix_workflows({"sample.yml": workflow})
    assert any("timeout-minutes" in p for p in problems), problems


def test_the_matrix_rule_leaves_single_os_workflows_alone():
    """No false positives: a workflow that runs on one platform cannot starve the pool this way."""
    single = ("name: sample\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
              "    strategy:\n      matrix:\n        python-version: ['3.12', '3.13']\n")
    assert unbounded_matrix_workflows({"sample.yml": single}) == []
