#!/usr/bin/env python3
"""The displayed search score is relative to its own result set, not a match quality (#2790).

Two "retrieval quality" readings have been in open disagreement since §86.4: the CLI prints a
percentage that sits at 90–98% for the top hits, and the worker-side evaluation reports 12–19 for
relevant and 2–4 for irrelevant. §86.4 recorded that #2790 "must reconcile the two readings".

They are not in conflict — they are on different scales. `_normalize` is min–max, so the CLI's
number is a **position within the returned set**: the best of *any* set normalises to 100%,
including a set where every candidate is a bad match. That is the whole reason a "98%" top hit
carried no information about coverage in the subagent reports §86.4 examined.

This file pins the property, because it is invisible in the output and is exactly what a reader
would otherwise re-derive wrongly.
"""
from __future__ import annotations

from misakanet.search.engine import _normalize


def test_the_best_hit_normalizes_to_one_even_when_every_hit_is_bad():
    """The load-bearing consequence: a query with no good answer still shows its best hit at 100%."""
    assert _normalize([3.0, 2.0, 1.0])[0] == 1.0


def test_a_strong_match_and_a_weak_one_reach_the_same_number():
    """Same 1.0 for a query with a real answer and one without — so the number cannot rank queries."""
    assert _normalize([30.0, 2.0, 1.0])[0] == _normalize([3.0, 2.0, 1.0])[0] == 1.0


def test_the_worst_hit_is_zero_and_the_shape_is_monotone():
    out = _normalize([3.0, 2.0, 1.0])
    assert out == [1.0, 0.5, 0.0]


def test_all_zero_stays_zero_so_the_caller_can_still_detect_no_results():
    """The threshold that decides `no_match` depends on this, so it is not merely cosmetic."""
    assert _normalize([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]


def test_a_flat_non_zero_vector_gets_the_neutral_half():
    assert _normalize([2.0, 2.0]) == [0.5, 0.5]
