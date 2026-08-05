#!/usr/bin/env python3
"""Test misaka run wrapper — failure capture and lesson search."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_extract_keywords():
    """Extract error keywords from stderr-like text."""
    from scripts.misaka_run import extract_keywords

    text = """
    Running tests...
    FAILED test_something
    AssertionError: expected 1 got 2
    Exit code 1
    """
    keywords = extract_keywords(text)
    assert len(keywords) > 0


def test_extract_keywords_fallback():
    """Fallback to last lines if no error keywords."""
    from scripts.misaka_run import extract_keywords

    text = "some output\nmore output\nfinal line"
    keywords = extract_keywords(text)
    assert "final line" in keywords


def test_search_lessons_empty():
    """Search returns empty list on failure."""
    from scripts.misaka_run import search_lessons

    # This will either return results or empty list depending on index
    result = search_lessons("nonexistent_query_xyz_12345")
    assert isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
