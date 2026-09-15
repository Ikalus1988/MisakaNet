"""Tests for the intake coverage triage helper."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import intake_coverage

ISSUE_1460_TITLE = (
    "[Intake] Docker build fails with exit code 137 when using multi-stage builds "
    "with large base images on GitHub Actions runners with 7GB RAM limit"
)


def test_issue_1460_title_produces_compact_error_query_and_lesson_hit():
    """The long title is retained, but the extracted error query finds the lesson."""
    normalized, queries = intake_coverage.build_queries(ISSUE_1460_TITLE)

    assert normalized.startswith("Docker build fails")
    assert "[Intake]" not in normalized
    assert "docker exit code 137" in queries

    report = intake_coverage.analyze(ISSUE_1460_TITLE, top_n=5)
    matching_ids = {
        result["id"] for query_report in report["queries"] for result in query_report["results"]
    }
    error_query = next(
        item for item in report["queries"] if item["query"] == "docker exit code 137"
    )
    assert "kubernetes-crashloopbackoff-debugging" in matching_ids
    assert any(
        result["id"] == "kubernetes-crashloopbackoff-debugging" for result in error_query["results"]
    )
    assert report["conclusion"] == "lesson-covered"


def test_pipeline_metadata_and_opire_template_are_removed():
    body = """**Kind:** missing_lesson
**Source:** claude-code
**Dedup:** `abc123`

## Problem
Docker reports exit code 137.

_Submitted via remote MCP (claude-code). No account required._
<br/>
<hr/>
<details><summary>Opire</summary>
/reward 100 and /try instructions
</details>
"""

    cleaned = intake_coverage.strip_pipeline_boilerplate(body)

    assert "Kind" not in cleaned
    assert "Source" not in cleaned
    assert "Dedup" not in cleaned
    assert "Submitted via remote MCP" not in cleaned
    assert "Opire" not in cleaned
    assert "reward" not in cleaned
    assert "Docker reports exit code 137" in cleaned


def test_dotted_paths_and_underscored_error_strings_survive_normalization():
    _, queries = intake_coverage.build_queries(
        "[Question] worker returns ERR_CONNECTION_RESET in package.json",
        "The failing path is src/register_proxy.py",
    )
    flattened = " | ".join(queries)
    assert "err_connection_reset" in flattened
    assert "package.json" in flattened or "src/register_proxy.py" in flattened


def test_conclusion_distinguishes_faq_only_and_no_coverage():
    assert (
        intake_coverage.classify_conclusion(
            [{"type": "faq", "score": 0.6, "meets_threshold": True}]
        )
        == "faq-only"
    )
    assert (
        intake_coverage.classify_conclusion(
            [{"type": "lesson", "score": 0.39, "meets_threshold": False}]
        )
        == "no-coverage"
    )


def test_search_report_uses_type_from_frontmatter_without_changing_engine(monkeypatch):
    lesson = SimpleNamespace(
        filepath=Path("lessons/contrib/covered.md"),
        title="Covered lesson",
        content="---\ntitle: Covered lesson\ntype: lesson\n---\nfix",
    )
    faq = SimpleNamespace(
        filepath=Path("lessons/contrib/faq-entry.md"),
        title="FAQ entry",
        content="---\ntitle: FAQ entry\ntype: faq\n---\nanswer",
    )

    monkeypatch.setattr(intake_coverage, "_load_docs", lambda *args, **kwargs: [lesson, faq])
    monkeypatch.setattr(
        intake_coverage,
        "_rank_docs",
        lambda query, docs, titles_only=False, broad_only=False: [(0.8, lesson), (0.7, faq)],
    )

    report = intake_coverage.analyze("[Intake] covered query", top_n=2)

    assert report["conclusion"] == "lesson-covered"
    assert report["queries"][0]["results"][0]["type"] == "lesson"
    assert report["queries"][0]["results"][1]["type"] == "faq"
