#!/usr/bin/env python3
"""The intake classifier has to be able to say "this is not a failure report".

Why this file exists (2026-11-01)
---------------------------------
#4251 was a three-month plan for the Glama listing — a proposal, and it said so in its own words
("This is not a failure report, it is an executable three-month proposal"). It came in through
`misakanet_submit_intake`, whose `kind` enum is missing_lesson / stale_lesson /
new_lesson_candidate / question: there is no value for a proposal, so the submitter had to file it
as `new_lesson_candidate` *and* argue with the classifier in prose.

The classifier answered with four wrong labels at once — `lesson-candidate`, `type:bug`,
`priority:high`, `pending-review` — because the keyword rules see a document that discusses
failures and cannot see that it is not reporting one. `type:bug` and `pending-review` are the two
that cost something: one says the wrong thing about the submission, the other puts a proposal in
the queue that exists for lessons.

**The test that should have caught it could not.** `tests/test_intake_triage.py` mirrors the
classifier's priority scoring and type detection in Python; the rules actually run in JavaScript
inside `.github/workflows/issue-intake-triage.yml`, so the mirror drifts and never fails. This file
runs the *real* inline script under node with `github`/`core`/`context` stubbed, and asserts the
decisions it makes — the same shape `tests/test_auto_merge_docs.py` uses for the docs-only rule.

The trigger is deliberately narrow: only an explicit self-declaration routes a submission to
`proposal`. "Mentions failures" and "reads like a plan" are exactly the keyword guesses that
produced the wrong labels, so a case below pins that a lesson-shaped report keeps its route.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github/workflows/issue-intake-triage.yml"

# The bodies travel as data. They are shaped like the real submissions: the fields the workflow
# parses (`**Kind:**`, `## Problem`, ...) and enough prose to trigger the keyword rules.
PROPOSAL_BODY = """**Kind:** new_lesson_candidate
**Source:** cindy
**Dedup:** `5d209526-5e2`

## Problem

3-month plan: two tiers of work on the listing page. This is not a failure report, it is an
executable three-month proposal (proposal), please triage it as such.

The page puts us at number 13 with composite 51.2; the weighted mean is 85.3 and the relevance
multiplier is what holds it back. The list is rebuilt weekly.

## Fix (if known)

Month 1: declare the integration in the listing copy and add annotations to the tools. There were
error messages in the metric snapshot, which is why the keyword rules see failures here.

## Verification

Measurement, without an account: the public list page for the composite, the server page for the
tool score, and the weekly download counts.
"""

LESSON_BODY = """**Kind:** missing_lesson
**Source:** dsh
**Dedup:** `aaaabbbb-cc`

## Problem

pip install exits 1 behind a corporate proxy. The last two lines are:

```text
ERROR: Could not install packages due to an OSError: ReadTimeoutError
```

Note the classifier's bug rule matches whole words (`error`, `crash`, `traceback`): an exception
class name like `ReadTimeoutError` does not match it, which is why this body carries the log line
the way a real report does.

## What was tried

Exported HTTP_PROXY and HTTPS_PROXY; the failure persisted on the second index.

## Fix

Pass the proxy to the resolver explicitly and raise the retry budget.

## Verification

```bash
python -m pip install -r requirements.txt --proxy "$HTTPS_PROXY"
```

Expected: the install completes with exit code 0.
"""

QUESTION_BODY = """**Kind:** question
**Source:** cindy

## Problem

How do I configure MCP auth in production?
"""

FILLER = "Extra context for the priority scorer. " * 30


def _script() -> str:
    """The inline `actions/github-script` body, as it runs in Actions."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["triage"]["steps"]:
        script = step.get("with", {}).get("script")
        if script:
            return script
    raise AssertionError("no inline script in the triage job — this gate would be checking nothing")


def _cases() -> list[dict]:
    return [
        {
            "name": "a submission that declares itself not a failure report",
            "title": "[Intake] 3-month plan for the listing (proposal, not a failure report)",
            "body": PROPOSAL_BODY,
            "labels": ["intake", "mcp-intake", "pending-review", "type:bug", "priority:high"],
            "expect_classification": "proposal",
            "expect_type": "feature",
            "expect_removed": ["pending-review", "type:bug"],
            "expect_not_added": ["needs-ac", "pending-review"],
        },
        {
            "name": "a failure report, which must keep its route",
            "title": "[Intake] pip install ReadTimeoutError behind a corporate proxy",
            "body": LESSON_BODY,
            "labels": ["intake", "mcp-intake"],
            "expect_classification": "lesson-candidate",
            "expect_type": "bug",
            "expect_removed": [],
            "expect_not_added": [],
        },
        {
            "name": "a question, routed by its explicit kind",
            "title": "[Intake] How do I configure MCP auth?",
            "body": QUESTION_BODY,
            "labels": ["intake"],
            "expect_classification": "question",
            "expect_type": "question",
            "expect_removed": [],
            "expect_not_added": [],
        },
        {
            # The narrow-trigger contract: a report that merely discusses failures — the shape the
            # keyword rules were built for — is not a proposal. Filler keeps the length comparison
            # from making this case pass or fail for the wrong reason.
            "name": "a failure report that talks about errors at length is still a lesson candidate",
            "title": "[Intake] workflow trigger failure after token expiry",
            "body": LESSON_BODY + "\n" + FILLER,
            "labels": ["intake"],
            "expect_classification": "lesson-candidate",
            "expect_type": "bug",
            "expect_removed": [],
            "expect_not_added": [],
        },
        {
            # Re-triage after a rule change: the labels moved on #4251 but the comment above them
            # still said `lesson-candidate`, because the guard was "a triage comment exists" rather
            # than "it says this classification". A second triage pass has to be allowed to correct
            # the record — and to say that it did.
            "name": "a re-triage whose classification changed posts the correction",
            "title": "[Intake] 3-month plan for the listing (proposal, not a failure report)",
            "body": PROPOSAL_BODY,
            "labels": ["intake", "mcp-intake", "type:feature"],
            "prior_classification": "lesson-candidate",
            "expect_classification": "proposal",
            "expect_type": "feature",
            "expect_removed": [],
            "expect_not_added": ["needs-ac"],
            "expect_not_added": ["needs-ac", "pending-review"],
            "expect_comment": True,
            "expect_retriage_note": True,
        },
        {
            # The other half of that guard: an unchanged classification must not re-comment, or every
            # `edited` event on an intake issue would add a duplicate.
            "name": "a re-triage that agrees with the existing comment stays quiet",
            "title": "[Intake] 3-month plan for the listing (proposal, not a failure report)",
            "body": PROPOSAL_BODY,
            "labels": ["intake", "mcp-intake", "type:feature"],
            "prior_classification": "proposal",
            "expect_classification": "proposal",
            "expect_type": "feature",
            "expect_removed": [],
            "expect_not_added": ["needs-ac", "pending-review"],
            "expect_comment": False,
        },
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="the classifier is JavaScript inside the workflow")
def test_the_classifier_routes_what_it_says_it_routes(tmp_path: Path) -> None:
    """Run the real rule with the API stubbed, and read back the decisions it took."""
    program = (
        "const fs = require('node:fs');\n"
        "(async () => {\n"
        "const cases = " + json.dumps(_cases()) + ";\n"
        "const script = fs.readFileSync(process.argv[2], 'utf8');\n"
        "const results = [];\n"
        "for (const c of cases) {\n"
        "  const added = []; const removed = []; let classification = null; let issueType = null;\n"
        "  let commented = false; let commentBody = '';\n"
        "  const existing = new Set(c.labels);\n"
        "  const priorComments = c.prior_classification\n"
        "    ? [{ body: '<!-- misakanet-intake-triage -->\\n## MCP Intake Triage\\n\\n- Classification: `'\n"
        "        + c.prior_classification + '`\\n' }]\n"
        "    : [];\n"
        "  const core = { info: () => {}, setFailed: (m) => { throw new Error(m); } };\n"
        "  const github = {\n"
        "    rest: { issues: {\n"
        "      get: async () => ({ data: c }),\n"
        "      addLabels: async ({ labels }) => { for (const l of labels) added.push(l); },\n"
        "      removeLabel: async ({ name }) => { removed.push(name); },\n"
        "      createComment: async ({ body }) => {\n"
        "        commented = true; commentBody = body;\n"
        "        classification = (body.match(/- Classification: `([^`]+)`/) || [])[1] || null;\n"
        "        issueType = (body.match(/- Issue type: `([^`]+)`/) || [])[1] || null;\n"
        "        return { data: {} };\n"
        "      },\n"
        "      listComments: async () => ({ data: priorComments }),\n"
        "    } },\n"
        "    paginate: async (fn, params) => (await fn(params)).data,\n"
        "  };\n"
        "  const issue = { number: 1, title: c.title, body: c.body, labels: c.labels.map((name) => ({ name })) };\n"
        "  const context = { repo: { owner: 'o', repo: 'r' }, issue: { number: 1 }, payload: { issue } };\n"
        "  const run = new Function('github', 'core', 'context', 'require',\n"
        "    `return (async () => {\\n${script}\\n})();`);\n"
        "  await run(github, core, context, require);\n"
        "  results.push({ added, removed, classification, issueType, commented, commentBody, existing: [...existing] });\n"
        "}\n"
        "console.log('@@RESULTS@@' + JSON.stringify(results));\n"
        "})();\n"
    )
    script_path = tmp_path / "triage-script.js"
    script_path.write_text(_script(), encoding="utf-8")
    program_path = tmp_path / "harness.js"
    program_path.write_text(program, encoding="utf-8")

    result = subprocess.run(["node", str(program_path), str(script_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, f"the classifier harness failed:\n{result.stderr}{result.stdout}"
    marker = "@@RESULTS@@"
    assert marker in result.stdout, f"the harness printed no result line:\n{result.stdout}"
    decisions = json.loads(result.stdout.split(marker, 1)[1].strip())

    problems = []
    for case, got in zip(_cases(), decisions):
        name = case["name"]
        if case.get("expect_comment", True):
            if got["classification"] != case["expect_classification"]:
                problems.append(f"{name}: classified {got['classification']!r}, "
                                f"expected {case['expect_classification']!r}")
            if got["issueType"] != case["expect_type"]:
                problems.append(f"{name}: typed {got['issueType']!r}, expected {case['expect_type']!r}")
        else:
            # Nothing is posted, so the decision is only observable in the labels. That is enough:
            # `expect_not_added` below covers the one label a proposal must never gain, and triage
            # is allowed to (re)apply its standard set on every pass.
            pass
        for label in case["expect_removed"]:
            if label not in got["removed"]:
                problems.append(f"{name}: did not remove the contradicted label {label!r} "
                                f"(removed {got['removed']})")
        for label in case["expect_not_added"]:
            if label in got["added"]:
                problems.append(f"{name}: added {label!r}, which does not apply to this shape")
        if "expect_comment" in case and got["commented"] != case["expect_comment"]:
            problems.append(f"{name}: commented={got['commented']}, expected {case['expect_comment']}"
                            " (the guard must key on the classification, not on 'a comment exists')")
        if case.get("expect_retriage_note") and "Re-triaged:" not in got["commentBody"]:
            problems.append(f"{name}: the re-triage comment does not say the classification changed")
    assert not problems, "intake classifier decisions changed:\n- " + "\n- ".join(problems)


@pytest.mark.skipif(shutil.which("node") is None, reason="the classifier is JavaScript inside the workflow")
def test_the_proposal_branch_is_not_the_only_route_pinned(tmp_path: Path) -> None:
    """A guard on the guard: the case table has to cover the shape this file exists for.

    Without this, deleting the proposal cases would leave the behavioural test green over the
    classifier that mislabelled #4251 — the failure mode `test_the_classifier_routes_what_it_says_
    it_routes` is about, one level up.
    """
    classes = {case["expect_classification"] for case in _cases()}
    assert {"proposal", "lesson-candidate", "question"} <= classes, (
        f"the case table no longer covers every route (has {sorted(classes)}); the proposal route "
        "was added because #4251 was mislabelled — keep a case for each class"
    )
