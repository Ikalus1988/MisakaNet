import pytest
import os
import sys
from pathlib import Path

# Add the project root to the path to allow imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from search_knowledge import bm25_search, parse_query

# Fixture data directory
FIXTURES_DIR = project_root / "tests" / "fixtures"

@pytest.fixture
def sample_documents():
    """Load sample documents for testing."""
    # In a real scenario, this might load from a JSON file or DB
    # For this test, we define a static set of documents
    return [
        {"id": "1", "content": "Python is a great programming language."},
        {"id": "2", "content": "Solidity is used for smart contracts."},
        {"id": "3", "content": "JavaScript powers the web."},
        {"id": "4", "content": "Edge cases are important for robust software."},
        {"id": "5", "content": "Unit tests ensure code quality."},
    ]

def test_empty_query_string(sample_documents):
    """Test behavior when query string is empty."""
    # parse_query should return an empty list or handle gracefully
    parsed = parse_query("")
    assert parsed == []
    
    # bm25_search should return empty results or handle gracefully
    results = bm25_search(sample_documents, "")
    assert results == []

def test_special_characters_in_query(sample_documents):
    """Test handling of special characters in query."""
    special_queries = [
        "!!!",
        "@#$%",
        "test<>script",
        "query with (parentheses)",
        "query with [brackets]",
        "query with {braces}",
        "query with | pipe",
        "query with & ampersand",
        "query with * asterisk",
        "query with ? question",
    ]
    
    for query in special_queries:
        # Should not raise an exception
        parsed = parse_query(query)
        # Results should be empty or contain only valid tokens if any
        results = bm25_search(sample_documents, query)
        # Just ensure no crash occurs
        assert isinstance(results, list)

def test_single_word_match(sample_documents):
    """Test matching with a single word query."""
    test_cases = [
        ("Python", ["1"]),
        ("Solidity", ["2"]),
        ("JavaScript", ["3"]),
        ("Edge", ["4"]),
        ("tests", ["5"]),
    ]
    
    for query, expected_ids in test_cases:
        results = bm25_search(sample_documents, query)
        result_ids = [r["id"] for r in results]
        # Check that the expected document is in results
        for expected_id in expected_ids:
            assert expected_id in result_ids

def test_extremely_long_query(sample_documents):
    """Test handling of extremely long query (>500 chars)."""
    # Create a query longer than 500 characters
    long_word = "a" * 100
    long_query = f"{long_word} {long_word} {long_word} {long_word} {long_word} {long_word}"
    assert len(long_query) > 500
    
    # Should not raise an exception
    parsed = parse_query(long_query)
    results = bm25_search(sample_documents, long_query)
    
    # Should return a list (possibly empty if no matches)
    assert isinstance(results, list)

def test_mixed_case_query(sample_documents):
    """Test that queries are case-insensitive."""
    results_lower = bm25_search(sample_documents, "python")
    results_upper = bm25_search(sample_documents, "PYTHON")
    results_mixed = bm25_search(sample_documents, "PyThOn")
    
    # All should return the same results
    assert len(results_lower) == len(results_upper) == len(results_mixed)
    if results_lower:
        assert results_lower[0]["id"] == results_upper[0]["id"] == results_mixed[0]["id"]

def test_query_with_extra_whitespace(sample_documents):
    """Test handling of queries with extra whitespace."""
    query_with_spaces = "   python   is   great   "
    query_normal = "python is great"
    
    results_spaces = bm25_search(sample_documents, query_with_spaces)
    results_normal = bm25_search(sample_documents, query_normal)
    
    # Should return same results
    assert len(results_spaces) == len(results_normal)
    if results_spaces:
        assert results_spaces[0]["id"] == results_normal[0]["id"]