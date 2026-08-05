"""Tests for #314: Typo tolerance with edit distance ≤2."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from search_knowledge import _edit_distance, _typo_retry_search


# ── Edit distance ──


def test_edit_distance_identical():
    assert _edit_distance("hello", "hello") == 0


def test_edit_distance_single_substitution():
    assert _edit_distance("timout", "timeout") == 1


def test_edit_distance_single_insertion():
    assert _edit_distance("timeout", "timout") == 1


def test_edit_distance_single_deletion():
    assert _edit_distance("timout", "timeout") == 1


def test_edit_distance_two_edits():
    assert _edit_distance("timot", "timeout") == 2


def test_edit_distance_beyond_threshold():
    assert _edit_distance("abc", "xyz") == 3


def test_edit_distance_empty():
    assert _edit_distance("", "hello") == 5
    assert _edit_distance("hello", "") == 5
    assert _edit_distance("", "") == 0


# ── Typo retry search ──


class FakeDoc:
    def __init__(self, title, content="", domain="", status="published"):
        self.title = title
        self.content = content
        self.domain = domain
        self.status = status
        self.filename = title.replace(" ", "_") + ".md"
        self.filepath = Path(f"lessons/{self.filename}")
        self.tags = []
        self.language = ""
        self.reference = ""
        self.scope = ""
        self.source = ""
        self.is_lesson = True
        self.mtime = 0.0

    @property
    def is_draft(self):
        return self.status == "draft"

    @property
    def score_baseline(self):
        return 0.0 if self.is_draft else 0.1


def test_typo_retry_finds_correction():
    docs = [
        FakeDoc("pip install timeout fix", "pip install network timeout error fix"),
        FakeDoc("SSL certificate error", "SSL certificate verification failed"),
        FakeDoc("proxy configuration", "HTTP proxy setup guide"),
    ]
    results, corrected = _typo_retry_search("timout", docs, False, False, 10)
    assert len(results) > 0
    assert "timeout" in corrected


def test_typo_retry_no_correction_needed():
    docs = [
        FakeDoc("pip install timeout fix", "pip install network timeout error fix"),
    ]
    results, corrected = _typo_retry_search("timeout", docs, False, False, 10)
    # "timeout" is already in vocab, no correction needed
    assert results == []


def test_typo_retry_empty_query():
    results, corrected = _typo_retry_search("", [], False, False, 10)
    assert results == []


def test_typo_retry_no_match():
    docs = [
        FakeDoc("completely unrelated topic", "nothing here"),
    ]
    results, corrected = _typo_retry_search("zzzzz", docs, False, False, 10)
    assert results == []
