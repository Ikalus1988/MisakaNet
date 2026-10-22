#!/usr/bin/env python3
"""Posting the conversion receipt: the four acceptance criteria of #3509.

The loop this closes was measured on 2026-10-18: 20 of the 26 issues closed that day were lessons
merged days earlier with the reporter never told. `done_but_open.py` finds them and
`intake_receipt.py` composes the receipt; this file is about the half that was missing — actually
putting the receipt on the issue, once, and marking it `ready-to-close` without closing anything.

What each test pins:

* AC1 — two runs, one receipt. The `<!-- misakanet-receipt -->` marker makes the second run *edit*
  the comment rather than add a second one. Driven as a fake two-run sequence so the transcript
  can be pasted as evidence.
* AC2 — a receipt only where `intake_receipt.py` resolves the citation through lesson frontmatter.
  A bare `#N` in prose must not trigger a post; the resolver already refuses that shape and this
  file asserts the *poster* obeys it rather than growing a second opinion.
* AC3 — the comment names the lesson id, the evidence level, `search_knowledge.py "<id>" --lessons`,
  and the receipt channel (`misakanet_register` with the same `client_id`).
* AC4 — a finding whose lesson was reverted or removed gets no receipt: the check re-runs against
  the current tree at post time, so a stale findings list cannot invent one.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.post_intake_receipts import (  # noqa: E402
    RECEIPT_MARKER,
    READY_TO_CLOSE,
    comment_body,
    format_result,
    main,
    post_finding,
    receipt_for,
)


class FakeGitHub:
    """An in-memory GitHub with the four operations the poster uses. Records every call."""

    def __init__(self, labels_on_issue=None):
        self.comments = {}        # issue -> [{id, body}]
        self.issue_labels = {}    # issue -> list of label names
        self.known_labels = set()
        self.actions = []
        self._next_id = 1
        if labels_on_issue:
            for issue, labels in labels_on_issue.items():
                self.issue_labels[issue] = list(labels)

    def list_comments(self, issue):
        self.actions.append(("list_comments", issue))
        return list(self.comments.get(issue, []))

    def create_comment(self, issue, body):
        cid = self._next_id
        self._next_id += 1
        self.comments.setdefault(issue, []).append({"id": cid, "body": body})
        self.actions.append(("create_comment", issue, cid))
        return {"id": cid, "body": body}

    def update_comment(self, comment_id, body):
        for lst in self.comments.values():
            for comment in lst:
                if comment["id"] == comment_id:
                    comment["body"] = body
                    self.actions.append(("update_comment", comment_id))
                    return comment
        raise AssertionError(f"no comment {comment_id} to update")

    def ensure_label(self, name):
        self.actions.append(("ensure_label", name))
        self.known_labels.add(name)

    def add_labels(self, issue, labels):
        self.actions.append(("add_labels", issue, tuple(labels)))
        self.issue_labels.setdefault(issue, []).extend(l for l in labels
                                                      if l not in self.issue_labels.get(issue, []))

    # What must never happen (the tests assert it didn't):
    def close_issue(self, issue, **kwargs):  # pragma: no cover - guard
        raise AssertionError(f"the poster must never close #{issue}")

    def marker_comments(self, issue):
        return [c for c in self.comments.get(issue, []) if RECEIPT_MARKER in (c["body"] or "")]


def write_lesson(tree: Path, name: str, intake: int, *, evidence: str = "E3",
                 lesson_id: str | None = None, prose_only: bool = False) -> Path:
    """One fixture lesson. `prose_only` mentions the intake number in the body but not in any
    citation field — the shape that must NOT produce a receipt."""
    lesson_id = lesson_id or name
    if prose_only:
        front = (f'---\ntitle: "Related work"\ndomain: devops\nstatus: published\n'
                 f'evidence_level: E1\nsource: "somewhere"\n---\n')
        body = f"\n## Problem\n\nThis resembles #{intake} and #9999 but converted neither.\n"
    else:
        front = (f'---\ntitle: "A real conversion"\ndomain: devops\nstatus: published\n'
                 f'evidence_level: {evidence}\nid: {lesson_id}\n'
                 f'source: "intake-{intake}"\nprovenance:\n  issue: "#{intake}"\n---\n')
        body = "\n## Problem\n\nThe thing that failed.\n\n## Fix\n\nThe fix.\n"
    path = tree / f"{name}.md"
    path.write_text(front + body, encoding="utf-8")
    return path


# ── AC1: two runs, one receipt ───────────────────────────────────────────────────────────────────
def test_two_runs_post_exactly_one_receipt(tmp_path, capsys):
    """The idempotency AC, as a fake two-run sequence: run 1 creates, run 2 edits."""
    write_lesson(tmp_path, "9011-lesson", 9011, evidence="E2")
    gh = FakeGitHub()
    finding = {"intake": 9011}

    print("=== fake two-run sequence (finding: intake #9011) ===")
    run1 = post_finding(finding, gh, lessons_dir=tmp_path)
    print(f"run 1: action={run1['action']} comment_id={run1.get('comment_id')} "
          f"labels={run1['labels']}")
    run2 = post_finding(finding, gh, lessons_dir=tmp_path)
    print(f"run 2: action={run2['action']} comment_id={run2.get('comment_id')} "
          f"labels={run2['labels']}")
    marker_count = len(gh.marker_comments(9011))
    print(f"comments carrying {RECEIPT_MARKER} after 2 runs: {marker_count}")

    assert run1["action"] == "created" and run1["posts"] == 1
    assert run2["action"] == "edited", "the second run must edit, not duplicate"
    assert run2["comment_id"] == run1["comment_id"], "the same comment is the one edited"
    assert marker_count == 1, "exactly one receipt per finding after two runs"
    assert len(gh.comments[9011]) == 1
    created = [a for a in gh.actions if a[0] == "create_comment"]
    updated = [a for a in gh.actions if a[0] == "update_comment"]
    assert len(created) == 1 and len(updated) == 1

    transcript = capsys.readouterr().out
    assert "run 1: action=created" in transcript
    assert "run 2: action=edited" in transcript
    assert ": 1" in transcript.splitlines()[-1]


def test_three_runs_still_leave_one_receipt(tmp_path):
    write_lesson(tmp_path, "9012-lesson", 9012)
    gh = FakeGitHub()
    for _ in range(3):
        post_finding({"intake": 9012}, gh, lessons_dir=tmp_path)
    assert len(gh.marker_comments(9012)) == 1
    assert len([a for a in gh.actions if a[0] == "create_comment"]) == 1


# ── AC2: only a frontmatter citation triggers a receipt ──────────────────────────────────────────
def test_a_bare_issue_number_in_prose_posts_nothing(tmp_path, capsys):
    """A lesson that merely *mentions* #N has not converted it — no comment, no label."""
    write_lesson(tmp_path, "mentions-only", 9021, prose_only=True)
    gh = FakeGitHub()

    print("=== bare #N in prose (intake #9021) ===")
    result = post_finding({"intake": 9021}, gh, lessons_dir=tmp_path)
    print(f"run 1: action={result['action']} reason={result['reason']}")
    print(f"comments created: {len(gh.comments.get(9021, []))}")
    print(f"labels applied: {result['labels']}")

    assert result["action"] == "skipped" and result["posts"] == 0
    assert gh.comments == {}, "a prose mention must not produce a comment"
    assert gh.actions == [], "and must not touch the issue at all"
    assert "no lesson cites" in result["reason"]
    transcript = capsys.readouterr().out
    assert "comments created: 0" in transcript


def test_the_negative_case_goes_through_the_ssot_not_a_local_rule(tmp_path):
    """Whatever the poster decides must equal what intake_receipt's resolver decides."""
    write_lesson(tmp_path, "mentions-only", 9022, prose_only=True)
    assert receipt_for(9022, lessons_dir=tmp_path)["emitted"] is False
    write_lesson(tmp_path, "real", 9023, evidence="E1")
    assert receipt_for(9023, lessons_dir=tmp_path)["emitted"] is True


# ── AC3: the comment names id, level, the command, and the receipt channel ───────────────────────
def test_the_comment_names_id_evidence_command_and_channel(tmp_path):
    write_lesson(tmp_path, "9031-lesson", 9031, evidence="E2", lesson_id="9031-lesson")
    gh = FakeGitHub()
    result = post_finding({"intake": 9031}, gh, lessons_dir=tmp_path)
    body = gh.marker_comments(9031)[0]["body"]

    assert result["action"] == "created"
    assert "9031-lesson" in body, "AC3: the lesson id must be named"
    assert "E2" in body, "AC3: the evidence level must be named"
    assert 'search_knowledge.py "9031-lesson" --lessons' in body, (
        "AC3: the reporter needs a command they can run — search_knowledge.py \"<id>\" --lessons"
    )
    assert "misakanet_register" in body, "AC3: the receipt channel must be named"
    assert "client_id" in body, "AC3: … with the same client_id"
    assert RECEIPT_MARKER in body, "AC1: the marker that makes re-runs idempotent"
    # The receipt body itself is the SSOT's render(), not a parallel copy of it.
    assert "回执：你的报料已经变成课程" in body


def test_dry_run_prints_but_never_writes(tmp_path, capsys):
    write_lesson(tmp_path, "9032-lesson", 9032)
    gh = FakeGitHub()
    result = post_finding({"intake": 9032}, gh, lessons_dir=tmp_path, dry_run=True)
    assert result["action"] == "would-upsert" and result["posts"] == 0
    assert gh.actions == [] and gh.comments == {}
    assert RECEIPT_MARKER in result["body"]


# ── AC4: a reverted/removed lesson gets no receipt ───────────────────────────────────────────────
def test_a_finding_whose_lesson_is_gone_gets_no_receipt(tmp_path):
    """A stale findings list cannot invent a receipt: the resolve re-runs against the tree."""
    write_lesson(tmp_path, "9041-lesson", 9041)  # cited once…
    (tmp_path / "9041-lesson.md").unlink()      # …then reverted
    gh = FakeGitHub()

    result = post_finding({"intake": 9041, "lessons": ["9041-lesson.md"]}, gh, lessons_dir=tmp_path)

    assert result["action"] == "skipped" and result["posts"] == 0
    assert "no lesson cites" in result["reason"]
    assert gh.comments == {}, "no receipt for a lesson that is not on the tree"
    assert gh.issue_labels == {}, "and no ready-to-close for work that is no longer done"


def test_the_removed_lesson_run_writes_nothing_at_all(tmp_path):
    """Once posted, removing the lesson must not make the next run touch the issue either."""
    lesson = write_lesson(tmp_path, "9042-lesson", 9042)
    gh = FakeGitHub()
    first = post_finding({"intake": 9042}, gh, lessons_dir=tmp_path)
    assert first["action"] == "created"

    lesson.unlink()
    before = list(gh.actions)
    result = post_finding({"intake": 9042}, gh, lessons_dir=tmp_path)
    new_actions = gh.actions[len(before):]

    assert result["action"] == "skipped" and result["posts"] == 0
    assert new_actions == [], f"the skip path must write nothing at all, got {new_actions}"
    assert len(gh.marker_comments(9042)) == 1, "the old comment is left as it was, not duplicated"
    assert gh.issue_labels.get(9042) == [READY_TO_CLOSE], "run 1's label is left alone"


# ── labelling and the things it must not do ──────────────────────────────────────────────────────
def test_ready_to_close_is_added_and_needs_human_review_left_alone(tmp_path):
    write_lesson(tmp_path, "9051-lesson", 9051)
    gh = FakeGitHub(labels_on_issue={9051: ["needs-human-review", "intake"]})
    result = post_finding({"intake": 9051}, gh, lessons_dir=tmp_path)

    assert result["labels"] == [READY_TO_CLOSE]
    assert READY_TO_CLOSE in gh.issue_labels[9051], "the new label is applied"
    assert "needs-human-review" in gh.issue_labels[9051], "and left alone"
    assert "intake" in gh.issue_labels[9051], "nothing else is touched either"
    assert READY_TO_CLOSE in gh.known_labels, "the label is created if it did not exist"
    close_calls = [a for a in gh.actions if "close" in a[0]]
    assert close_calls == [], "closing stays a human act (SOP §2)"


def test_label_application_is_idempotent_across_runs(tmp_path):
    write_lesson(tmp_path, "9052-lesson", 9052)
    gh = FakeGitHub()
    post_finding({"intake": 9052}, gh, lessons_dir=tmp_path)
    post_finding({"intake": 9052}, gh, lessons_dir=tmp_path)
    assert gh.issue_labels[9052].count(READY_TO_CLOSE) == 1


# ── CLI wiring ───────────────────────────────────────────────────────────────────────────────────
def test_cli_dry_run_over_a_findings_file(tmp_path, capsys):
    write_lesson(tmp_path, "9061-lesson", 9061)
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([{"intake": 9061, "lessons": ["stale/path.md"]}]),
                        encoding="utf-8")

    # Point the SSOT at the fixture tree by monkeypatching the seam.
    import scripts.post_intake_receipts as mod
    original = mod.receipt_for
    mod.receipt_for = lambda intake, source="unknown", lessons_dir=None: original(
        intake, source, lessons_dir=tmp_path)
    try:
        rc = main(["--findings", str(findings)])
    finally:
        mod.receipt_for = original

    assert rc == 0
    out = capsys.readouterr().out
    assert "9061-lesson" in out and "would upsert" in out
    assert "posted/updated" in out


def test_an_explicitly_empty_findings_file_does_not_relist_the_backlog(tmp_path, monkeypatch):
    """`[]` from the detector means "nothing to do" — it must not trigger a second listing pass."""
    findings = tmp_path / "empty.json"
    findings.write_text("[]", encoding="utf-8")

    import scripts.done_but_open as dbo
    import scripts.post_intake_receipts as mod

    def explode(*args, **kwargs):
        raise AssertionError("the open backlog must not be listed again")

    monkeypatch.setattr(dbo, "open_issue_numbers", explode)
    assert mod.main(["--findings", str(findings)]) == 0


def test_a_missing_findings_file_is_an_error_not_silence(tmp_path):
    with pytest.raises(SystemExit):
        main(["--findings", str(tmp_path / "nope.json")])


def test_the_workflow_step_runs_the_poster_and_never_closes():
    import yaml
    workflow = REPO / ".github" / "workflows" / "intake-salvage-digest.yml"
    wf = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    runs = [s.get("run") or "" for s in wf["jobs"]["salvage-digest"]["steps"]]
    poster = [r for r in runs if "post_intake_receipts.py" in r]
    assert len(poster) == 1, "exactly one step posts the receipts"
    assert "--post" in poster[0], "and it opts in to actually posting"
    assert "--findings" in poster[0], "fed by the findings JSON the detector step already wrote"
    assert "close" not in poster[0], (
        "the receipt step must never close — closing stays a human act (SOP §2)"
    )
    assert "scripts/done_but_open.py" not in poster[0], (
        "the detector is invoked once per run (wiring test #2040); the poster reuses its JSON"
    )
    # The comment must not be posted through `gh` in a way that bypasses the marker either.
    assert "gh issue comment" not in poster[0], "posting goes through the marker-aware script"


def test_format_result_names_what_happened():
    assert "skipped" in format_result({"intake": 1, "action": "skipped", "reason": "no lesson cites"})
    assert "edited" in format_result({"intake": 1, "action": "edited", "comment_id": 5,
                                      "lessons": ["a"], "evidence_level": "E1", "labels": [READY_TO_CLOSE]})
    assert "ready-to-close" in format_result({"intake": 1, "action": "created", "comment_id": 5,
                                              "lessons": ["a"], "evidence_level": "E1",
                                              "labels": [READY_TO_CLOSE]})


# ── the comment read must see every page (the AC1 guarantee depends on it) ───────────────────────
def test_list_comments_paginates_so_a_receipt_past_the_first_page_is_still_found():
    """GitHub returns comments oldest-first, so one `per_page=100` page is the OLDEST 100 and the
    receipt — typically the newest — is the one that goes missing past the cliff. A missed marker
    means a re-run posts a second receipt, which is exactly what AC1 forbids. (Regression: the
    `test_github_list_reads_paginate` gate caught the original one-page read.)"""
    from scripts.post_intake_receipts import GitHub

    pages = {
        1: [{"id": i, "body": f"noise {i}"} for i in range(1, 101)],
        2: [{"id": 200, "body": f"{RECEIPT_MARKER}\nold receipt"}],
    }
    seen = []

    def fake_request(method, path, payload=None):
        seen.append(path)
        # NB: `per_page=100` *contains* `page=100`, and `page=1` is a prefix of that — a naive
        # substring match hands back page 1 forever (the trap the paginate gate was written for).
        match = re.search(r"(?<!per_)page=(\d+)", path)
        return pages.get(int(match.group(1)), []) if match else []

    gh = GitHub(token="t", repo="o/r", request=fake_request)
    comments = gh.list_comments(7)

    assert len(comments) == 101, "page 1 (100) + page 2 (1) must all come back"
    assert any(RECEIPT_MARKER in c["body"] for c in comments), (
        "a receipt comment on page 2 must be visible — otherwise the re-run duplicates it"
    )
    assert len(seen) == 2 and "page=1" in seen[0] and "page=2" in seen[1], seen

    # And the marker on page 2 is what the poster keys on — found via `GitHub.list_comments`.
    assert next(c for c in comments if RECEIPT_MARKER in c["body"])["id"] == 200


def test_list_comments_stops_at_the_page_cap():
    """A proxy that strips `page` must not make the read loop forever."""
    import scripts.post_intake_receipts as mod
    from scripts.post_intake_receipts import GitHub

    calls = []

    def always_a_full_page(method, path, payload=None):
        calls.append(path)
        return [{"id": i, "body": "x"} for i in range(100)]

    gh = GitHub(token="t", repo="o/r", request=always_a_full_page)
    assert len(gh.list_comments(7)) == 100 * mod.MAX_LIST_PAGES
    assert len(calls) == mod.MAX_LIST_PAGES


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:
                print(f"FAIL: {e}")
