#!/usr/bin/env python3
"""The bounty-claim guard must be able to say "no" — and must not say it to a clean PR (issue #2043).

`scripts/bounty_claim.py` decides four things about an incoming PR, and every one of them is pinned
here in both directions:

* **a clean PR is `ok` and is never commented on.** A guard that fires on honest contributions is how
  the queue noise it was written to remove gets *added to* — so the false-positive direction is a test,
  not a hope (`test_a_clean_pr_is_ok_and_the_guard_says_nothing`);
* **each non-`ok` verdict has a receipt that says what to do next** (``**回主线的路**``). This
  repository's receipts on #1959/#1960/#1961 all end with a concrete route and the maintainer treats
  one without it as incomplete, so the rule is asserted for *every* verdict, including verdicts added
  later;
* **each rule is load-bearing.** Removing a rule from `RULES` must change a verdict, which is what
  "can it go red?" means here — the same idiom as `tests/test_workflow_inventory.py`. Nothing is
  edited on disk to check it: `decide_with()` takes the rule list as an argument.
* **the workflow that carries the guard cannot block a contributor**, has no `paths:` filter (a
  filtered run reports nothing and leaves PRs at "Expected — waiting for status" forever, #1920), and
  updates its own receipt instead of posting a new one on every `edited` event.

The CLI half (`main`, `gather_facts`, `upsert_receipt`) is deliberately never executed here: it talks
to the GitHub API. What it *decides* — which comment to update, which PR is a rival — is pure code and
is tested directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import bounty_claim as bc  # noqa: E402  (path set up above, on purpose)

WORKFLOW = REPO / ".github" / "workflows" / "bounty-claim-guard.yml"

RIVAL = bc.CompetingPullRequest(number=1959, author="early-agent", title="gemini recipe",
                                created_at="2026-09-20T16:00:00Z", body="fixes #1942")
LATER = bc.CompetingPullRequest(number=1980, author="late-agent", title="gemini recipe again",
                                created_at="2026-09-21T09:00:00Z", body="Fixes #1942")


def clean_facts(**overrides) -> bc.PullRequestFacts:
    """A well-formed PR: it names an issue, the issue is open and unsatisfied, nobody else is on it."""
    base = dict(number=2043, author="honest-agent", created_at="2026-09-22T10:00:00Z",
                body="fix: enforce one-PR-per-issue for bounties\n\nFixes #2042\n",
                issue_number=None, issue_state="open")
    base.update(overrides)
    return bc.PullRequestFacts(**base)


# One facts → expected verdict case per verdict, plus the near-misses that must NOT produce them. The
# rule-load-bearing test below runs over this table, so a verdict with no case here is a hole.
CASES: dict[str, tuple[bc.PullRequestFacts, str]] = {
    "clean pr": (clean_facts(), bc.VERDICT_OK),
    "no reference": (clean_facts(body="just a patch, no issue named anywhere"), bc.VERDICT_NO_ISSUE_REFERENCE),
    "reference only inside a fence": (clean_facts(body="```\nFixes #1942\n```\n"), bc.VERDICT_NO_ISSUE_REFERENCE),
    "satisfied by a merged pr": (clean_facts(body="Fixes #1942", satisfied_by=("PR #1969（已合并）",)),
                                 bc.VERDICT_ISSUE_ALREADY_SATISFIED),
    "issue closed with no evidence": (clean_facts(body="Fixes #1942", issue_state="closed"),
                                      bc.VERDICT_ISSUE_ALREADY_SATISFIED),
    "competing pr": (clean_facts(body="Fixes #1942", competing_prs=(RIVAL,)),
                     bc.VERDICT_COMPETING_PR_EXISTS),
}


def without(*names: str):
    return tuple(rule for rule in bc.RULES if rule.__name__ not in names)


# ── the false-positive direction: nothing must be said to a clean PR ─────────────────────────────


def test_a_clean_pr_is_ok_and_the_guard_says_nothing():
    """The one verdict that must never comment: a body that names an issue, no rival, issue open."""
    decision = bc.decide(clean_facts())
    assert decision.verdict == bc.VERDICT_OK
    assert decision.issue == 2042, "the referenced issue must be read off the body"
    assert decision.comment is None, (
        "a clean PR must not be commented on — a guard that talks to honest contributors is noise")


def test_the_ok_verdict_cannot_carry_a_comment_by_construction():
    """The invariant, so a future rule cannot make `ok` chatty without this failing."""
    with pytest.raises(ValueError, match="must not be commented on"):
        bc.Decision(bc.VERDICT_OK, 1, "reason", comment="hello")


def test_every_other_verdict_must_carry_a_receipt_by_construction():
    with pytest.raises(ValueError, match="must carry the receipt"):
        bc.Decision(bc.VERDICT_COMPETING_PR_EXISTS, 1, "reason", comment=None)


def test_an_unknown_verdict_is_rejected():
    with pytest.raises(ValueError, match="unknown verdict"):
        bc.Decision("looks_fine_to_me", 1, "reason", comment="x")


# ── verdict 1: the body names no issue ───────────────────────────────────────────────────────────


def test_a_body_with_no_reference_gets_the_no_issue_reference_verdict():
    decision = bc.decide(clean_facts(body="## Summary\n\n- add the guard\n\n### Testing\n\n- none"))
    assert decision.verdict == bc.VERDICT_NO_ISSUE_REFERENCE
    assert decision.issue is None


def test_the_no_issue_reference_receipt_teaches_the_reference_forms():
    comment = bc.decide(clean_facts(body="no issue here")).comment
    assert "Fixes #1234" in comment, "the receipt must show the exact thing to add"
    assert "/claim #1234" in comment, "Opire's claim form is what makes claim and work line up"
    assert "<!--" in comment and "代码块" in comment, (
        "the receipt must cover the author whose reference is real but fenced/commented")


def test_a_reference_only_inside_a_fenced_block_is_a_quotation_not_a_claim():
    """The scars: PR bodies here have been whole agent transcripts, full of `#NNNN`."""
    transcript = ("Let me start by exploring the repository structure…\n\n```\n"
                  "$ gh issue view 1942\nfixes #1942\n```\n")
    assert bc.reference_issue(transcript) is None
    assert bc.decide(clean_facts(body=transcript)).verdict == bc.VERDICT_NO_ISSUE_REFERENCE


def test_a_reference_hidden_in_an_html_comment_is_invisible_so_it_does_not_count():
    assert bc.reference_issue("chore: tidy up\n\n<!-- fixes #1942 -->\n") is None


def test_a_reference_in_the_prose_of_a_body_with_a_transcript_still_counts():
    """The reverse direction: a real reference next to a fenced block must not be swallowed."""
    body = "Fixes #1942\n\n```\n$ gh issue view 9999\n```\n"
    assert bc.reference_issue(body) == 1942


def test_the_closing_keyword_beats_a_bare_mention():
    """\"related to #1941 … Fixes #1942\" claims #1942; a receipt about #1941 is a wrong receipt."""
    assert bc.reference_issue("Related to #1941.\n\nFixes #1942\n") == 1942
    assert bc.reference_issue("Fixes #1942.\n\nSee also #1941\n") == 1942


def test_the_opire_claim_form_is_a_reference():
    assert bc.reference_issue("## Summary\n\n/claim #1942\n") == 1942
    assert bc.reference_issue("Closes #1942.") == 1942
    assert bc.reference_issue("Resolves: owner/repo#1942") == 1942


def test_a_markdown_heading_is_not_an_issue_reference():
    assert bc.reference_issue("## 1942 was fixed already\n") is None
    assert bc.reference_issue("### Testing\n\n- pytest\n") is None


def test_the_reference_parser_agrees_with_the_one_pr_genius_report_uses():
    """One question, one answer: the same bodies must resolve to the same number in both parsers."""
    from scripts.pr_genius_report import ISSUE_REFERENCE

    for body in ("Fixes #1942", "closes #7", "related to #1941", "fixed owner/repo#1234", "no refs"):
        theirs = ISSUE_REFERENCE.search(body)
        mine = bc.reference_issue(body)
        assert (int(theirs.group().rsplit("#", 1)[1]) if theirs else None) == mine, body


# ── verdict 2: merged work already satisfies the issue ───────────────────────────────────────────


def test_merged_work_already_satisfying_the_issue_names_the_evidence():
    decision = bc.decide(clean_facts(body="Fixes #1942",
                                     satisfied_by=("PR #1969（已合并）", "`lessons/x.md`（已引用 intake #1942）")))
    assert decision.verdict == bc.VERDICT_ISSUE_ALREADY_SATISFIED
    assert "PR #1969（已合并）" in decision.comment
    assert "lessons/x.md" in decision.comment, "the receipt must name what is already on main"


def test_a_closed_issue_is_already_satisfied_and_the_receipt_admits_what_it_does_not_know():
    decision = bc.decide(clean_facts(body="Fixes #1942", issue_state="closed"))
    assert decision.verdict == bc.VERDICT_ISSUE_ALREADY_SATISFIED
    assert "关闭" in decision.comment
    assert "先在上面问一句" in decision.comment, "no evidence means ask, not guess"


def test_an_unknown_issue_state_is_not_treated_as_closed():
    """A failed fetch must not invent "the issue is done" — that verdict stops somebody's work."""
    decision = bc.decide(clean_facts(body="Fixes #1942", issue_state=""))
    assert decision.verdict == bc.VERDICT_OK


def test_satisfied_beats_a_competing_pr():
    """The 2026-09-21 case exactly: three PRs on #1942, and the useful sentence is "it is done"."""
    decision = bc.decide(clean_facts(body="Fixes #1942", satisfied_by=("PR #1969（已合并）",),
                                     competing_prs=(RIVAL, LATER)))
    assert decision.verdict == bc.VERDICT_ISSUE_ALREADY_SATISFIED


# ── verdict 3: another open PR claims the same issue ─────────────────────────────────────────────


def test_a_competing_pr_produces_the_coordination_receipt():
    decision = bc.decide(clean_facts(body="Fixes #1942", competing_prs=(RIVAL,)))
    assert decision.verdict == bc.VERDICT_COMPETING_PR_EXISTS
    assert "#1959" in decision.comment
    assert "early-agent" in decision.comment, "the author must be able to find who to talk to"


def test_the_pr_is_not_its_own_competitor():
    """The guard re-runs on every edit; a PR that reports itself would argue with its own author."""
    mine = bc.CompetingPullRequest(number=2043, author="honest-agent", created_at="2026-09-22T10:00:00Z",
                                   body="Fixes #1942")
    assert bc.decide(clean_facts(body="Fixes #1942", competing_prs=(mine,))).verdict == bc.VERDICT_OK
    assert bc.competitors(clean_facts(body="Fixes #1942", competing_prs=(mine,)), 1942) == []


def test_a_pr_that_names_a_different_issue_is_not_a_competitor():
    """"Another PR is open" is not "another PR is working on #1942"."""
    other = bc.CompetingPullRequest(number=1960, author="someone", body="Fixes #1941")
    assert bc.decide(clean_facts(body="Fixes #1942", competing_prs=(other,))).verdict == bc.VERDICT_OK


def test_the_earliest_competitor_is_named_whatever_order_the_api_returns():
    facts = clean_facts(body="Fixes #1942", competing_prs=(LATER, RIVAL))
    decision = bc.decide(facts)
    assert decision.verdict == bc.VERDICT_COMPETING_PR_EXISTS
    assert f"#{RIVAL.number}" in decision.comment.split("**回主线的路**")[0], (
        "the receipt must point at whoever arrived first, not at whatever the API listed first")


def test_the_later_author_is_told_to_join_the_earlier_pr():
    facts = clean_facts(created_at="2026-09-22T10:00:00Z", body="Fixes #1942", competing_prs=(RIVAL,))
    comment = bc.decide(facts).comment
    assert "比你先到" in comment
    assert "去 #1959 下面留言" in comment


def test_the_earlier_author_is_not_told_to_join_the_later_pr():
    """The rule is first-come, so the wording must flip — a receipt that reverses it loses the bounty
    for whoever did the work first."""
    facts = clean_facts(created_at="2026-09-19T08:00:00Z", body="Fixes #1942", competing_prs=(LATER,))
    comment = bc.decide(facts).comment
    assert "你才是先到的" in comment
    assert "去 #1980 下面留言" not in comment
    assert "请对方把独有内容并到**你**这条上" in comment


def test_unknown_timestamps_do_not_invent_an_ordering():
    facts = clean_facts(created_at="", body="Fixes #1942", competing_prs=(RIVAL,))
    comment = bc.decide(facts).comment
    assert "无法比较先后" in comment
    assert "你才是先到的" not in comment


def test_a_vetted_rival_without_a_body_is_still_a_rival():
    """The caller may have filtered already; the pure core must accept that cheap path."""
    vetted = bc.CompetingPullRequest(number=1959, author="early-agent")
    assert bc.decide(clean_facts(body="Fixes #1942", competing_prs=(vetted,))).verdict == \
        bc.VERDICT_COMPETING_PR_EXISTS


# ── every verdict: a case, and a receipt with a path back ────────────────────────────────────────


def test_every_verdict_has_at_least_one_case():
    """Guard the guard: a verdict nobody can produce is a verdict nobody has tested."""
    produced = {bc.decide(facts).verdict for facts, _ in CASES.values()}
    assert produced == set(bc.VERDICTS), f"untested verdicts: {sorted(set(bc.VERDICTS) - produced)}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_case_produces_its_expected_verdict(name):
    facts, expected = CASES[name]
    assert bc.decide(facts).verdict == expected


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_non_ok_receipt_carries_the_marker_and_the_path_back(name):
    facts, expected = CASES[name]
    decision = bc.decide(facts)
    if decision.verdict == bc.VERDICT_OK:
        assert decision.comment is None
        return
    assert decision.comment.startswith(bc.MARKER), (
        "the marker is what makes the workflow idempotent — without it every edit posts again")
    assert "**回主线的路**" in decision.comment, (
        "a receipt without a route back is incomplete (the maintainer's #1959/#1960/#1961 receipts "
        "all end with one)")
    assert decision.comment.index("**回主线的路**") > 100, "the route must be a section, not a word"


def test_the_path_back_rule_catches_a_receipt_without_one():
    """The rule above must be able to fail, or it is decoration."""
    comment = bc.decide(clean_facts(body="no issue here")).comment
    gutted = comment.replace("**回主线的路**", "**更多信息**")
    assert gutted != comment and "**回主线的路**" not in gutted


def test_the_marker_rule_catches_a_receipt_without_one():
    comment = bc.decide(clean_facts(body="no issue here")).comment
    assert not comment.replace(bc.MARKER, "").startswith(bc.MARKER)


# ── the rules are load-bearing: removing one must change a verdict ───────────────────────────────


@pytest.mark.parametrize("rule", [rule.__name__ for rule in bc.RULES])
def test_each_rule_is_load_bearing(rule):
    reduced = without(rule)
    changed = {name for name, (facts, expected) in CASES.items()
               if bc.decide_with(reduced, facts).verdict != expected}
    assert changed, (
        f"removing {rule}() changed no verdict in {sorted(CASES)} — a rule nothing depends on is not "
        "a rule, and the guard would look green while doing nothing")


def test_removing_the_no_reference_rule_lets_a_body_with_no_issue_through_as_ok():
    facts = CASES["no reference"][0]
    assert bc.decide_with(without("rule_no_issue_reference"), facts).verdict == bc.VERDICT_OK
    assert bc.decide_with(without("rule_no_issue_reference"), facts).comment is None


def test_removing_the_satisfied_rule_lets_work_on_a_done_issue_through():
    """The #1942 case: without this rule the three duplicate PRs get no receipt at all."""
    facts = CASES["satisfied by a merged pr"][0]
    assert bc.decide_with(without("rule_issue_already_satisfied"), facts).verdict == bc.VERDICT_OK


def test_removing_the_competing_rule_lets_a_second_pr_on_the_same_issue_through():
    facts = CASES["competing pr"][0]
    assert bc.decide_with(without("rule_competing_pr_exists"), facts).verdict == bc.VERDICT_OK


def test_the_rules_are_applied_in_precedence_order():
    """Satisfied above competing is the ordering the 2026-09-21 case needed, not an accident."""
    assert [rule.__name__ for rule in bc.RULES] == [
        "rule_no_issue_reference", "rule_issue_already_satisfied", "rule_competing_pr_exists"]


def test_the_issue_number_in_the_facts_wins_over_the_body():
    """A caller that already resolved the reference must not be second-guessed by a re-parse."""
    facts = clean_facts(body="Fixes #1942", issue_number=1942)
    assert bc.decide(facts).issue == 1942
    assert bc.decide(clean_facts(body="Fixes #1942", issue_number=2042)).issue == 2042


# ── idempotency is a decision, not an HTTP detail ────────────────────────────────────────────────


def test_the_receipt_is_updated_when_the_guard_has_already_spoken():
    posted = [{"id": 11, "body": "thanks!"},
              {"id": 12, "body": f"{bc.MARKER}\n### old receipt\n"}]
    assert bc.receipt_action(posted) == ("update", 12), (
        "an `edited` event must refresh the receipt, not leave a second one on the PR")


def test_the_first_receipt_is_created():
    assert bc.receipt_action([]) == ("create", None)
    assert bc.receipt_action([{"id": 11, "body": "thanks!"}, {"id": 13, "body": None}]) == ("create", None)


def test_a_body_that_merely_mentions_this_guard_is_a_marker_sighting_only_for_the_marker():
    """The marker is exact: 'bounty-claim-guard' in prose must not be mistaken for the receipt."""
    prose = [{"id": 14, "body": "I think bounty-claim-guard should not comment here"}]
    assert bc.receipt_action(prose) == ("create", None)


# ── the workflow: a comment is the whole action, and it must not lie by omission ─────────────────


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_workflow_runs_when_a_pr_is_opened_or_its_body_is_edited():
    text = workflow_text()
    assert "pull_request:" in text, "the guard is triggered by the PR event"
    assert "types: [opened, edited]" in text, (
        "a body that gains or loses its issue reference must be re-decided — `edited` is the event "
        "that makes the no_issue_reference receipt actionable")


def test_the_workflow_has_no_paths_filter():
    """#1920's scar: a filtered workflow reports *nothing* for the PRs it skips, and GitHub then holds
    them at "Expected — waiting for status to be reported" forever."""
    text = workflow_text()
    assert "\n    paths:" not in text and "\n    paths-ignore:" not in text
    assert "\n  paths:" not in text and "\n  paths-ignore:" not in text


def test_the_comment_step_cannot_fail_the_pull_request():
    """The governance rule is a receipt, not a gate: blocking a contributor on it (or on this
    workflow's own bugs) is how the queue noise gets worse instead of better."""
    text = workflow_text()
    step = text.split("id: guard", 1)[1]
    assert "continue-on-error: true" in step, (
        "the step that can fail must be non-blocking; the job stays green so the PR is never held")
    assert "core.setFailed" not in text and "exit 1" not in text


def test_the_workflow_runs_the_cli_with_posting_enabled():
    text = workflow_text()
    assert "python3 scripts/bounty_claim.py" in text
    assert "--post" in text, "without it the guard decides and says nothing"
    assert "--verdict-file" in text, "the verdict has to reach the run summary, not just a log line"


def test_the_trigger_is_the_one_2043_asked_for_and_the_fork_limitation_is_written_down():
    """Two things at once, because they are the same decision: the workflow runs on `pull_request`,
    and on a fork PR that means a read-only token, so the receipt can be rejected with 403 — the
    failure mode that once made a whole class of receipts in this repository fail invisibly. The
    limitation and the one-word alternative are written in the file, so the next person reads a
    decision instead of discovering it from a silent green run."""
    text = workflow_text()
    assert "\n  pull_request_target:" not in text
    assert "types: [opened, edited]" in text
    assert "read-only token" in text and "403" in text


def test_no_code_from_the_pull_request_is_ever_used():
    """Nothing from the head is checked out or run: the body and the issue are read over the API."""
    text = workflow_text()
    assert "github.event.pull_request.head" not in text
    assert "scripts/bounty_claim.py" in text, "the only code this job runs is this repository's own"


def test_the_workflow_uses_pinned_actions():
    text = workflow_text()
    uses = [line.split("uses:", 1)[1].strip() for line in text.splitlines() if "uses:" in line]
    assert uses, "the workflow must do something"
    for target in uses:
        name, _, ref = target.partition("@")
        assert len(ref.split()[0]) == 40, f"{name} is not pinned to a commit sha: {target}"
