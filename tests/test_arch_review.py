"""Tests for architecture review script (Issue #1184)."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.arch_review import (
    analyze_structure,
    check_aider_available,
    generate_file_listing,
    generate_repo_map,
    ARCH_QUESTIONS,
)


class TestStructureAnalysis(unittest.TestCase):
    """Test structure analysis."""

    def test_modules_detected(self):
        """Should detect misakanet/ modules."""
        analysis = analyze_structure()
        self.assertIn("modules", analysis)
        # Should have at least a few modules
        if (Path(__file__).resolve().parent.parent / "misakanet").exists():
            self.assertGreater(len(analysis["modules"]), 0)

    def test_patterns_detected(self):
        """Should detect common patterns."""
        analysis = analyze_structure()
        self.assertIn("patterns", analysis)
        # We know these exist
        self.assertIn("has_tests", analysis["patterns"])

    def test_concerns_list(self):
        """Should list concerns (may be empty)."""
        analysis = analyze_structure()
        self.assertIn("concerns", analysis)
        self.assertIsInstance(analysis["concerns"], list)


class TestRepoMap(unittest.TestCase):
    """Test repo map generation."""

    @patch("scripts.arch_review.check_aider_available")
    def test_fallback_to_file_listing(self, mock_aider):
        """Should fall back to file listing when aider unavailable."""
        mock_aider.return_value = False
        result = generate_repo_map()
        self.assertEqual(result["source"], "file-listing")
        self.assertIn("map", result)

    def test_file_listing_contains_python_files(self):
        """File listing should include Python files."""
        listing = generate_file_listing()
        self.assertIn(".py", listing)


class TestQuestions(unittest.TestCase):
    """Test review questions."""

    def test_questions_list(self):
        """Should have multiple questions."""
        self.assertGreater(len(ARCH_QUESTIONS), 3)

    def test_questions_are_strings(self):
        """All questions should be strings."""
        for q in ARCH_QUESTIONS:
            self.assertIsInstance(q, str)
            self.assertIn("?", q)


if __name__ == "__main__":
    unittest.main()
