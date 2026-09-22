#!/usr/bin/env python3
"""The docs auto-merge gate must never treat a lesson as documentation.

`auto-merge-docs.yml` merges external contributors' docs-only PRs to main, where `docs.yml` publishes
them. Its "docs-only" test was

    f.filename.endsWith('.md') || f.filename.endsWith('.txt') || f.filename.startsWith('docs/') || …

— which is true for **any** `.md` anywhere, `lessons/**` included, directly under a comment saying
"`lessons/` is deliberately NOT docs-only". And `.github/labeler.yml` gives `area:docs` to every
`**/*.md`, so the job's label condition is satisfied by lesson PRs too: #1746 and #1750 carry
`area:docs` + `area:lessons` + `lessons-only` + `needs-human-review`, and both are still open.

The hole was armed, not theoretical: the job runs on `synchronize` and `ready_for_review`, so an
external lesson PR that is pushed again (or leaves draft) after the label lands reaches
`gh pr merge --auto` with `docs-only: true`. The only thing that stopped those two was `needs-dco` — a
check about commit trailers, not about review (found 2026-09-19).

So the rule is now one named function in the workflow, and this test *runs* it over a table of paths
instead of grepping for it. Node is used because the rule executes inside Actions; where node is
unavailable the behavioural half is skipped rather than faked.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's trigger block")

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "auto-merge-docs.yml"
START = "// ── docs-only rule"
END = "// ── end docs-only rule ──"

# path -> is this a docs-only PR made of exactly this one file?
CASES = {
    # prose a human reads: yes
    "docs/field-reports/2026-09-18-report.md": True,
    "docs/setup-reports/x.yaml": True,
    "docs/architecture.md": True,
    "README.md": True,
    "CONTRIBUTING.md": True,
    "CHANGELOG.md": True,
    "JOIN.md": True,
    # machine input / the site frame: a person decides
    "docs/.well-known/mcp.json": False,
    "docs/.well-known/llms.txt": False,
    "docs/index.html": False,
    # lessons are read and acted on by agents: a human merges them, always
    "lessons/contrib/some-lesson.md": False,
    "lessons/en/ci-dco-fork-pr-signoff.md": False,
    # neither: a stray file at the root, or a doc under a code directory, is not "the docs"
    "fork-error.txt": False,
    "scripts/README.md": False,
    "workers/notes.md": False,
    ".github/workflows/x.yml": False,
    "search_knowledge.py": False,
}


def _rule_source() -> str:
    """The region between the two marker comments, marker lines excluded.

    Sliced by whole lines: the start marker carries a trailing note, and taking a character offset
    from the marker text left that note dangling as invalid JavaScript (the first version of this
    test failed with `SyntaxError: Unexpected identifier 'place'`).
    """
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if START in line)
    end = next(i for i, line in enumerate(lines) if END in line)
    assert end > start, "the docs-only rule markers are out of order"
    return "\n".join(lines[start + 1:end])


def test_the_rule_exists_and_excludes_the_non_prose_surfaces_by_name():
    """Structural half: the exclusions are present even where node cannot run it."""
    rule = _rule_source()
    for exclusion in ("lessons/", "docs/.well-known/", "docs/index.html"):
        assert exclusion in rule, f"the rule must exclude {exclusion} explicitly"
    assert "isDocsFile" in rule


def _job_condition() -> str:
    """The job's `if:` expression, comments removed.

    The comment above that condition *names* the automatically applied label it deliberately does not
    key on, so an assertion against the raw block text fails on the documentation — the third time
    today a rule was tripped by the prose explaining it.
    """
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("if: >"))
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start + 1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        body.append(line)
    return "\n".join(line for line in body if not line.strip().startswith("#"))


def test_a_person_has_to_let_a_pr_in_and_adding_the_label_is_what_triggers_the_check():
    """The opt-in label is the entry condition, and `labeled` is what fires on it.

    Keying on a label nobody applies automatically is only half a design: the job also has to *run*
    when that label appears. Both halves are asserted here, because either one alone silently
    disables the channel — which is exactly how it produced nothing for as long as it existed.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True) or {}
    assert "pull_request_target" in triggers, (
        "a fork PR's `pull_request` run is held as `action_required` until a maintainer approves it "
        "(#1801: eight suites, including this workflow, that never executed) — and external "
        "contributors are exactly who this gate is for"
    )
    # The trigger is only safe because the workflow never touches PR code. Pin that, or a later edit
    # turns this into the classic `pull_request_target` vulnerability.
    # Comments stripped: the workflow's own comment names `actions/checkout` while explaining why it
    # must never appear here (the fourth time today a rule was tripped by the prose documenting it).
    text = "\n".join(line for line in WORKFLOW.read_text(encoding="utf-8").splitlines()
                     if not line.strip().startswith("#"))
    assert "actions/checkout" not in text, (
        "pull_request_target + checking out the PR head + a write token is the textbook exploit; this "
        "workflow must stay API-only"
    )
    types = triggers["pull_request_target"]["types"]
    for event in ("labeled", "unlabeled", "edited"):
        assert event in types, (
            f"the job must trigger on `{event}`: every label it keys on (auto-merge-eligible, "
            "lessons-only, needs-human-review) is applied after the PR opens, a maintainer removing a "
            "refusal label is a decision to re-evaluate, and retargeting the base branch changes which "
            "workflow file the PR is even running (#1801, 2026-09-19)"
        )
    job_if = _job_condition()
    assert "auto-merge-eligible" in job_if, (
        "the entry condition must be the maintainer's opt-in label, not one applied automatically "
        "(`area:docs` comes from .github/labeler.yml for every *.md, lessons included)"
    )
    assert "area:docs" not in job_if, (
        "an automatically applied label must not be able to let a PR in on its own"
    )
    for refusal in ("lessons-only", "needs-human-review"):
        assert refusal in job_if, f"the job condition must refuse PRs labelled '{refusal}'"


@pytest.mark.skipif(shutil.which("node") is None, reason="node runs the rule inside Actions")
def test_the_rule_returns_what_the_gate_needs_for_each_path(tmp_path):
    """Behavioural half: evaluate the real function, not a paraphrase of it."""
    rule = _rule_source()
    # The rule text is a comment block plus one arrow function. It is written to a temp module and
    # *executed as a file*, rather than passed to `node -e`: a program assembled by string
    # interpolation and handed to an interpreter is the shape a scanner (rightly) reports as a
    # potential injection, and there is no reason for a test to carry that shape — the file says what
    # it is, and the case table travels with it as data.
    program = (
        rule
        + "\nconst cases = " + json.dumps(CASES) + ";\n"
        + "const wrong = [];\n"
        + "for (const [path, expected] of Object.entries(cases)) {\n"
        + "  const got = isDocsFile(path);\n"
        + "  if (got !== expected) wrong.push(`${path}: got ${got}, expected ${expected}`);\n"
        + "}\n"
        + "if (wrong.length) { console.error(wrong.join('\\n')); process.exit(1); }\n"
        + "console.log(`${Object.keys(cases).length} paths classified as expected`);\n"
    )
    program_path = tmp_path / "docs-only-rule.mjs"
    program_path.write_text(program, encoding="utf-8")
    result = subprocess.run(["node", str(program_path)], capture_output=True, text=True)
    assert result.returncode == 0, (
        "the docs-only rule misclassifies paths:\n" + (result.stderr or result.stdout)
    )
    assert "as expected" in result.stdout

# ── the two gaps that share this file: what the merge does downstream, and what a refusal says ───
#
# Both were measured on 2026-09-21, and they fail in opposite directions: the merge was invisible to
# the rest of the repository, and the refusal was invisible to the person who opted in.
#
# Each check is a function over the workflow *text*, so the mutation cases below feed a mutated copy
# through the same code the repository is judged by — asserting "the mutation took" and then asserting
# something trivially true is not a guard, it is decoration.


def _steps_of(text: str) -> list[dict]:
    return yaml.safe_load(text)["jobs"]["auto-merge"]["steps"]


def _step_named(text: str, name: str) -> dict:
    for step in _steps_of(text):
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} — the steps are {[s.get('name') for s in _steps_of(text)]}")


def _executable(step: dict) -> str:
    """A step's code, comments stripped.

    The comments in this workflow name the constructs the rules forbid (that is what they are for), so
    a check that reads the raw text is satisfied by the explanation of the bug it is looking for.
    """
    text = (step.get("run") or "") + "\n" + (step.get("with", {}).get("script") or "")
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def merge_token_problems(text: str) -> list[str]:
    """`GITHUB_TOKEN` on the merge, or a token widened to the `workflow` scope."""
    problems = []
    step = _step_named(text, "Enable auto-merge")
    token = (step.get("env") or {}).get("GH_TOKEN", "")
    if "SHELDON_PAT" not in token:
        problems.append(f"the merge does not use the PAT (GH_TOKEN={token!r})")
    if "GITHUB_TOKEN" in token:
        problems.append(
            "a `GITHUB_TOKEN` merge produces a push that starts no workflows, so the post-merge chain "
            "(Release Please, Leaderboard Watch, the count/badge mirrors, docs deploy) never runs")
    if "workflow" in json.dumps(step.get("env") or {}):
        problems.append(
            "the PAT must not need the `workflow` scope: this gate merges docs only, and that scope "
            "would let an auto-merged PR change CI itself")
    return problems


def refusal_report_problems(text: str) -> list[str]:
    """The refusal path must post (and update) a comment that names the reason and the way back in."""
    problems = []
    reporting = [s for s in _steps_of(text)
                 if (s.get("if") or "").strip() == "steps.check.outputs.docs-only != 'true'"]
    if not reporting:
        return ["no step runs when docs-only is false: the gate can refuse a PR carrying the "
                "maintainer's opt-in label and leave no trace anywhere a human looks"]
    code = _executable(reporting[0])
    if "createComment" not in code or "updateComment" not in code:
        problems.append(
            "the comment must be upserted (create + update): the gate wakes on labeled/unlabeled/"
            "edited/synchronize, so one PR can be evaluated many times")
    if "OFFENDERS" not in code and "offenders" not in code:
        problems.append("the refusal must name the files that broke the rule")
    if "label" not in code:
        problems.append(
            "the refusal must say how to be re-evaluated (re-apply `auto-merge-eligible`): "
            "eligibility can change without a push, and the reader cannot guess which events wake "
            "this gate")
    if "pr merge" in code:
        problems.append("the refusal path must not be able to merge")
    # A refusal that cannot see the check step's output cannot name the files.
    if "steps.check.outputs.offenders" not in json.dumps(reporting[0]):
        problems.append("the reporting step does not read the offender list from the check step")
    return problems


@pytest.mark.parametrize("check", [merge_token_problems, refusal_report_problems])
def test_the_two_gaps_stay_closed(check):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert check(text) == [], "; ".join(check(text))


def _mutate(tmp_path, mutate) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    mutated = mutate(text)
    assert mutated != text, "the mutation did not take — a mutation that does not mutate asserts nothing"
    return mutated


def test_reverting_the_merge_token_is_caught(tmp_path):
    mutated = _mutate(tmp_path, lambda t: t.replace("GH_TOKEN: ${{ secrets.SHELDON_PAT }}",
                                                    "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}"))
    assert merge_token_problems(mutated), "putting `GITHUB_TOKEN` back must be caught"


def test_granting_the_workflow_scope_is_caught(tmp_path):
    """The tempting "just in case" edit: it would let this channel merge a change to CI."""
    mutated = _mutate(tmp_path, lambda t: t.replace(
        "GH_TOKEN: ${{ secrets.SHELDON_PAT }}",
        "GH_TOKEN: ${{ secrets.WORKFLOW_PAT }}\n          WIDENED: workflow"))
    problems = merge_token_problems(mutated)
    assert any("workflow" in p for p in problems), problems


def test_dropping_the_refusal_report_is_caught(tmp_path):
    def drop(text: str) -> str:
        lines = text.splitlines(keepends=True)
        start = next(i for i, l in enumerate(lines) if "name: Report the refusal on the pull request" in l)
        end = next(i for i, l in enumerate(lines) if "name: Enable auto-merge" in l)
        return "".join(lines[:start - 1] + lines[end:])

    assert refusal_report_problems(_mutate(tmp_path, drop)), (
        "removing the reporting step must leave the rule with nothing to point at")


def test_a_stacked_comment_is_caught(tmp_path):
    """Regression shape: a refusal that only creates comments stacks one per event on a busy PR."""
    mutated = _mutate(tmp_path, lambda t: t.replace("updateComment", "createComment"))
    problems = refusal_report_problems(mutated)
    assert any("upsert" in p for p in problems), problems


# ── the rule's soundness: "all files" vs "some files" ────────────────────────────────────────────
#
# `pulls.listFiles` returns 30 files by default and orders them by filename, where `docs/…` sorts
# before `lessons/…`. A PR with 30 docs files and one lesson file therefore answered
# "docs-only: true" from a single call — the poisoning vector this gate exists to close, reachable
# on a fork PR because the trigger is `pull_request_target`. Truncation is the difference between
# "every file qualifies" and "the first page qualifies".


def file_listing_problems(text: str) -> list[str]:
    problems = []
    step = _step_named(text, "Check if docs-only")
    code = _executable(step)
    if "listFiles" not in code:
        return ["the check step no longer lists the PR's files"]
    if "paginate" not in code:
        problems.append(
            "the file list is not paginated: one `pulls.listFiles` call returns 30 files, so a PR "
            "with 30 docs files plus one lesson file is judged docs-only")
    if "per_page" not in code:
        problems.append("no `per_page`, so the page size is whatever the API defaults to")
    return problems


def test_the_docs_only_decision_reads_every_file(tmp_path):
    assert file_listing_problems(WORKFLOW.read_text(encoding="utf-8")) == []


def test_an_unpaginated_file_list_is_caught(tmp_path):
    def strip_pagination(text: str) -> str:
        return text.replace("await github.paginate(github.rest.pulls.listFiles, {",
                            "await github.rest.pulls.listFiles({").replace("per_page: 100,", "")

    mutated = _mutate(tmp_path, strip_pagination)
    assert "paginate" not in mutated, "the mutation did not take"
    assert file_listing_problems(mutated), "an unpaginated list must be caught"


def test_the_refusal_is_withdrawn_when_the_pr_qualifies():
    """Otherwise a merged PR keeps a comment saying it was refused — a lie that outlives its state."""
    text = WORKFLOW.read_text(encoding="utf-8")
    steps = _steps_of(text)
    withdraw = [s for s in steps if "Withdraw" in (s.get("name") or "")]
    assert withdraw, "no step reconciles the earlier refusal"
    code = _executable(withdraw[0])
    assert "deleteComment" in code and "auto-merge-docs" in code, code[:200]
    assert (withdraw[0].get("if") or "").strip() == "steps.check.outputs.docs-only == 'true'", (
        "the withdrawal must run on the acceptance path")
