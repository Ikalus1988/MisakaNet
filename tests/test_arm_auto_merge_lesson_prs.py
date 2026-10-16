#!/usr/bin/env python3
"""The sweep that arms the lesson auto-merge channel must not arm anything the channel refuses.

Why this file exists (2026-10-17)
---------------------------------
`auto-merge-lessons.yml` is opt-in by label and **nothing applied the label**, so lesson pull
requests piled up at `auto-merge-lessons = skipping` while a human merged each one. The label
cannot be applied at PR-creation time: the channel fires on `labeled` / `synchronize` /
`ready_for_review` — not `opened` — and it no longer listens to `check_suite`, so its own
documentation records that a PR armed *before* its checks finish waits forever. Arming therefore
belongs after the conditions hold, which is what the scheduled sweep
(`scripts/arm_auto_merge_lesson_prs.py`, run from `auto-sync-prs.yml`) does.

Two things have to be true, and both are pinned here as functions of the source rather than as
prose (a rule that cannot be shown to fail is a comment, not a gate):

* the sweep asks the channel's **own** judge whether the PR would merge the moment it carried the
  label, so the two can never disagree about what "mergeable" means; and
* the sweep only considers PRs whose head branch lives in this repository — an external
  contributor's fork PR stays opt-in by hand, which is the owner's stated boundary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import arm_auto_merge_lesson_prs as sweep  # noqa: E402
from lesson_pr_mergeable import OPT_IN_LABEL, decide  # noqa: E402

WORKFLOW = REPO / ".github" / "workflows" / "auto-sync-prs.yml"

REPO_SLUG = "Ikalus1988/MisakaNet"


def a_pr(**over) -> dict:
    pr = {
        "number": 3344,
        "author_association": "COLLABORATOR",
        "draft": False,
        "head": {"sha": "a" * 40, "ref": "lesson/x", "repo": {"full_name": REPO_SLUG}},
        "base": {"ref": "main"},
        "labels": [],
        "body": "",
    }
    pr.update(over)
    return pr


def a_check(name: str, conclusion: str, started: str = "2026-10-17T10:00:00Z") -> dict:
    return {"name": name, "conclusion": conclusion, "started_at": started}


GREEN_CHECKS = [
    a_check("gate", "success"),
    a_check("provenance", "success"),
    a_check("dco", "success"),
    a_check("audit-shape", "success"),
    a_check("test (ubuntu-latest, 3.11)", "success"),
]
LESSON_FILES = [{"filename": "lessons/contrib/x.md", "additions": 60, "deletions": 0}]


# ── who may be swept ────────────────────────────────────────────────────────
class TestCandidateScope:
    @pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
    def test_a_same_repo_pr_from_a_writer_is_a_candidate(self, association):
        assert sweep.candidate_skip_reason(a_pr(author_association=association), REPO_SLUG) is None

    def test_a_fork_pr_stays_opt_in_by_hand(self):
        fork = a_pr(head={"sha": "b" * 40, "ref": "lesson/x",
                          "repo": {"full_name": "someone/MisakaNet"}})
        reason = sweep.candidate_skip_reason(fork, REPO_SLUG)
        assert reason and "external contributors" in reason, reason

    @pytest.mark.parametrize("association", ["CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", "NONE", ""])
    def test_an_untrusted_author_association_is_skipped(self, association):
        """Belt and braces: a same-repo branch already implies write access, but the sweep states
        the association it accepted so a change on either side is visible."""
        reason = sweep.candidate_skip_reason(a_pr(author_association=association), REPO_SLUG)
        assert reason and "opt-in by hand" in reason, reason

    def test_a_draft_or_a_non_main_base_is_skipped(self):
        assert "draft" in sweep.candidate_skip_reason(a_pr(draft=True), REPO_SLUG)
        assert "not main" in sweep.candidate_skip_reason(a_pr(base={"ref": "release"}), REPO_SLUG)


# ── the facts are read the way the channel reads them ───────────────────────
class TestPayloadAssembly:
    def test_the_newest_run_of_a_check_name_wins(self):
        """A re-run adds a second run under the same name; an older failure must not outvote it.

        `auto-merge-lessons.yml` sorts by `started_at` for exactly this reason. Reading it
        differently here would arm a PR the channel then refuses — a label that promises a merge
        that never comes.
        """
        runs = [a_check("gate", "failure", "2026-10-17T09:00:00Z"),
                a_check("gate", "success", "2026-10-17T11:00:00Z")]
        payload = sweep.build_payload(a_pr(), LESSON_FILES, runs, [])
        assert payload["checks"]["gate"] == "success"

    def test_the_latest_review_per_author_decides(self):
        reviews = [
            {"state": "CHANGES_REQUESTED", "submitted_at": "2026-10-17T09:00:00Z",
             "user": {"login": "alice"}},
            {"state": "APPROVED", "submitted_at": "2026-10-17T10:00:00Z",
             "user": {"login": "alice"}},
        ]
        assert sweep.build_payload(a_pr(), LESSON_FILES, GREEN_CHECKS, reviews)["review_state"] == "APPROVED"

    def test_a_later_changes_requested_blocks(self):
        reviews = [
            {"state": "APPROVED", "submitted_at": "2026-10-17T09:00:00Z", "user": {"login": "a"}},
            {"state": "CHANGES_REQUESTED", "submitted_at": "2026-10-17T10:00:00Z",
             "user": {"login": "b"}},
        ]
        assert sweep.build_payload(a_pr(), LESSON_FILES, GREEN_CHECKS,
                                   reviews)["review_state"] == "CHANGES_REQUESTED"

    def test_dismissed_reviews_are_ignored_and_no_review_is_none(self):
        reviews = [{"state": "DISMISSED", "submitted_at": "2026-10-17T09:00:00Z",
                    "user": {"login": "a"}}]
        assert sweep.build_payload(a_pr(), LESSON_FILES, GREEN_CHECKS, reviews)["review_state"] == "NONE"

    def test_line_stats_and_the_simulated_label(self):
        payload = sweep.build_payload(a_pr(), LESSON_FILES, GREEN_CHECKS, [])
        assert payload["file_stats"] == {"lessons/contrib/x.md": [60, 0]}
        assert OPT_IN_LABEL in payload["labels"]


# ── the decision, and the invariant that makes it safe ──────────────────────
class TestArmingDecision:
    def test_a_green_lessons_only_pr_is_armed(self):
        arm, reason = sweep.arming_decision(a_pr(), LESSON_FILES, GREEN_CHECKS, [])
        assert arm, reason
        assert "would merge" in reason

    @pytest.mark.parametrize("runs,expected", [
        ([a_check("gate", "in_progress")], "wait"),
        # The failure is the *newest* run of `gate`, which is the reading the channel uses.
        ([a_check("gate", "failure", "2026-10-17T12:00:00Z")] + GREEN_CHECKS, "refuse"),
        ([], "wait"),
    ])
    def test_a_pr_the_channel_would_not_merge_is_not_armed(self, runs, expected):
        arm, reason = sweep.arming_decision(a_pr(), LESSON_FILES, runs, [])
        assert not arm, reason
        assert expected in reason, reason

    def test_a_file_outside_lessons_is_not_armed(self):
        files = LESSON_FILES + [{"filename": "scripts/lesson_gate.py", "additions": 3, "deletions": 1}]
        arm, reason = sweep.arming_decision(a_pr(), files, GREEN_CHECKS, [])
        assert not arm and "refuse" in reason, reason

    def test_a_deny_list_label_is_not_armed(self):
        arm, reason = sweep.arming_decision(a_pr(labels=[{"name": "wip"}]), LESSON_FILES,
                                            GREEN_CHECKS, [])
        assert not arm and "deny-list" in reason, reason

    def test_an_already_labelled_pr_is_not_re_armed(self):
        """Adding a label that is already there raises no `labeled` event: a no-op that reads
        like an action, and the channel would never be woken by it."""
        arm, reason = sweep.arming_decision(a_pr(labels=[{"name": OPT_IN_LABEL}]), LESSON_FILES,
                                            GREEN_CHECKS, [])
        assert not arm and "already carries" in reason, reason

    def test_arming_means_the_label_is_the_only_thing_missing(self):
        """The invariant the whole design rests on, stated as an equality rather than a hope.

        For every case the sweep arms, the channel's own judge must (a) say *wait* with only the
        label absent, and (b) say *merge* with it present. If (a) ever fails, the sweep is arming
        a PR for a reason other than "the label is missing" — and a label that does not change the
        verdict is a label that merges nothing.
        """
        cases = [
            (a_pr(), LESSON_FILES, GREEN_CHECKS, []),
            (a_pr(), LESSON_FILES, GREEN_CHECKS,
             [{"state": "APPROVED", "submitted_at": "2026-10-17T10:00:00Z", "user": {"login": "a"}}]),
        ]
        for pr, files, runs, reviews in cases:
            arm, reason = sweep.arming_decision(pr, files, runs, reviews)
            assert arm, reason
            payload = sweep.build_payload(pr, files, runs, reviews, assume_label=False)
            without, why_without = decide(files=payload["files"], checks=payload["checks"],
                                          labels=payload["labels"], draft=payload["draft"],
                                          review_state=payload["review_state"],
                                          file_stats=payload["file_stats"])
            assert without == "wait" and "not present" in why_without, why_without
            with_label = sweep.build_payload(pr, files, runs, reviews)
            with_verdict, why = decide(files=with_label["files"], checks=with_label["checks"],
                                       labels=with_label["labels"], draft=with_label["draft"],
                                       review_state=with_label["review_state"],
                                       file_stats=with_label["file_stats"])
            assert with_verdict == "merge", why


# ── the workflow that runs the sweep ────────────────────────────────────────
def source(path: Path | None = None) -> str:
    return (path or WORKFLOW).read_text(encoding="utf-8")


def arming_problems(text: str) -> list[str]:
    """Rules a reader of the workflow can check without running it. Each is a named failure."""
    import yaml

    problems: list[str] = []
    spec = yaml.safe_load(text)
    jobs = (spec or {}).get("jobs") or {}
    job = jobs.get("arm-lesson-auto-merge")
    if not job:
        problems.append("no `arm-lesson-auto-merge` job: nothing arms the channel, so every lesson "
                        "PR still waits for a human")
        return problems
    if job.get("needs") != "sync":
        problems.append("the arming job does not run after the sync: arming first and re-heading "
                        "the branch afterwards races the channel against a head that is about to move")
    steps = job.get("steps") or []
    checkout = next((s for s in steps if str((s.get("with") or {}) or "").find("fetch-depth") >= 0
                     or s.get("uses", "").startswith("actions/checkout")), None)
    if checkout is None:
        problems.append("the arming job does not check out anything")
    elif (checkout.get("with") or {}).get("ref"):
        problems.append("the arming job checks out an explicit ref — it must run the default "
                        "branch's copy of the script, never a pull request's")
    env = next((s.get("env") or {} for s in steps if "arm_auto_merge_lesson_prs.py" in str(s.get("run") or "")),
               {})
    token = str(env.get("GH_TOKEN") or "")
    if "SHELDON_PAT" not in token:
        problems.append("the sweep authenticates with something other than a PAT: a label applied "
                        "with GITHUB_TOKEN starts no `pull_request: labeled` run, so the label does "
                        "nothing at all")
    run = "\n".join(str(s.get("run") or "") for s in steps)
    if "--apply" not in run:
        problems.append("the sweep is invoked without --apply: it would print a plan forever and "
                        "never arm anything")
    return problems


def test_the_sweep_is_wired_in_with_the_pat_and_the_default_branch():
    problems = arming_problems(source())
    assert problems == [], problems


def test_the_arming_guard_can_go_red():
    """The checks above are only worth having if they fail on the shapes they name."""
    text = source()
    assert arming_problems(text.replace("SHELDON_PAT", "GITHUB_TOKEN")), "GITHUB_TOKEN was accepted"
    assert arming_problems(text.replace("--apply", "")), "--apply was not required"
    assert arming_problems(text.replace("needs: sync", "needs: []")), "the ordering rule is not checked"
