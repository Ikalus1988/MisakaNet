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
def test_the_rule_returns_what_the_gate_needs_for_each_path():
    """Behavioural half: evaluate the real function, not a paraphrase of it."""
    rule = _rule_source()
    # The rule text is a comment block plus one arrow function; hand the whole region to node and
    # pull the function out of it, so the test cannot drift from the workflow.
    body = rule
    script = f"""
{body}
const cases = {json.dumps(CASES)};
const wrong = [];
for (const [path, expected] of Object.entries(cases)) {{
  const got = isDocsFile(path);
  if (got !== expected) wrong.push(`${{path}}: got ${{got}}, expected ${{expected}}`);
}}
if (wrong.length) {{ console.error(wrong.join('\\n')); process.exit(1); }}
console.log(`${{Object.keys(cases).length}} paths classified as expected`);
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, (
        "the docs-only rule misclassifies paths:\n" + (result.stderr or result.stdout)
    )
    assert "as expected" in result.stdout
