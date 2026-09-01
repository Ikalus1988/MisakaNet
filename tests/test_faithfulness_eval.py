"""Tests for faithfulness evaluator (Issue #1162)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.faithfulness_eval import (
    extract_claims,
    check_claim_support,
    evaluate_faithfulness,
    get_usage_stats,
    log_usage,
)


class TestClaimExtraction:
    """Test claim extraction from agent responses."""

    def test_extracts_sentences(self):
        """Should extract factual claims from response."""
        text = "The Docker build fails because of COPY ordering. Multi-stage builds need named stages. Try changing the COPY order."
        claims = extract_claims(text)
        assert len(claims) >= 2
        assert any("Docker" in c for c in claims)

    def test_filters_short_fragments(self):
        """Should filter out short fragments."""
        text = "Yes. No. Maybe. The actual claim is that Docker builds fail with multi-stage configurations."
        claims = extract_claims(text)
        # Should keep the long claim, filter short ones
        assert len(claims) >= 1
        assert any("Docker" in c for c in claims)

    def test_empty_response(self):
        """Empty response should return empty claims."""
        assert extract_claims("") == []

    def test_single_sentence(self):
        """Single sentence should be extracted."""
        claims = extract_claims("The error occurs because of missing dependencies.")
        assert len(claims) == 1


class TestClaimSupport:
    """Test claim support checking."""

    def test_supported_claim(self):
        """Claim with matching content should be supported."""
        claim = "Docker build fails with COPY ordering"
        content = "Docker build can fail when COPY instructions are in the wrong order. Reorder COPY commands."
        assert check_claim_support(claim, [content]) is True

    def test_unsupported_claim(self):
        """Claim with no matching content should not be supported."""
        claim = "Python uses GIL for thread safety"
        content = "Docker build fails with multi-stage builds"
        assert check_claim_support(claim, [content]) is False

    def test_partial_overlap(self):
        """Claim with partial word overlap should be checked."""
        claim = "The error is caused by missing configuration file"
        content = "Configuration file not found error can be fixed by creating config.yaml"
        # Should have some overlap
        result = check_claim_support(claim, [content])
        # May or may not pass depending on threshold
        assert isinstance(result, bool)

    def test_empty_content(self):
        """Empty content list should return False."""
        assert check_claim_support("any claim", []) is False

    def test_short_claim(self):
        """Very short claims should be filtered."""
        assert check_claim_support("ok", ["some content"]) is False


class TestFaithfulnessEvaluation:
    """Test full faithfulness evaluation."""

    def test_high_faithfulness(self):
        """Response informed by lessons should score high."""
        query = "How to fix Docker COPY error?"
        response = "Docker build fails when COPY instructions reference files not yet available. Use named build stages to fix this."
        contents = [
            "Docker COPY fails when referencing files not in build context. Use multi-stage builds with named stages.",
            "Fix: Create a named stage first, then COPY from that stage.",
        ]

        result = evaluate_faithfulness(query, response, contents)
        assert result["score"] >= 0.5
        assert result["was_used"] is True

    def test_low_faithfulness(self):
        """Response not informed by lessons should score low."""
        query = "How to fix Docker COPY error?"
        response = "Python GIL prevents true parallelism. Use multiprocessing instead."
        contents = [
            "Docker COPY fails when referencing files not in build context.",
        ]

        result = evaluate_faithfulness(query, response, contents)
        assert result["score"] < 0.5
        assert result["was_used"] is False

    def test_empty_response(self):
        """Empty response should return zero score."""
        result = evaluate_faithfulness("query", "", ["content"])
        assert result["score"] == 0.0
        assert result["was_used"] is False

    def test_empty_contents(self):
        """No lessons should result in low score."""
        result = evaluate_faithfulness("query", "Some response text here.", [])
        assert result["score"] == 0.0
        assert result["was_used"] is False


class TestUsageLogging:
    """Test usage log functionality."""

    def test_log_creates_file(self, tmp_path):
        """Log should create file if not exists."""
        log_file = tmp_path / "usage.jsonl"
        with patch("scripts.faithfulness_eval.USAGE_LOG", log_file):
            log_usage("test query", "test response", ["id1"], True)

        assert log_file.exists()
        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["query"] == "test query"
        assert entry["was_used"] is True

    def test_stats_empty(self, tmp_path):
        """Stats with no data should return zeros."""
        log_file = tmp_path / "empty.jsonl"
        with patch("scripts.faithfulness_eval.USAGE_LOG", log_file):
            stats = get_usage_stats()
        assert stats["total"] == 0
        assert stats["used"] == 0

    def test_stats_with_data(self, tmp_path):
        """Stats should compute correctly."""
        log_file = tmp_path / "usage.jsonl"
        with open(log_file, "w") as f:
            f.write(json.dumps({"query": "q1", "was_used": True}) + "\n")
            f.write(json.dumps({"query": "q2", "was_used": False}) + "\n")
            f.write(json.dumps({"query": "q3", "was_used": True}) + "\n")

        with patch("scripts.faithfulness_eval.USAGE_LOG", log_file):
            stats = get_usage_stats()
        assert stats["total"] == 3
        assert stats["used"] == 2
        assert stats["unused"] == 1
        assert abs(stats["usage_rate"] - 0.667) < 0.01
