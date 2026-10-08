#!/usr/bin/env python3
"""Tests for the MisakaNet artifact validator."""

import pytest
import tempfile
import os
from pathlib import Path
from scripts.validate import (
    ArtifactResult,
    collect_artifacts,
    extract_date_field,
    main,
    parse_date,
    parse_frontmatter,
    summarize,
    validate_artifact,
)


SAMPLE_FRESH = """---
date: 2026-07-01
title: Fresh doc
---
Body content here.
"""

SAMPLE_STALE_UNACKNOWLEDGED = """---
date: 2025-01-01
title: Stale doc
---
This is old.
"""

SAMPLE_STALE_ACKNOWLEDGED = """---
date: 2025-01-01
needs_reverify: true
title: Stale acknowledged doc
---
Acknowledged debt.
"""

SAMPLE_NO_DATE = """---
title: No date doc
---
Nothing here.
"""


class TestFrontmatterParsing:
    def test_basic_frontmatter(self):
        fm, body = parse_frontmatter(SAMPLE_FRESH)
        assert fm is not None
        assert fm["date"] == "2026-07-01"
        assert fm["title"] == "Fresh doc"
        assert "Body content here." in body

    def test_no_frontmatter(self):
        fm, body = parse_frontmatter("Just plain text\n")
        assert fm is None
        assert body.strip() == "Just plain text"

    def test_multiline_value(self):
        text = "key: val1\n  val2\n"
        fm, _ = parse_frontmatter(text)
        assert fm is not None
        assert "val1 val2" in fm.get("key", "")


class TestDateParsing:
    def test_iso_date(self):
        assert parse_date("2025-03-15") is not None

    def test_iso_with_time(self):
        dt = parse_date("2025-03-15T10:30:00")
        assert dt is not None
        assert dt.hour == 10

    def test_invalid_date(self):
        assert parse_date("not-a-date") is None


class TestExtractDateField:
    def test_finds_date(self):
        assert extract_date_field({"date": "2026-01-01"}) == "2026-01-01"

    def test_fallback_to_last_verified(self):
        assert extract_date_field({"last_verified": "2026-01-01"}) == "2026-01-01"

    def test_none(self):
        assert extract_date_field({}) is None


class TestValidateArtifact:
    def test_fresh_artifact(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text(SAMPLE_FRESH)
        r = validate_artifact(p, stale_threshold_days=90, strict=False, enforce_evidence=False)
        assert not r.stale
        assert not r.acknowledged

    def test_stale_unacknowledged(self, tmp_path):
        p = tmp_path / "old.md"
        p.write_text(SAMPLE_STALE_UNACKNOWLEDGED)
        r = validate_artifact(p, stale_threshold_days=90, strict=False, enforce_evidence=False)
        assert r.stale
        assert not r.acknowledged
        assert any("acknowledge" in w.lower() for w in r.warnings)

    def test_stale_acknowledged(self, tmp_path):
        p = tmp_path / "old-ack.md"
        p.write_text(SAMPLE_STALE_ACKNOWLEDGED)
        r = validate_artifact(p, stale_threshold_days=90, strict=False, enforce_evidence=False)
        assert r.stale
        assert r.acknowledged
        assert any("acknowledged" in w.lower() for w in r.warnings)

    def test_no_date(self, tmp_path):
        p = tmp_path / "nodate.md"
        p.write_text(SAMPLE_NO_DATE)
        r = validate_artifact(p, stale_threshold_days=90, strict=False, enforce_evidence=False)
        assert not r.stale

    def test_enforce_evidence_marks_unacknowledged_stale(self, tmp_path):
        p = tmp_path / "old.md"
        p.write_text(SAMPLE_STALE_UNACKNOWLEDGED)
        r = validate_artifact(p, stale_threshold_days=90, strict=False, enforce_evidence=True)
        assert r.stale
        assert not r.acknowledged
        assert any("missing" in w.lower() for w in r.warnings)

    def test_dates_untouched(self, tmp_path):
        p = tmp_path / "old.md"
        original = SAMPLE_STALE_UNACKNOWLEDGED
        p.write_text(original)
        validate_artifact(p, stale_threshold_days=90, strict=False, enforce_evidence=False)
        assert p.read_text() == original


class TestSummarize:
    def test_empty(self):
        assert summarize([]) == "fresh=0 stale=0 (acknowledged=0)"

    def test_mixed(self):
        fresh = ArtifactResult(path="a", date_field="", age_days=10, stale=False)
        stale_u = ArtifactResult(path="b", date_field="", age_days=100, stale=True, acknowledged=False)
        stale_a = ArtifactResult(path="c", date_field="", age_days=100, stale=True, acknowledged=True)
        assert summarize([fresh, stale_u, stale_a]) == "fresh=1 stale=1 (acknowledged=1)"


class TestMainStrictMode:
    def test_strict_passes_with_fresh(self, tmp_path):
        p = tmp_path / "fresh.md"
        p.write_text(SAMPLE_FRESH)
        rc = main(["--root", str(tmp_path), "--strict", "--stale-days", "90"])
        assert rc == 0

    def test_strict_fails_with_unacknowledged_stale(self, tmp_path):
        p = tmp_path / "old.md"
        p.write_text(SAMPLE_STALE_UNACKNOWLEDGED)
        rc = main(["--root", str(tmp_path), "--strict", "--stale-days", "90"])
        assert rc == 1

    def test_strict_passes_with_acknowledged_stale(self, tmp_path):
        p = tmp_path / "old-ack.md"
        p.write_text(SAMPLE_STALE_ACKNOWLEDGED)
        rc = main(["--root", str(tmp_path), "--strict", "--stale-days", "90"])
        assert rc == 0

    def test_summary_line(self, tmp_path, capsys):
        p1 = tmp_path / "fresh.md"
        p1.write_text(SAMPLE_FRESH)
        p2 = tmp_path / "old.md"
        p2.write_text(SAMPLE_STALE_UNACKNOWLEDGED)
        p3 = tmp_path / "old-ack.md"
        p3.write_text(SAMPLE_STALE_ACKNOWLEDGED)
        main(["--root", str(tmp_path), "--stale-days", "90"])
        captured = capsys.readouterr()
        assert "fresh=1 stale=1 (acknowledged=1)" in captured.out
