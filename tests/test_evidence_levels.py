#!/usr/bin/env python3
"""Tests for lesson evidence levels E0–E4 (Issue #786)."""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from misakanet.evidence import (  # noqa: E402
    DEFAULT_EVIDENCE_LEVEL,
    EVIDENCE_LEVELS,
    PROMOTION_RULES,
    describe,
    distribution,
    evidence_label,
    evidence_of,
    evidence_weight,
    next_level,
    normalize_evidence_level,
    promotion_requirement,
    trust_score,
)


def test_levels_match_the_issue_model():
    assert EVIDENCE_LEVELS == ["E0", "E1", "E2", "E3", "E4"]
    assert DEFAULT_EVIDENCE_LEVEL == "E0"
    assert evidence_label("E3") == "Sandbox / CI verified recovery"


@pytest.mark.parametrize("value", [None, "", "  ", "E9", "high", "verified", {}, [], True, False, -1, 7])
def test_unknown_values_never_claim_evidence(value):
    """Anything unrecognised degrades to E0 — evidence is never assumed."""
    assert normalize_evidence_level(value) == "E0"


@pytest.mark.parametrize("value,expected", [
    ("E2", "E2"), ("e2", "E2"), (" e4 ", "E4"), (0, "E0"), (3, "E3"), (2.0, "E2"),
])
def test_reasonable_spellings_are_accepted(value, expected):
    assert normalize_evidence_level(value) == expected


def test_weights_increase_monotonically():
    weights = [evidence_weight(level) for level in EVIDENCE_LEVELS]
    assert weights == sorted(weights)
    assert weights[0] == 0.0 and weights[-1] == 1.0


def test_missing_frontmatter_field_defaults_to_e0():
    assert evidence_of({"title": "x"}) == "E0"
    assert evidence_of(None) == "E0"
    assert evidence_of({"evidence_level": "E4"}) == "E4"


def test_promotion_is_one_step_at_a_time():
    assert [rule[:2] for rule in PROMOTION_RULES] == [("E0", "E1"), ("E1", "E2"), ("E2", "E3"), ("E3", "E4")]
    assert next_level("E0") == "E1"
    assert next_level("E4") is None
    assert "review" in promotion_requirement("E0").lower()
    assert "reproduce" in promotion_requirement("E1").lower()
    assert "ci" in promotion_requirement("E2").lower()
    assert "reuse" in promotion_requirement("E3").lower()
    assert promotion_requirement("E4") is None


def test_trust_score_scales_quality_by_evidence():
    assert trust_score(1.0, "E0") == 0.7
    assert trust_score(1.0, "E4") == 1.0
    assert trust_score(0.0, "E4") == 0.0
    # Same writing quality, different evidence → different trust.
    assert trust_score(0.8, "E3") > trust_score(0.8, "E1")


def test_trust_score_is_robust_to_bad_input():
    assert trust_score(None, "E2") == 0.0
    assert trust_score("nonsense", "E2") == 0.0
    assert trust_score(5.0, "E4") == 1.0, "quality is clamped to 1.0"
    assert trust_score(-3, "E4") == 0.0


def test_describe_gives_a_ui_everything_it_needs():
    info = describe("e2")
    assert info["evidence_level"] == "E2"
    assert info["next_level"] == "E3"
    assert info["weight"] == 0.5
    assert info["label"] and info["how_to_achieve"] and info["promotion_requirement"]


def test_distribution_reports_every_level():
    counts = distribution(["E0", "E0", "E3", "bogus", None])
    assert counts == {"E0": 4, "E1": 0, "E2": 0, "E3": 1, "E4": 0}


# ── Integration with the surrounding pipeline ──────────────────────────────

def test_schema_constrains_the_field():
    schema = json.loads((REPO_ROOT / "schemas" / "lesson.json").read_text(encoding="utf-8"))
    field = schema["properties"]["evidence_level"]
    assert field["enum"] == EVIDENCE_LEVELS
    assert field["default"] == "E0"
    assert "evidence_level" not in schema["required"], "existing lessons must stay valid"


def test_new_lessons_default_to_e0():
    source = (REPO_ROOT / "scripts" / "queue_lesson.py").read_text(encoding="utf-8")
    # Evidence level is now inferred (infer_evidence_level) with a DEFAULT
    # fallback — assert both the inference hook and the E0 fallback exist.
    assert "infer_evidence_level(content)" in source
    assert "DEFAULT_EVIDENCE_LEVEL" in source
    assert source.count("evidence_level") >= 3


def test_index_generator_emits_the_field():
    source = (REPO_ROOT / "scripts" / "misakanet-index.py").read_text(encoding="utf-8")
    assert "evidence_level = evidence_of(fm)" in source


def test_index_generator_infers_evidence_and_trust(tmp_path):
    """Coogen borrow (Phase 2): frontmatter wins; legacy lessons get a
    content-inferred level + trust_score so public pages can show evidence
    counts instead of composite averages."""
    import importlib.util

    sys.path.insert(0, str(REPO_ROOT))
    path = REPO_ROOT / "scripts" / "misakanet-index.py"
    spec = importlib.util.spec_from_file_location("misakanet_index_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    core = tmp_path / "core"
    core.mkdir()

    legacy = core / "legacy-no-frontmatter.md"
    legacy.write_text(
        "---\n"
        + json.dumps({"title": "Legacy", "domain": "devops", "status": "published"})
        + "\n---\n\n"
        "## Problem\n\nx\n\n## Solution\n\ny\n\n"
        "Verified by CI: the workflow run passed all checks.\n",
        encoding="utf-8",
    )
    explicit = core / "explicit-frontmatter.md"
    explicit.write_text(
        "---\n"
        + json.dumps({"title": "Explicit", "domain": "git", "status": "published",
                      "evidence_level": "E4", "confidence": 0.8})
        + "\n---\n\n## Problem\n\nplain body without evidence markers\n",
        encoding="utf-8",
    )

    index = module.build_index(tmp_path)

    by_id = {e["id"]: e for e in index}
    assert by_id["legacy-no-frontmatter"]["evidence_level"] == "E3"
    assert by_id["legacy-no-frontmatter"]["evidence_source"] == "inferred"
    # Frontmatter wins over inference, even when the body has no markers.
    assert by_id["explicit-frontmatter"]["evidence_level"] == "E4"
    assert by_id["explicit-frontmatter"]["evidence_source"] == "frontmatter"
    # trust_score is bounded and scales with evidence.
    for e in index:
        assert 0.0 <= e["trust_score"] <= 1.0
    assert by_id["explicit-frontmatter"]["trust_score"] > by_id["legacy-no-frontmatter"]["trust_score"]


def test_scorer_reports_evidence_without_changing_the_quality_gate(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from scripts.score_lessons import score_lesson

    lesson = REPO_ROOT / "lessons" / "core" / "_evidence_probe.md"
    frontmatter = {"title": "Probe lesson", "domain": "devops", "status": "published"}
    body = (
        "## Problem\n\nx\n\n## Root Cause\n\nThe error message says exit code 1.\n\n"
        "## Solution\n\ny\n\n## Verification\n\n```bash\npytest\n```\nexpected: pass\n"
    )

    try:
        lesson.write_text("---\n" + json.dumps(frontmatter) + "\n---\n\n" + body, encoding="utf-8")
        e0 = score_lesson(lesson)

        lesson.write_text(
            "---\n" + json.dumps({**frontmatter, "evidence_level": "E4"}) + "\n---\n\n" + body,
            encoding="utf-8",
        )
        e4 = score_lesson(lesson)
    finally:
        lesson.unlink(missing_ok=True)

    assert e0["evidence_level"] == "E0"
    assert e4["evidence_level"] == "E4"
    # Quality is unchanged — only trust moves, so the CI threshold keeps its meaning.
    assert e0["score"] == e4["score"]
    assert e4["trust_score"] > e0["trust_score"]


def test_search_page_shows_the_badge_and_defaults_to_e0():
    html = (REPO_ROOT / "docs" / "search" / "index.html").read_text(encoding="utf-8")
    assert "badge-evidence" in html
    assert "function evidenceInfo(" in html
    assert "EVIDENCE_LABELS[key] ? key : 'E0'" in html
    for level in EVIDENCE_LEVELS:
        assert f"{level}:" in html


def test_lesson_pages_show_the_level():
    source = (REPO_ROOT / "scripts" / "build_lesson_pages.py").read_text(encoding="utf-8")
    assert "describe(lesson.get(\"evidence_level\"))" in source
    assert "Evidence {evidence[" in source


def test_docs_define_the_promotion_rules():
    doc = (REPO_ROOT / "docs" / "trust-semantics.md").read_text(encoding="utf-8")
    for level in EVIDENCE_LEVELS:
        assert f"**{level}**" in doc
    for phrase in ("Promotion rules", "trust_score", "Default is E0"):
        assert phrase in doc
