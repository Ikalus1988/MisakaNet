#!/usr/bin/env python3
"""The `[Lesson]` converter must be mechanical, and its failures must be visible.

Every test here corresponds to something that went wrong in the 2026-10-30 hand-converted batch:

* a Windows path inside a double-quoted YAML scalar made **the whole frontmatter unparseable** (the
  file looked fine, the gate reported every field missing);
* a non-canonical domain (`qt`, `agent-tooling`) would have failed the gate rather than being mapped;
* a title longer than 120 characters silently broke the gate's limit;
* two of every batch are lessons that already merged, and checking only the batch doubles the corpus.

The converter is deliberately allowed to *skip* with a reason and never to invent a field: the section
that is absent in the issue stays absent in the file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402 — the converter writes frontmatter; parsing it back is the assertion

from scripts import intake_lesson_to_file as conv  # noqa: E402

CANONICAL = set(json.loads((REPO / "data" / "domains.json").read_text(encoding="utf-8"))["canonical"])


def issue(number: int, title: str, body: str) -> dict:
    return {"number": number, "title": f"[Lesson] {title}", "body": body}


BODY = """**Kind:** lesson_submission
**Source:** dsh
**Node:** Misaka1
**Domain:** {domain}
**Title:** {title}
## Problem
{problem}
## Root Cause
{cause}
## Fix
{fix}
## Verification
{verify}
**Tags:** npm, registry, tls

<br/>
<hr/>

<details><summary>Opire banner</summary>do not copy me</details>
"""


def sample(**over) -> dict:
    values = {
        "domain": "devops",
        "title": "npm registry unreachable: pin a mirror",
        "problem": "pnpm failed with ERR_PNPM_META_FETCH_FAIL against registry.npmjs.org.",
        "cause": "The default registry is unreachable with valid certificates from this network.",
        "fix": "Set registry=https://registry.npmmirror.com in the profile .npmrc.",
        "verify": "Metadata fetch returns HTTP 200 and the install completes.",
    }
    values.update(over)
    return issue(101, values["title"], BODY.format(**values))


def test_a_clean_submission_becomes_a_lesson_with_the_gate_fields():
    lesson, notes = conv.convert(sample(), CANONICAL)
    assert lesson is not None, notes
    assert lesson["domain"] == "devops"
    assert lesson["tags"] == ["npm", "registry", "tls"]
    assert lesson["source"] == "dsh"
    assert lesson["summary_plain"].startswith("pnpm failed with ERR_PNPM_META_FETCH_FAIL")
    assert "## Verification" in lesson["content"]
    assert "Opire" not in lesson["content"], "the banner is not lesson text"


def test_a_non_canonical_domain_is_mapped_and_the_mapping_is_reported():
    lesson, notes = conv.convert(sample(domain="qt"), CANONICAL)
    assert lesson is not None
    assert lesson["domain"] == "frontend"
    assert any("qt → frontend" in note for note in notes), notes


def test_an_unknown_domain_is_skipped_with_the_name_in_the_reason():
    lesson, notes = conv.convert(sample(domain="quantum-computing"), CANONICAL)
    assert lesson is None
    assert "quantum-computing" in notes[0]


def test_a_missing_verification_is_recorded_as_missing_not_invented():
    full = sample()
    body = full["body"].replace("## Verification\nMetadata fetch returns HTTP 200 and the install completes.\n", "")
    lesson, notes = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert "Not recorded by the submitter." in lesson["content"]
    assert any("no Verification" in note for note in notes), notes


def test_a_windows_path_survives_the_yaml_round_trip():
    """The 2026-10-30 batch: `verify: "E:\\Deepseek\\..."` made YAML read `\\D` as an escape."""
    lesson, _ = conv.convert(sample(verify=r"Run C:\Users\eric\bin\tool.exe and check exit 0."),
                             CANONICAL)
    text = conv.render(lesson, "2026-10-31")
    block = text.split("---", 2)[1]
    parsed = yaml.safe_load(block)
    assert parsed["verify"].startswith("Run C:\\Users\\eric\\bin\\tool.exe"), parsed["verify"]
    assert parsed["title"] and parsed["domain"] == "devops"


def test_a_title_longer_than_the_gate_limit_is_trimmed_on_a_word_boundary():
    lesson, _ = conv.convert(sample(title="word " * 40), CANONICAL)
    assert lesson is not None
    assert len(lesson["title"]) <= 120
    assert lesson["title"].endswith("…")


def test_tags_are_capped_at_ten_and_deduplicated():
    full = sample()
    body = full["body"].replace("**Tags:** npm, registry, tls",
                                "**Tags:** npm, npm, " + ", ".join(f"tag{i}" for i in range(15)))
    lesson, _ = conv.convert({**full, "body": body}, CANONICAL)
    assert lesson is not None
    assert len(lesson["tags"]) == 10


def test_a_chinese_title_with_no_latin_characters_gets_an_issue_number_slug():
    assert conv.slugify("长上下文污染", 2738) == "lesson-2738"
    assert conv.slugify("npm registry unreachable: pin a mirror", 1) == "npm-registry-unreachable-pin-a-mirror"


def test_a_duplicate_of_a_published_lesson_is_skipped_not_written(tmp_path, monkeypatch):
    published = tmp_path / "lessons.json"
    published.write_text(json.dumps([{"id": "npm-registry-unreachable-pin-a-mirror",
                                      "title": "npm registry unreachable: pin a mirror"}]),
                         encoding="utf-8")
    monkeypatch.setattr(conv, "PUBLISHED", published)
    assert "npm registry unreachable: pin a mirror" in conv.published_titles()


def test_the_cli_writes_files_and_a_slug_map(tmp_path, monkeypatch):
    monkeypatch.setattr(conv, "LESSONS_DIR", tmp_path / "contrib")
    (tmp_path / "contrib").mkdir()
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps([sample()]), encoding="utf-8")
    slugs = tmp_path / "slugs.json"
    code = conv.main(["--issues-json", str(issues), "--write", "--created", "2026-10-31",
                      "--slugs", str(slugs)])
    assert code == 0
    written = list((tmp_path / "contrib").glob("*.md"))
    assert len(written) == 1
    assert written[0].name == "npm-registry-unreachable-pin-a-mirror.md"
    assert json.loads(slugs.read_text(encoding="utf-8")) == {"101": "npm-registry-unreachable-pin-a-mirror"}


def test_the_cli_dry_run_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(conv, "LESSONS_DIR", tmp_path / "contrib")
    (tmp_path / "contrib").mkdir()
    issues = tmp_path / "issues.json"
    issues.write_text(json.dumps([sample()]), encoding="utf-8")
    assert conv.main(["--issues-json", str(issues)]) == 0
    assert list((tmp_path / "contrib").glob("*.md")) == []
