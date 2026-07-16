"""Tests for #481: Retrieval NoiseBench metrics."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.retrieval_noisebench import (
    _forbidden_hit_rate,
    _mrr,
    _precision_at_k,
)


# ── Precision@K ──


def test_precision_at_k_all_relevant():
    assert _precision_at_k(["a", "b", "c"], {"a", "b", "c"}, 3) == 1.0


def test_precision_at_k_none_relevant():
    assert _precision_at_k(["x", "y", "z"], {"a", "b"}, 3) == 0.0


def test_precision_at_k_partial():
    assert _precision_at_k(["a", "x", "b"], {"a", "b"}, 3) == pytest.approx(2 / 3)


def test_precision_at_k_k1():
    assert _precision_at_k(["a", "x", "y"], {"a"}, 1) == 1.0
    assert _precision_at_k(["x", "a", "y"], {"a"}, 1) == 0.0


def test_precision_at_k_empty():
    assert _precision_at_k([], {"a"}, 3) == 0.0


# ── MRR ──


def test_mrr_first():
    assert _mrr(["a", "b", "c"], {"a"}) == 1.0


def test_mrr_second():
    assert _mrr(["x", "a", "c"], {"a"}) == 0.5


def test_mrr_third():
    assert _mrr(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3)


def test_mrr_none():
    assert _mrr(["x", "y", "z"], {"a"}) == 0.0


def test_mrr_multiple_relevant():
    # Should return 1/rank of FIRST relevant
    assert _mrr(["x", "a", "b"], {"a", "b"}) == 0.5


# ── Forbidden Hit Rate ──


def test_forbidden_none():
    assert _forbidden_hit_rate(["a", "b", "c"], {"x"}, 3) == 0.0


def test_forbidden_one():
    assert _forbidden_hit_rate(["a", "x", "b"], {"x"}, 3) == pytest.approx(1 / 3)


def test_forbidden_multiple():
    assert _forbidden_hit_rate(["x", "y", "z"], {"x", "y", "z"}, 3) == 1.0


def test_forbidden_empty():
    assert _forbidden_hit_rate(["a", "b"], set(), 3) == 0.0
