#!/usr/bin/env python3
"""One test per shape predicate, each with the negative fixture it must not fire on.

The negative half is the point. Every rule here reports *shape*, not correctness, and a shape rule that
fires on legitimate work is worse than no rule: it teaches contributors to ignore the guard. So each
predicate below is checked against a real contribution from this repository's history that looks similar
and must stay clean.

The fixtures are the shapes measured in #2066 (2026-09-22) and in the four PRs triaged on 2026-09-26/27:
root `ai_solution.py`, `solutions/issue_2283_solution.ts`, and the `pyproject.toml` rewrite that dropped
`[build-system]` + `[project]`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.pr_shape_guard import (  # noqa: E402
    _mask_inner,
    findings,
    linked_issues,
    mentions_issues,
    packaging_damage,
    question_bounty_without_a_lesson,
    root_solution_dump,
)

HEALTHY_PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "misakanet"
version = "2.37.0"
dependencies = []
"""

BROKEN_PYPROJECT = """[tool.pytest.ini_options]
testpaths = ["tests"]
"""

QUESTION_BOUNTY_BODY = (
    "<!-- misakanet-question-bounty:anchor-2255 -->\n"
    "# [Bounty] Answer the 2 linked question(s) as a lesson\n\n"
    "## Deliverable\n\nA lesson under `lessons/` that answers the question(s) above."
)


# ── rule 1: a root-level solution dump ────────────────────────────────────────────────────────────

def test_a_root_solution_file_is_flagged_for_a_question_bounty():
    found = root_solution_dump(["ai_solution.py"])
    assert found and "ai_solution.py" in found[0], found
    assert "Deliverable" in found[0], "the finding must point at the artifact the task asks for"
    assert root_solution_dump(["solutions/issue_2283_solution.ts"]), "a new solutions/ dir is the same shape"
    assert root_solution_dump(["solution.py", "test_solution.py"]), "#2061-#2063's shape"


def test_real_contributions_are_not_flagged_as_solution_dumps():
    """The negative fixtures: files that contain the word and are exactly where they belong."""
    for paths in (
        ["scripts/solution_check.py"],          # inside scripts/, not a root dump
        ["lessons/contrib/an-unrelated-solution-to-timeouts.md"],
        ["tests/test_solution_shape.py"],
        ["workers/register-proxy-sw.js", "docs/index.html"],
    ):
        assert root_solution_dump(paths) == [], paths


# ── rule 2: packaging damage ──────────────────────────────────────────────────────────────────────

def test_dropping_the_project_table_is_flagged():
    found = packaging_damage(HEALTHY_PYPROJECT, BROKEN_PYPROJECT)
    assert found, "the #2061-#2063 rewrite must be caught"
    assert "[project]" in found[0] and "[build-system]" in found[0], found


def test_a_real_packaging_change_is_not_flagged():
    """A release bump edits the `[project]` table and keeps it — the rule is about loss, not change."""
    bumped = HEALTHY_PYPROJECT.replace('version = "2.37.0"', 'version = "2.38.0"')
    assert packaging_damage(HEALTHY_PYPROJECT, bumped) == []
    # Adding a dependency, moving a script entry, or a pyproject that never had the table.
    assert packaging_damage(HEALTHY_PYPROJECT, HEALTHY_PYPROJECT + '\n[project.optional-dependencies]\n') == []
    assert packaging_damage(None, BROKEN_PYPROJECT) == [], "no base text means no claim to make"


# ── rule 3: a question bounty with no lesson ──────────────────────────────────────────────────────

def test_a_question_bounty_without_a_lesson_is_flagged():
    found = question_bounty_without_a_lesson(
        ["scripts/check_provenance.py", "tests/test_issue_2283.py"],
        {2283: QUESTION_BOUNTY_BODY}, "Fixes #2283")
    assert found, "2026-09-26: a script patch claimed a lesson task and the lesson gate stayed green"
    assert "#2283" in found[0], found
    assert "lessons/" in found[0], "the finding must name where the deliverable goes"


def test_a_lesson_pr_and_a_code_bounty_are_both_left_alone():
    # The answer to the task, at any depth under the indexed directories.
    assert question_bounty_without_a_lesson(
        ["lessons/contrib/macos-chrome-headless-pdf-supervision.md"], {2283: QUESTION_BOUNTY_BODY},
        "Fixes #2283") == []
    # A *code* bounty (no question marker) is not this rule's business: #2274 asked for a fix to
    # scripts/push_preflight.py and nothing else.
    assert question_bounty_without_a_lesson(
        ["scripts/push_preflight.py"], {2274: "# push_preflight 的判据不区分方向"}, "Fixes #2274") == []
    # A lesson at the repository root of `lessons/` is *not* indexed (INDEXED_DIRS), so it is still a
    # missing deliverable — the failure mode PR #2293 shipped.
    assert question_bounty_without_a_lesson(
        ["lessons/chrome-headless-pdf-macos-supervision.md"], {2283: QUESTION_BOUNTY_BODY}, "Fixes #2283")


def test_linked_issues_reads_the_forms_contributors_actually_use():
    assert linked_issues("Fixes #2283") == [2283]
    assert linked_issues("Closes #2255") == [2255]
    assert linked_issues("resolve issue #2280 - [Bounty] Answer 3 linked question(s)") == [2280]
    assert linked_issues("no issue reference here") == []


def test_a_release_pr_body_that_lists_merged_prs_is_not_a_claim():
    """Measured on #2311 (2026-09-27): the release body lists `… (#2332)`, and #2332's own body quotes
    the bounty marker while explaining the rule — so a bare-number rule reported the release train as
    "claims a question bounty without a lesson", and `audit-shape` went red on the release PR.

    A body that names many numbers and claims none must stay clean, even when one of those numbers is a
    bounty issue.
    """
    release_body = (
        "chore(main): release 2.37.0\n\n"
        "* fix(search): the index froze because it is one row under a hard cap (#2327)\n"
        "* feat(ci): the shape guard now decides the three shapes (#2332)\n"
        "* feat(site): the drawer links the pages that existed (#2328)\n"
        "* Refs #2283\n"
    )
    assert linked_issues(release_body) == [], linked_issues(release_body)
    assert question_bounty_without_a_lesson(
        ["pyproject.toml", "CHANGELOG.md", "workers/register-proxy-sw.js"],
        {2283: QUESTION_BOUNTY_BODY, 2332: "explaining the marker: misakanet-question-bounty"},
        release_body) == [], "the release train must not be reported as a bounty claim"
    # And the lookup helper still sees the mentions, so the workflow can fetch their bodies.
    assert 2283 in mentions_issues(release_body)


# ── rule 3b: a quoted example is not a claim (#3281, §92.7) ───────────────────────────────────────
#
# §92.7: PR #3278 changed only `docs/maintainer/handoff-2026-10-15.md`. Its body quoted, in a code span,
# the line that `pr-agent` had stripped from the rebased PR — and `CLAIMS_ISSUE` read the quote as a
# claim, so #2838's bounty marker made the guard report "claims a question bounty without a lesson"
# against the PR that was documenting the defect. The tests below are the red-bounded half: each names
# one exemption, its raw fixture *must* still be caught (or the guard has been weakened), and the
# explanatory sentence around it must survive with the rest of its claims intact.

_DEFECT_CLAIM = "{verb} #{n}"                    # the line pr-agent strips, as typed
_QUOTED_DEFECT = "`" + _DEFECT_CLAIM + "`"       # the same line quoted in a code span (the #3278 shape)


def test_a_code_span_is_a_quote_not_a_claim_but_the_raw_claim_still_hits():
    """The #3278 shape: the only claim-looking text is *inside* the code span."""
    quoted = f"the body rewrite replaced {_QUOTED_DEFECT.format(verb='Closes', n=2838)}. with a section"
    raw = _DEFECT_CLAIM.format(verb="Closes", n=2838)
    assert linked_issues(raw) == [2838], "the red bound: the unquoted claim must still be caught"
    assert linked_issues(quoted) == [], "a code span is described text, not intent"


def test_a_double_quoted_sentence_is_a_quote_not_a_claim_but_the_raw_claim_still_hits():
    """The same sentence outside a code span, as prose quotes it."""
    quoted = f'the rewrite dropped "{_DEFECT_CLAIM.format(verb="Fixes", n=2838)}." before the merge'
    raw = _DEFECT_CLAIM.format(verb="Fixes", n=2838)
    assert linked_issues(raw) == [2838], "the red bound: the unquoted claim must still be caught"
    assert linked_issues(quoted) == [], "the quoted sentence is described text, not intent"


def test_a_claim_beside_a_quoted_example_is_still_caught():
    """Masking must remove one span, not the line — the failure mode that would be a real weakening.

    A code span and a live claim share the line, and the code span comes first, so a masker that ate the
    rest of the line would silently drop the claim that follows it.
    """
    text = f"{_QUOTED_DEFECT.format(verb='Closes', n=2838)} is what got stripped; this PR closes #2299"
    assert linked_issues(text) == [2299], linked_issues(text)
    # And `mentions_issues()` is deliberately *not* masked: the workflow still has to fetch #2838's body
    # to decide whether it is a question bounty at all.
    assert mentions_issues(text) == [2299, 2838], mentions_issues(text)


def test_a_blockquote_marker_is_a_quote_but_a_quoted_verb_alone_does_not_hide_a_claim():
    """A `>` marker is attribution, not the quoted text — and a quoted word is not a paraphrase."""
    assert linked_issues("> `Closes #2838.`") == [], "a blockquote's quoted example is a quote"
    assert linked_issues("> Closes #2838") == [2838], "the red bound: the text itself still counts"
    # Only a quoted span that *states* a claim is masked; quoting the verb alone must not swallow a
    # claim that is typed outside the quotes.
    text = '"Fixes" is the word the guard matches; this PR closes #2283'
    assert linked_issues(text) == [2283], linked_issues(text)


def test_the_documenting_pr_from_92_7_is_clean_and_the_bounty_rule_agrees():
    """The end-to-end shape: a docs-only PR that explains the defect, against a bounty-marked issue.

    `pr-agent` generated the second occurrence as a mermaid diagram that reproduced the matching token,
    so the fenced case is not hypothetical either.
    """
    body = (
        "### What changed\n\n"
        "`docs/maintainer/handoff-2026-10-15.md` only.\n\n"
        "## Why\n\n"
        "`pr-agent` rewrites every body and strips the original closing keyword: the rebased PR's body "
        f"had {_QUOTED_DEFECT.format(verb='Closes', n=2838)} and now has a generated section.\n\n"
        "```mermaid\n"
        f'flowchart TD\n  A["PR body quotes {_QUOTED_DEFECT.format(verb="Closes", n=2838)} in a code span\n'
        "```\n"
    )
    assert linked_issues(body) == [], linked_issues(body)
    for paths in (["docs/maintainer/handoff-2026-10-15.md"], []):
        assert question_bounty_without_a_lesson(paths, {2838: QUESTION_BOUNTY_BODY}, body) == [], paths
    # The red bound: the same body with the sentence typed as a claim *is* a claim. Without this the
    # first assertion could pass because the rule stopped working altogether.
    assert linked_issues(f"Fixes #{2838}") == [2838]


def test_mask_inner_masks_without_moving_anything():
    """Masked, never deleted: a claim after a quote keeps its own span, and nothing shifts position."""
    text = f"explain {_QUOTED_DEFECT.format(verb='Closes', n=2838)} then Fixes #2299"
    masked = _mask_inner(text)
    assert len(masked) == len(text), "masking must preserve offsets, not delete text"
    assert masked.endswith("then Fixes #2299"), masked
    assert "#2838" not in masked and "#2299" in masked, masked


# ── the aggregation, and the CLI the workflow calls ───────────────────────────────────────────────

def test_findings_aggregates_every_rule_without_repeating_itself():
    both = findings(paths=["ai_solution.py"], pr_text="Fixes #2283",
                    base_pyproject=HEALTHY_PYPROJECT, head_pyproject=BROKEN_PYPROJECT,
                    issue_bodies={2283: QUESTION_BOUNTY_BODY})
    assert len(both) == 3, both
    assert findings(paths=["lessons/contrib/x.md"], pr_text="Fixes #2283",
                    base_pyproject=HEALTHY_PYPROJECT, head_pyproject=HEALTHY_PYPROJECT,
                    issue_bodies={2283: QUESTION_BOUNTY_BODY}) == []


def test_the_cli_prints_json_for_the_workflow(tmp_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("ai_solution.py\npyproject.toml\n", encoding="utf-8")
    body = tmp_path / "body.txt"
    body.write_text("Fixes #2283", encoding="utf-8")
    base = tmp_path / "base.toml"
    base.write_text(HEALTHY_PYPROJECT, encoding="utf-8")
    head = tmp_path / "head.toml"
    head.write_text(BROKEN_PYPROJECT, encoding="utf-8")
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps({"2283": QUESTION_BOUNTY_BODY}), encoding="utf-8")

    proc = subprocess.run([sys.executable, str(REPO / "scripts" / "pr_shape_guard.py"),
                           "--changed-files", str(changed), "--pr-body", str(body),
                           "--base-pyproject", str(base), "--head-pyproject", str(head),
                           "--issue-bodies", str(issues)],
                          capture_output=True, text=True, cwd=REPO)
    assert proc.returncode == 0, (
        f"the guard must never fail the step on its own — the workflow decides what to do with the "
        f"findings; exit {proc.returncode}: {proc.stderr[-300:]}"
    )
    parsed = json.loads(proc.stdout)
    assert len(parsed) == 3, parsed
    assert all(isinstance(item, str) and item.strip() for item in parsed), parsed


def test_the_workflow_runs_this_module_and_merges_its_findings():
    """A predicate nobody runs is a comment. The wiring is asserted, not remembered."""
    text = (REPO / ".github" / "workflows" / "pr-shape-guard.yml").read_text(encoding="utf-8")
    assert "scripts/pr_shape_guard.py" in text, "the workflow does not run the predicates"
    assert "findings.json" in text, "the workflow does not collect the predicate output"
    assert "pull_request_target" in text, (
        "the guard must run on the trusted base, never checking out the PR's code"
    )


def test_the_claim_forms_the_2026_09_26_prs_actually_used():
    """Real titles from the four PRs triaged that night, each classified the way a reviewer would.

    The guard's job is to fire on the ones that claimed a lesson task and delivered something else — not
    on the ones that merely mention a number. A guard that cannot tell these apart false-positives on the
    release train (which is exactly what happened to #2311 minutes after this rule shipped).
    """
    claims = {
        "fix: solve issue #2283 - [Bounty] Answer 2 linked question(s) as a lesson": [2283],
        "fix(MisakaNet): resolve issue #2283 - [Bounty] Answer 2 linked question(s) as a lesson": [2283],
        "AI Agent Fix for Issue #2283": [2283],
        "Fixes #2283": [2283],
        "Closes #2255": [2255],
    }
    for text, expected in claims.items():
        assert linked_issues(text) == expected, (text, linked_issues(text))

    mentions_only = [
        "chore(main): release 2.37.0\n* fix(search): the index froze (#2327)\n* feat(ci): the guard (#2332)\n* Refs #2283",
        "Related to #2283",
        "[Draft] [Bounty] Answer 2 linked question(s) as a lesson",
        "fix: bump (#2332)",
    ]
    for text in mentions_only:
        assert linked_issues(text) == [], (text, linked_issues(text))
