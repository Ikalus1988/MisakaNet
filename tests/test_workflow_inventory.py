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

import fnmatch
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



# ── rule 4: a JavaScript test no workflow runs is a check that measures nothing ─────────────────

# `node --test <path>` invocations, extracted per step. Two things this must get right, both of
# which a naive regex over the whole file gets wrong:
#
#   * **Comments are not invocations.** `mcp-stress.yml` and `pr-checks.yml` both explain their
#     globs in prose — "the unquoted `workers/*.test.mjs` did not reach …" — and a whole-file regex
#     happily collects those as paths that are covered. It would have green-lit every orphan in the
#     tree on the strength of a sentence describing a bug that was already fixed.
#   * **`node --test` resolves against the step's `working-directory`.** `fatal-guard.yml` runs
#     `node --test 'tests/*.test.js'` with `working-directory: packages/fatal-guard`, so the path it
#     covers is `packages/fatal-guard/tests/*.test.js`, not `tests/*.test.js`. Without that, five
#     tests that really do run looked orphaned — which is the over-firing that gets a rule like this
#     argued out of existence instead of fixed.
#
# The quoting is read as written rather than resolved by a shell, because that is the point:
# `node --test 'tests/*.test.js'` lets *node* expand the glob, while unquoted lets the shell do it,
# and with bash's `globstar` off an unquoted `workers/**/*.test.mjs` collapses to the top level and
# silently drops the nested file. `AGENTS.md` records that rule; here both spellings count as
# coverage, and matching is on the pattern as written, never on an expansion.
_STEP_SPLIT = re.compile(r"^\s{2,}-\s", re.M)
_WORKING_DIR = re.compile(r"^\s+working-directory:\s*(?P<dir>[^\s#]+)", re.M)
_NODE_TEST = re.compile(r"node\s+--test\s+(?P<arg>[^\n|;&]+)")
_COMMENT = re.compile(r"(?<!:)#[^\n]*")


def _strip_quotes(arg: str) -> str:
    return arg.strip().strip("\"'").strip()


def _covered_paths(workflows: dict[str, str]) -> list[str]:
    """Every repo-relative path a `node --test` invocation in this tree could reach."""
    seen: list[str] = []
    for text in workflows.values():
        job_wd = _WORKING_DIR.search(text)
        for step in _STEP_SPLIT.split(text):
            body = _COMMENT.sub("", step)
            step_wd = _WORKING_DIR.search(body)
            prefix = (step_wd or job_wd).group("dir").strip() if (step_wd or job_wd) else ""
            for match in _NODE_TEST.finditer(body):
                arg = _strip_quotes(match.group("arg"))
                if not arg:
                    continue
                seen.append(f"{prefix}/{arg}" if prefix and not arg.startswith("/") else arg)
    return seen


def js_tests_outside_workers() -> list[str]:
    """Every JS test file that is not under `workers/`, as a repo-relative POSIX path.

    The worker suite is one `node --test 'workers/**/*.test.mjs'` line covering 75 files, so
    per-file coverage there would be noise. Everything else is named or globbed individually.
    """
    found: set[str] = set()
    for pattern in ("tests/*.test.js", "tests/*.test.mjs",
                    "packages/*/tests/*.test.js", "packages/*/tests/*.test.mjs",
                    "integrations/*/tests/*.test.js", "integrations/*/tests/*.test.mjs"):
        for candidate in sorted(REPO.glob(pattern)):
            if candidate.is_file():
                found.add(candidate.relative_to(REPO).as_posix())
    return sorted(found)


def unrun_js_tests(workflows: dict[str, str]) -> list[str]:
    """Test files no workflow can execute.

    `tests/frontend.test.js` was in this set until 2026-10-07 — it imported `vitest`, which the
    root `package.json` does not depend on — along with four of the five tests in
    `packages/fatal-guard/tests/`, which `fatal-guard.yml` ran one at a time out of five.
    """
    patterns = _covered_paths(workflows)
    return [test for test in js_tests_outside_workers()
            # `fnmatch`'s `*` crosses `/`, which is what a shell-free comparison needs: the
            # patterns are compared as written and never expanded, so a directory prefix still
            # has to match the file's own path.
            if not any(fnmatch.fnmatch(test, pat) for pat in patterns)]


def test_no_javascript_test_is_left_without_a_workflow_that_runs_it():
    orphans = unrun_js_tests(load_workflows())
    assert not orphans, (
        "these JavaScript test files are executed by nothing, so they cannot fail and cannot "
        "help:\n  " + "\n  ".join(orphans)
        + "\n\nA file no workflow runs is worse than no file: it reads as coverage in review and "
        "in the tree, while `pytest` (which collects `test_*.py` only) never sees it either. Add a "
        "`node --test` line to a workflow, or delete the file."
    )


def test_the_unrun_test_rule_would_catch_the_frontend_file_it_was_written_for():
    """The self-test: the rule is evidence only if it fires on the case that motivated it."""
    workflows = load_workflows()
    assert "tests/frontend.test.js" in js_tests_outside_workers(), (
        "the file this rule exists for is gone or renamed — check that the rule still aims at "
        "something"
    )
    stripped = {name: re.sub(r"[^\n]*frontend\.test\.js[^\n]*", "", text)
                for name, text in workflows.items()}
    assert "tests/frontend.test.js" in unrun_js_tests(stripped), (
        "removing every reference to tests/frontend.test.js did not make the rule fire — the "
        "matching is too loose to be evidence of anything"
    )


def test_a_glob_credits_the_files_it_names_though_no_workflow_lists_them():
    """The over-firing direction. `fatal-guard.yml` says `node --test 'tests/*.test.js'` and never
    names the five files; a rule demanding a literal path per file would report all five as
    orphaned, and the first person to hit that would delete the rule rather than its author."""
    workflows = load_workflows()
    assert "packages/fatal-guard/tests/smoke.test.js" not in unrun_js_tests(workflows), (
        "a working-directory-relative glob is not being credited with the files it names"
    )


def test_prose_describing_a_glob_does_not_count_as_running_it():
    """Comments are stripped, so a sentence about a fixed bug cannot green-light an orphan."""
    workflows = load_workflows()
    probe = dict(workflows)
    probe["zz-probe.yml"] = (
        "name: probe\njobs:\n  probe:\n    steps:\n      - name: talk about a glob\n"
        "        run: echo the unquoted `tests/*.test.js` did not reach the nested file\n"
    )
    assert unrun_js_tests(probe) == unrun_js_tests(workflows), (
        "a comment mentioning a glob changed which files the rule considers covered"
    )



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
    """Replayed on the real document, with a wrong number derived from the one it declares.

    The first version hardcoded "基础设施（6）" as the string to replace, so adding the seventh row
    (`install-smoke.yml`, 2026-09-30) quietly turned this guard into a no-op: `str.replace` found nothing,
    the stale copy was byte-identical to the real one, and the assertion that the rule reports a problem
    failed instead of the rule. Deriving the current number keeps the replay honest across inventory edits.
    """
    text = CI_DOC.read_text(encoding="utf-8")
    heading = re.search(r"(?m)^## 基础设施（(\d+)）$", text)
    assert heading, "the section heading this replay mutates is gone — update the replay with it"
    wrong = "3" if heading.group(1) != "3" else "4"
    stale = text.replace(heading.group(0), f"## 基础设施（{wrong}）", 1)
    assert stale != text, "the mutation did not take"
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


# ── rule: a workflow must not subscribe to an event its own runs re-emit (2026-10-02) ─────────────
#
# `check_suite: [completed]` and `check_run: [completed]` fire for the check suites and check runs
# that GitHub Actions itself creates — and **every workflow run creates one**. A workflow that
# subscribes to either is therefore (at least partly) its own trigger:
#
#     run → its own check suite / check run completes → check_suite|check_run → run → …
#
# Measured on `dedc383b`, main's tip from 04:07:48Z to 05:22:42Z (the next commit landed at
# 05:22:42Z, so nobody pushed to it during either window below):
#
# * **280 check suites** on that one commit; **276 are from `github-actions`**. The only non-Actions
#   suite that ever *completed* is `cloudflare-workers-and-pages` at 04:08:19Z (the other three never
#   left `queued`).
# * **276 check runs** on it, and **0 of them carry a `pull_requests` entry** — so `pull_requests` is
#   not a filter that can exclude this repository's own re-emitted events.
# * the three subscribers started **57 distinct seconds** of the day at the *identical* timestamp.
# * `Auto-Merge Lessons` started **37 of its 39** `check_suite` runs on that commit within 60 s of a
#   completed `github-actions` suite on the same commit (the other two within 748 s).
#
# So a subscription is allowed only when the workflow also carries a job `if:` that *proves* it
# excludes its own re-emitted events. Two guards qualify:
#
# * `check_suite` — a test on `check_suite.app.slug`. Actions' own suites carry
#   `app.slug == 'github-actions'`, so naming any other app excludes them
#   (`workers-builds-watch.yml` admits only `cloudflare-workers-and-pages`).
# * `check_run` — a test on `check_run.app.slug`, or a `check_run.name != '<own>'` against one of
#   *this workflow's own* check-run names. GitHub names a job's check run after `jobs.<id>.name`, and
#   after the job id when no `name:` is given (the job id of `pr-quality-gate.yml` is
#   `quality-labels`, which is exactly the check run it used to re-trigger on). The coupling is the
#   point: renaming that job renames the check run, so the guard has to be updated with it.
#
# This rule reads the workflow files rather than the run history on purpose — the run history is what
# it exists to keep clean, and the history of a repository this busy is not available to a reader of
# a commit.
SELF_TRIGGERING_EVENTS = {"check_suite", "check_run"}


def _workflow_jobs(spec: dict) -> dict:
    jobs = spec.get("jobs")
    return jobs if isinstance(jobs, dict) else {}


def _job_guard_text(spec: dict) -> str:
    """Every job-level `if:` in the workflow, joined (the guards live at job level, not trigger level)."""
    return "\n".join(
        job["if"] for job in _workflow_jobs(spec).values()
        if isinstance(job, dict) and isinstance(job.get("if"), str))


def _own_check_run_names(spec: dict) -> set[str]:
    """The check-run names this workflow's own jobs produce (`jobs.<id>.name`, else the job id)."""
    names = set()
    for job_id, job in _workflow_jobs(spec).items():
        declared = job.get("name") if isinstance(job, dict) else None
        names.add(declared if isinstance(declared, str) else str(job_id))
    return names


def _excludes_own_re_emitted_event(spec: dict, event: str) -> bool:
    """Does the workflow carry a guard that proves it is not its own trigger for `event`?"""
    guards = _job_guard_text(spec)
    if event == "check_suite":
        # Actions' own suites are `app.slug == 'github-actions'`; naming another app excludes them.
        return "check_suite.app.slug" in guards
    if "check_run.app.slug" in guards:
        return True
    return any(
        re.search(rf"check_run\.name\s*!=\s*['\"]{re.escape(own)}['\"]", guards)
        for own in _own_check_run_names(spec))


def self_triggering_triggers(workflows: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for name, text in workflows.items():
        try:
            spec = yaml.safe_load(text) or {}
        except Exception:
            continue  # malformed YAML is somebody else's rule
        if not isinstance(spec, dict):
            continue
        for event in sorted(_triggers(text) & SELF_TRIGGERING_EVENTS):
            if not _excludes_own_re_emitted_event(spec, event):
                problems.append(
                    f"{name}: `{event}: [completed]` also fires for the check runs/suites this "
                    f"repository's own workflows create — including this workflow's own — so the run "
                    f"re-emits the event that started it. Add a job `if:` that excludes them (for "
                    f"`check_suite`, a `check_suite.app.slug` other than `github-actions`; for "
                    f"`check_run`, a `check_run.name != '<this workflow's own job name>'`), or drop "
                    f"the trigger")
    return problems


def test_no_workflow_triggers_on_an_event_its_own_runs_re_emit():
    problems = self_triggering_triggers(load_workflows())
    assert not problems, (
        "these workflows are (at least partly) their own trigger:\n  " + "\n  ".join(problems))


# The two shapes this rule was written for, verbatim from `dedc383b`. Literals rather than a
# `git show`, because the checkout is shallow and that commit will fall out of it: the detector has to
# stay able to see the shape that was removed, on any checkout, or the rule is only green because
# nobody looks.
BEFORE_AUTO_MERGE_LESSONS = """name: Auto-Merge Lessons
on:
  pull_request:
    types: [labeled, synchronize, ready_for_review]
  check_suite:
    types: [completed]
jobs:
  auto-merge-lessons:
    runs-on: ubuntu-latest
    if: >
      github.event_name == 'pull_request'
      || github.event.check_suite.pull_requests[0].number != null
      || github.event.check_suite.head_branch != github.event.repository.default_branch
"""

BEFORE_PR_QUALITY_GATE = """name: PR Quality Gate
on:
  check_run:
    types: [completed]
  pull_request:
    types: [synchronize]
jobs:
  quality-labels:
    runs-on: ubuntu-latest
    if: github.event_name == 'check_run' || github.event_name == 'pull_request'
"""


def test_the_self_trigger_rule_catches_the_two_triggers_this_change_removed():
    """Positive control — the whole reason this rule exists.

    Verbatim `dedc383b`: the `check_suite` subscription whose `if:` only looked for an attached pull
    request (empty on `main`), and the `check_run` subscription whose `if:` accepted every check run,
    including the `quality-labels` one it creates itself. A rule that cannot see these is green for
    the same reason the loop was invisible.
    """
    problems = self_triggering_triggers({
        "auto-merge-lessons.yml": BEFORE_AUTO_MERGE_LESSONS,
        "pr-quality-gate.yml": BEFORE_PR_QUALITY_GATE,
    })
    assert any("auto-merge-lessons.yml" in p and "check_suite" in p for p in problems), problems
    assert any("pr-quality-gate.yml" in p and "check_run" in p for p in problems), problems


def test_a_pull_requests_guard_does_not_exclude_this_repositorys_own_events():
    """`pull_requests` is empty for every check run and suite on `main`, so it filters nothing.

    Measured 2026-10-02 on `dedc383b`: 0 of 276 check runs carry one, and all 71 `check_run`-triggered
    `PR Quality Gate` runs had `head_branch: main` with an empty `pull_requests`. This is the guard the
    old `auto-merge-lessons.yml` believed it had.
    """
    guard = ("name: X\non:\n  check_suite:\n    types: [completed]\njobs:\n  x:\n"
             "    runs-on: ubuntu-latest\n"
             "    if: github.event.check_suite.pull_requests[0].number != null\n")
    assert self_triggering_triggers({"x.yml": guard}), (
        "a `pull_requests` guard does not exclude the events this repository's own runs emit — that "
        "array is empty on `main`")


def test_the_self_trigger_rule_accepts_the_guards_this_change_kept():
    """The other direction: the guards that stayed have to pass, or the rule is unlivable.

    Both are the guarded forms shipped by this change, so this is also the assertion that the rule and
    the repository agree on what "proves it is not self-triggering" means.
    """
    keep = {
        "pr-quality-gate.yml": (
            "name: PR Quality Gate\non:\n  check_run:\n    types: [completed]\njobs:\n"
            "  quality-labels:\n    runs-on: ubuntu-latest\n"
            "    if: >-\n      github.event.check_run.name != 'quality-labels'\n"
            "      && github.event.check_run.pull_requests[0].number != null\n"),
        "workers-builds-watch.yml": (
            "name: Site build watch\non:\n  check_suite:\n    types: [completed]\njobs:\n"
            "  watch:\n    runs-on: ubuntu-latest\n"
            "    if: >-\n      github.event_name != 'check_suite'\n"
            "      || github.event.check_suite.app.slug == 'cloudflare-workers-and-pages'\n"),
    }
    assert self_triggering_triggers(keep) == [], self_triggering_triggers(keep)


def test_the_own_check_run_guard_is_read_against_the_workflows_own_job_names():
    """A `check_run.name` guard that names somebody *else's* check run is not a self-exclusion.

    The rule derives the names to exclude from the workflow's own jobs, so a guard naming a check run
    this workflow does not produce must still be reported — otherwise the guard could be about the
    wrong check run and the rule would not notice.
    """
    someone_elses = ("name: Y\non:\n  check_run:\n    types: [completed]\njobs:\n  y:\n"
                     "    runs-on: ubuntu-latest\n"
                     "    if: github.event.check_run.name != 'codecov'\n")
    assert self_triggering_triggers({"y.yml": someone_elses}), (
        "excluding a check run this workflow does not produce does not exclude its own")
