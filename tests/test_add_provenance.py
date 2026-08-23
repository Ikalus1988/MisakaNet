"""Tests for add_provenance.py (Issue #1219)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.add_provenance import (
    parse_frontmatter,
    has_provenance_section,
    add_provenance,
    extract_domain_from_path,
    guess_contributor,
)


def test_parse_frontmatter():
    """Test frontmatter parsing."""
    content = """---
title: "Test Lesson"
domain: "devops"
tags:
  - ci
  - github
status: "published"
---

# Content here
"""
    frontmatter, body = parse_frontmatter(content)
    assert frontmatter.get("title") == '"Test Lesson"'
    assert frontmatter.get("domain") == '"devops"'


def test_has_provenance_section():
    """Test provenance detection."""
    with_provenance = """---
title: "Test"
provenance:
  source: "internal"
---
"""
    without_provenance = """---
title: "Test"
---
"""

    assert has_provenance_section(with_provenance) is True
    assert has_provenance_section(without_provenance) is False


def test_add_provenance():
    """Test adding provenance to content."""
    content = """---
title: "Test Lesson"
---

# Content
"""
    result = add_provenance(content, "TestContributor", "internal")
    assert "provenance:" in result
    assert "TestContributor" in result
    assert "internal" in result
    assert "title: \"Test Lesson\"" in result


def test_add_provenance_no_frontmatter():
    """Test adding provenance to content without frontmatter."""
    content = "# Simple Content\n\nSome text."
    result = add_provenance(content, "Contributor", "community")
    assert result.startswith("---")
    assert "provenance:" in result
    assert "Simple Content" in result


def test_extract_domain():
    """Test domain extraction from path."""
    from scripts.add_provenance import LESSONS_DIR
    path = LESSONS_DIR / "contrib" / "lesson.md"
    assert extract_domain_from_path(path) == "contrib"

    path = LESSONS_DIR / "devops" / "lesson.md"
    assert extract_domain_from_path(path) == "devops"


def test_guess_contributor():
    """Test contributor guessing."""
    from scripts.add_provenance import LESSONS_DIR
    # From contributor field
    assert guess_contributor({"contributor": "TestNode"}, Path("test.md")) == "TestNode"

    # From title pattern
    assert guess_contributor({"title": "Misaka10018 fix"}, Path("test.md")) == "Misaka10018"

    # Default for contrib
    assert guess_contributor({}, LESSONS_DIR / "contrib" / "test.md") == "Community"


if __name__ == "__main__":
    test_parse_frontmatter()
    test_has_provenance_section()
    test_add_provenance()
    test_add_provenance_no_frontmatter()
    test_extract_domain()
    test_guess_contributor()
    print("All tests passed ✓")
