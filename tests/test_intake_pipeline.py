#!/usr/bin/env python3
"""Tests for scripts/intake_pipeline.py (PRD ③) — parse/classify/draft/precheck."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import intake_pipeline as ip


class TestParseIntake(unittest.TestCase):
    def test_parse_normalizes_fields(self):
        raw = {"kind": "missing_lesson", "problem": "pip timeout", "source": "mcp", "source_id": "s1"}
        out = ip.parse_intake(raw)
        self.assertEqual(out["kind"], "missing_lesson")
        self.assertEqual(out["source_id"], "s1")
        self.assertEqual(out["title"], "")

    def test_parse_defaults_kind_and_source_id(self):
        out = ip.parse_intake({"problem": "x"})
        self.assertEqual(out["kind"], "missing_lesson")
        self.assertEqual(out["source"], "mcp")
        self.assertTrue(out["source_id"].startswith("mcp-"))

    def test_parse_rejects_unknown_kind(self):
        out = ip.parse_intake({"kind": "bogus", "problem": "x"})
        self.assertEqual(out["kind"], "missing_lesson")


class TestClassify(unittest.TestCase):
    def test_python_domain_hint(self):
        intake = ip.parse_intake({"problem": "pip install fails with traceback", "kind": "missing_lesson"})
        cls = ip.classify(intake)
        self.assertEqual(cls["domain"], "python")

    def test_explicit_domain_wins(self):
        intake = ip.parse_intake({"problem": "python error", "domain": "devops", "kind": "missing_lesson"})
        cls = ip.classify(intake)
        self.assertEqual(cls["domain"], "devops")

    def test_question_type(self):
        intake = ip.parse_intake({"problem": "how to fix?", "kind": "question"})
        cls = ip.classify(intake)
        self.assertEqual(cls["type"], "question")


class TestGenerateDraft(unittest.TestCase):
    def test_draft_has_frontmatter_and_sections(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "service crashes on start",
                                  "error": "Segfault", "fix": "increase stack size",
                                  "verification": "restart ok", "source": "mcp", "source_id": "d1"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        self.assertTrue(draft["content_md"].startswith("---"))
        self.assertIn("## Problem", draft["content_md"])
        self.assertIn("## Solution", draft["content_md"])
        self.assertIn("## Verification", draft["content_md"])
        self.assertTrue(draft["slug"])

    def test_draft_marks_missing_solution(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "something broke", "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        self.assertIn("pending review", draft["content_md"])


class TestPrecheck(unittest.TestCase):
    def test_short_problem_flagged(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "short", "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        self.assertTrue(any("PROBLEM_TOO_SHORT" in i for i in pre["issues"]))
        self.assertLess(pre["score"], 100)

    def test_secret_pattern_flagged(self):
        intake = ip.parse_intake({"kind": "missing_lesson",
                                  "problem": "token ghp_abcdefghijklmnopqrstuvwxyz leaked",
                                  "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        self.assertTrue(any("SECRET_PATTERN" in i for i in pre["issues"]))

    def test_complete_intake_passes(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "database connection pool exhausted",
                                  "fix": "increase pool size", "verification": "load test passes",
                                  "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        self.assertTrue(pre["pass"])


class TestRun(unittest.TestCase):
    def test_dry_run_returns_preview_without_persisting(self):
        result = ip.run({"kind": "question", "problem": "how does sync work?", "source": "mcp"}, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["kind"], "question")
        self.assertIn("draft_preview", result)


class TestQuestionRouting(unittest.TestCase):
    """#1396: question intakes must never mint a lesson-shaped draft into
    lesson_drafts — they route straight to a [Question] issue."""

    def test_question_kind_skips_persist_and_lesson_notify(self):
        calls = {"persist": 0, "notify": 0, "notify_q": 0}
        orig = (ip.persist_draft, ip.notify, ip.notify_question)

        def fake_persist(*a, **k):
            calls["persist"] += 1
            return True

        def fake_notify(*a, **k):
            calls["notify"] += 1
            return {"issue_number": 1}

        def fake_notify_question(intake):
            calls["notify_q"] += 1
            return {"issue_number": 99, "issue_url": "https://github.com/x/issues/99"}

        ip.persist_draft, ip.notify, ip.notify_question = fake_persist, fake_notify, fake_notify_question
        try:
            res = ip.run({"kind": "question", "problem": "How do I set up MCP auth?", "source": "mcp"})
            self.assertEqual(calls["persist"], 0, "question must not persist a lesson draft")
            self.assertEqual(calls["notify"], 0, "lesson notify must not run for questions")
            self.assertEqual(calls["notify_q"], 1)
            self.assertEqual(res["routed_as"], "question")
            self.assertEqual(res["issue"]["issue_number"], 99)
        finally:
            ip.persist_draft, ip.notify, ip.notify_question = orig

    def test_question_issue_payload_is_question_shaped(self):
        title, labels, body = ip._question_issue_payload(
            ip.parse_intake({"kind": "question", "problem": "How do I configure MCP auth?", "source": "mcp"})
        )
        self.assertTrue(title.startswith("[Question]"))
        self.assertIn("question", labels)
        self.assertIn("needs-answer", labels)
        self.assertNotIn("new-lesson", labels)
        self.assertIn("**Kind:** question", body)
        self.assertIn("NOT a lesson candidate", body)
        # No lesson-shaped filler sections for questions.
        self.assertNotIn("## Solution", body)
        self.assertNotIn("pending review — no fix recorded", body)

    def test_long_question_body_is_not_silently_truncated(self):
        """#2743: a 2,000-char cap sheared the code-weight column off a ranked
        surface ledger, and the issue still looked answerable — numbered
        1,3,5,7,9,11,13 and cut mid-word. Whatever the submitter wrote past the
        cap has to reach the issue."""
        tail = "ROW-9-CODE-WEIGHT-612-LINES"
        problem = "surface ledger\n" + ("filler row to push past the old cap\n" * 60) + tail
        self.assertGreater(len(problem), 2000, "fixture must exceed the old cap")

        _title, _labels, body = ip._question_issue_payload(
            ip.parse_intake({"kind": "question", "problem": problem, "source": "mcp"})
        )
        self.assertIn(tail, body, "content past the old cap must survive into the issue")
        self.assertNotIn("Truncated at", body, "a sub-cap body must not claim truncation")

    def test_over_cap_question_body_is_truncated_visibly(self):
        """Past the cap we still have to cut, but loudly: a body that fits
        GitHub's 65,536 limit and says what went missing."""
        problem = "x" * (ip.QUESTION_BODY_CAP + 500)
        _title, _labels, body = ip._question_issue_payload(
            ip.parse_intake({"kind": "question", "problem": problem, "source": "mcp"})
        )
        self.assertIn("Truncated at", body)
        self.assertIn(f"{ip.QUESTION_BODY_CAP:,} characters", body)
        self.assertIn(f"{len(problem):,} were submitted", body)
        self.assertLess(len(body), 65_536, "payload must still fit GitHub's body limit")

    def test_short_question_body_passes_through_verbatim(self):
        problem = "How do I configure MCP auth?"
        _title, _labels, body = ip._question_issue_payload(
            ip.parse_intake({"kind": "question", "problem": problem, "source": "mcp"})
        )
        self.assertIn(problem, body)
        self.assertNotIn("Truncated", body)


class TestTruncationTravelsWithTheDraft(unittest.TestCase):
    """#2760: the 2,000-character caps used to cut silently, so a draft that lost its
    tail was indistinguishable from a complete one. The cut has to travel with both
    artifacts the pipeline produces — the draft it writes and the result it returns —
    which is the shape `misakanet_get_lesson` uses (`{truncated, content_length,
    content_returned, full_content_url}`)."""

    def _over_cap(self) -> dict:
        return ip.parse_intake({
            "kind": "missing_lesson", "source": "mcp", "source_id": "s1",
            "problem": "P" * 2500, "error": "E" * 2100, "fix": "F" * 4100,
            "verification": "V" * 2100,
        })

    def test_the_error_section_announces_its_cut(self):
        intake = self._over_cap()
        md = ip.generate_draft(intake, ip.classify(intake))["content_md"]
        self.assertIn("Truncated at 2,000 characters by intake-pipeline", md)
        self.assertIn("2,100 were submitted", md)
        self.assertIn("intake of record", md, "the notice must say where the full text still is")
        self.assertNotIn("E" * (ip.ERROR_SECTION_CAP + 1), md, "the head is the cap, not more")

    def test_the_stored_columns_announce_their_own_cut(self):
        """The D1 columns are what a triage query reads, and they are cut separately."""
        intake = self._over_cap()
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        captured = {}

        def fake_query(sql, params=None):
            captured["params"] = params
            return {"result": [{"meta": {"changes": 1}}]}

        original = ip._d1_query
        ip._d1_query = fake_query
        try:
            self.assertTrue(ip.persist_draft(intake, cls, draft, pre))
        finally:
            ip._d1_query = original
        problem, fix, verification = captured["params"][7:10]
        self.assertIn("Truncated at 2,000 characters", problem)
        self.assertIn("lesson_drafts.solution column", fix)
        self.assertIn("lesson_drafts.verification column", verification)
        self.assertIn("`content_md` of this same row", problem,
                      "the notice must name the copy that still has the full text")

    def test_the_result_says_which_fields_were_cut_and_by_how_much(self):
        result = ip.run({"kind": "missing_lesson", "source": "mcp", "source_id": "s1",
                         "problem": "P" * 2500, "error": "E" * 2100, "fix": "F" * 4100,
                         "verification": "V" * 2100}, dry_run=True)
        self.assertTrue(result["truncated"])
        self.assertEqual(set(result["truncations"]),
                         {"problem", "error", "fix", "verification"})
        self.assertEqual(result["truncations"]["fix"],
                         {"cap": ip.DRAFT_COLUMN_CAPS["fix"], "content_length": 4100,
                          "content_returned": ip.DRAFT_COLUMN_CAPS["fix"]})

    def test_the_issue_preview_announces_its_cut(self):
        """`notify` embeds `content_md[:3000]` in the issue; that cut has to be visible too."""
        intake = ip.parse_intake({"kind": "missing_lesson", "source": "mcp",
                                  "problem": "database connection pool exhausted", "source_id": "s1"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        draft["content_md"] = "x" * (ip.DRAFT_PREVIEW_CAP + 10)
        pre = ip.precheck(intake, draft)
        sent = {}

        class _Resp:
            def read(self):
                return json.dumps({"number": 7, "html_url": "https://example.invalid/7"}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(req, timeout=None):
            sent["body"] = json.loads(req.data.decode())["body"]
            return _Resp()

        original = ip.urllib.request.urlopen
        had_token = os.environ.get("GH_TOKEN")
        os.environ["GH_TOKEN"] = "test-token"
        ip.urllib.request.urlopen = fake_urlopen
        try:
            ip.notify(intake, cls, draft, pre, is_new=True)
        finally:
            ip.urllib.request.urlopen = original
            if had_token is None:
                os.environ.pop("GH_TOKEN", None)
            else:
                os.environ["GH_TOKEN"] = had_token
        self.assertIn("Truncated at 3,000 characters by intake-pipeline", sent["body"])
        self.assertIn("lesson_drafts.content_md", sent["body"])
        fence = sent["body"].index("```markdown")
        close = sent["body"].index("```", fence + len("```markdown"))
        self.assertGreater(sent["body"].index("Truncated at"), close,
                           "the notice inside the fenced block would render as the draft's own text")

    def test_no_field_can_be_cut_without_the_result_saying_so(self):
        """The shape, not the value: each named cap must surface, whatever the number becomes."""
        for field, cap in [("error", ip.ERROR_SECTION_CAP), *ip.DRAFT_COLUMN_CAPS.items()]:
            raw = {"kind": "missing_lesson", "source": "mcp",
                   "problem": "a real problem statement"}
            raw[field] = "z" * (cap + 1)
            report = ip.truncation_report(ip.parse_intake(raw))
            self.assertIn(field, report, f"{field} was cut without the result reporting it")

    def test_an_under_cap_submission_is_not_announced(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "a real problem statement",
                                  "error": "Segfault", "fix": "increase the stack size",
                                  "verification": "restart ok", "source": "mcp"})
        self.assertNotIn("Truncated", ip.generate_draft(intake, ip.classify(intake))["content_md"])
        self.assertEqual(ip.truncation_report(intake), {})
        self.assertNotIn("truncated", ip.run({"kind": "missing_lesson", "source": "mcp",
                                              "problem": "a real problem statement",
                                              "fix": "increase the stack size"}, dry_run=True))

    def test_an_over_cap_question_reports_its_cut_in_the_result(self):
        """The question body is the deliverable; `_clip_question` already says so in the issue."""
        problem = "q" * (ip.QUESTION_BODY_CAP + 5)
        result = ip.run({"kind": "question", "problem": problem, "source": "mcp"}, dry_run=True)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["truncations"]["problem"]["cap"], ip.QUESTION_BODY_CAP)
        self.assertEqual(result["truncations"]["problem"]["content_length"], len(problem))
class TestQuestionLabels(unittest.TestCase):
    """A question must not become a lesson because its `kind` field was wrong (#2760).

    `#2760` is a question — labels `question`, `type:question`, body a follow-up about a truncated
    intake — and two lesson pull requests on unrelated topics both cited it (`#3344`/`#3345`).
    `kind` is the only signal the MCP payload carries; when a caller *does* have the issue labels
    (the issue is the intake of record, and `intake-auto-review.yml` adds both), the label wins.
    """

    def test_labels_are_collected_in_every_spelling_the_callers_use(self):
        self.assertEqual(ip.parse_intake({"labels": ["Question", "type:question"]})["labels"],
                         ["question", "type:question"])
        self.assertEqual(ip.parse_intake({"labels": "intake, question"})["labels"],
                         ["intake", "question"])
        self.assertEqual(ip.parse_intake({"label": "type:question"})["labels"], ["type:question"])
        # Junk is dropped, never stringified into a label that happens to match nothing.
        self.assertEqual(ip.parse_intake({"labels": [1, None, "  ", "question"]})["labels"],
                         ["question"])
        self.assertEqual(ip.parse_intake({})["labels"], [])

    def test_routing_signal_is_named(self):
        self.assertEqual(ip.question_routed_by(ip.parse_intake({"kind": "question"})), "kind")
        self.assertEqual(
            ip.question_routed_by(ip.parse_intake({"kind": "missing_lesson", "labels": ["type:question"]})),
            "label")
        self.assertIsNone(ip.question_routed_by(ip.parse_intake({"kind": "missing_lesson"})))
        # `question` inside a longer label is not the label: matching must be exact, or a future
        # `question-followup` label silently reroutes failure reports.
        self.assertIsNone(
            ip.question_routed_by(ip.parse_intake({"labels": ["question-followup"]})))

    def test_a_question_label_never_mints_a_lesson_draft(self):
        """`kind` says `missing_lesson`; the label says question. The label is what the issue
        workflows acted on, so the pipeline must not score it as a lesson."""
        calls = {"persist": 0, "notify": 0, "notify_q": 0}
        orig = (ip.persist_draft, ip.notify, ip.notify_question)
        ip.persist_draft = lambda *a, **k: calls.__setitem__("persist", calls["persist"] + 1) or True
        ip.notify = lambda *a, **k: calls.__setitem__("notify", calls["notify"] + 1) or {"issue_number": 1}
        ip.notify_question = (lambda intake: calls.__setitem__("notify_q", calls["notify_q"] + 1)
                              or {"issue_number": 42, "issue_url": "https://github.com/x/issues/42"})
        try:
            res = ip.run({"kind": "missing_lesson", "problem": "Follow-up on a truncated body",
                          "source": "mcp", "labels": ["intake", "question", "type:question"]})
        finally:
            ip.persist_draft, ip.notify, ip.notify_question = orig
        self.assertEqual(calls["persist"], 0, "a labelled question must not persist a lesson draft")
        self.assertEqual(calls["notify"], 0, "the lesson notify path must not run for a question")
        self.assertEqual(calls["notify_q"], 1)
        self.assertEqual(res["routed_as"], "question")
        self.assertEqual(res["routed_by"], "label")

    def test_a_labelled_failure_report_still_mints_a_lesson(self):
        """The control: the rule must not fire on every labelled intake."""
        self.assertIsNone(ip.question_routed_by(
            ip.parse_intake({"kind": "missing_lesson", "labels": ["intake", "mcp-intake", "pending-review"]})))

    def test_the_skip_says_where_the_question_goes(self):
        """A skip whose only trace is a missing draft is indistinguishable from a bug."""
        import contextlib
        import io

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            res = ip.run({"kind": "question", "problem": "How do I configure MCP auth?",
                          "source": "mcp"}, dry_run=True)
        printed = stderr.getvalue()
        self.assertIn("question intake", printed)
        self.assertIn("kind=question", printed)
        # The result carries the same statement, for callers that read JSON rather than a log.
        note = res["note"]
        for fragment in ("[Question]", "sync-question-answers.yml", "FAQ", "lessons/"):
            self.assertIn(fragment, note, note)
        self.assertIn("not lesson candidates", note)


if __name__ == "__main__":
    unittest.main()
