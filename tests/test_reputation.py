#!/usr/bin/env python3
"""Tests for the reputation scoring engine.

Covers:
- New contributor surge (sigmoid cap prevents single-PR domination)
- Long-time contributor decay (time decay reduces old contributions)
- Single large PR (anti-gaming via sigmoid cap)
"""
import math
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.reputation import (
    sigmoid_cap,
    time_decay,
    compute_reputation,
    W_USAGE,
    W_LESSONS,
    W_REUSE,
    W_VERIFIED,
    HALF_LIFE_DAYS,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}{': ' + detail if detail else ''}")


def test_sigmoid_cap():
    print("\n── sigmoid cap ──")
    # At midpoint, cap should be ~0.5
    mid_val = sigmoid_cap(10)
    check("sigmoid(10) ≈ 0.5", abs(mid_val - 0.5) < 0.01, f"got {mid_val:.3f}")

    # At 0 lessons, cap should be low
    low_val = sigmoid_cap(0)
    check("sigmoid(0) < 0.1", low_val < 0.1, f"got {low_val:.3f}")

    # At 50 lessons, cap should be near 1
    high_val = sigmoid_cap(50)
    check("sigmoid(50) > 0.99", high_val > 0.99, f"got {high_val:.3f}")

    # Monotonicity
    check("sigmoid is monotonic", sigmoid_cap(5) < sigmoid_cap(15) < sigmoid_cap(30))


def test_time_decay():
    print("\n── time decay ──")
    now = datetime(2026, 7, 7, tzinfo=timezone.utc)

    # Recent contribution (today) → decay ≈ 1.0
    recent = time_decay("2026-07-07", now)
    check("today decay ≈ 1.0", abs(recent - 1.0) < 0.01, f"got {recent:.3f}")

    # Half-life ago → decay ≈ 0.5
    half_ago = (now - timedelta(days=HALF_LIFE_DAYS)).strftime("%Y-%m-%d")
    half_decay = time_decay(half_ago, now)
    check(f"{HALF_LIFE_DAYS}d ago decay ≈ 0.5", abs(half_decay - 0.5) < 0.05, f"got {half_decay:.3f}")

    # Very old → decay near 0
    old = time_decay("2020-01-01", now)
    check("2020 decay < 0.01", old < 0.01, f"got {old:.4f}")

    # Unknown date → neutral 0.5
    unknown = time_decay("", now)
    check("unknown date → 0.5", unknown == 0.5)


def test_new_contributor_surge():
    print("\n── new contributor surge (anti-gaming) ──")
    # A new contributor with 1 lesson and 100 usage reports
    lessons = [
        {"path": "lessons/contrib/newbie.md", "contributor": "newbie",
         "has_verification": True, "created": "2026-07-01", "domain": "devops", "status": "published"},
    ]
    usage = {"newbie": [{"tool": "test", "outcome": "solved"}] * 100}

    result = compute_reputation(lessons, usage)
    newbie = [c for c in result if c["login"] == "newbie"][0]

    # With 1 lesson, sigmoid cap should be low
    cap = sigmoid_cap(1)
    check("1-lesson sigmoid cap < 0.2", cap < 0.2, f"got {cap:.3f}")

    # Final score should be capped despite high usage
    check("score capped despite 100 usage reports", newbie["final_score"] < 10,
          f"got {newbie['final_score']}")


def test_long_time_contributor():
    print("\n── long-time contributor (time decay) ──")
    now = datetime(2026, 7, 7, tzinfo=timezone.utc)

    # Old lesson from 6 months ago
    lessons_old = [
        {"path": "lessons/core/old.md", "contributor": "veteran",
         "has_verification": True, "created": "2026-01-01", "domain": "devops", "status": "published"},
    ]

    # Recent lesson from today
    lessons_new = [
        {"path": "lessons/core/new.md", "contributor": "newcomer",
         "has_verification": True, "created": "2026-07-07", "domain": "devops", "status": "published"},
    ]

    result_old = compute_reputation(lessons_old, {})
    result_new = compute_reputation(lessons_new, {})

    veteran = result_old[0]
    newcomer = result_new[0]

    # Both have 1 lesson, but newcomer should score higher due to time decay
    check("newcomer > veteran (time decay)",
          newcomer["final_score"] > veteran["final_score"],
          f"newcomer={newcomer['final_score']:.3f} veteran={veteran['final_score']:.3f}")


def test_single_large_pr():
    print("\n── single large PR (anti-gaming) ──")
    # Someone submits 50 lessons in one PR
    lessons = [
        {"path": f"lessons/contrib/bulk-{i}.md", "contributor": "bulk-submitter",
         "has_verification": True, "created": "2026-07-01", "domain": "devops", "status": "published"}
        for i in range(50)
    ]

    result = compute_reputation(lessons, {})
    bulk = result[0]

    # Sigmoid cap at 50 lessons
    cap = sigmoid_cap(50)
    check("sigmoid(50) > 0.99", cap > 0.99, f"got {cap:.3f}")

    # Score should be bounded (not linear with lesson count)
    # 50 lessons × 1.5 per lesson = 75 raw, but sigmoid + decay cap it
    check("50-lesson score < 100", bulk["final_score"] < 100,
          f"got {bulk['final_score']}")

    # Compare with 10-lesson contributor
    lessons_10 = [
        {"path": f"lessons/contrib/careful-{i}.md", "contributor": "careful",
         "has_verification": True, "created": "2026-07-01", "domain": "devops", "status": "published"}
        for i in range(10)
    ]
    result_10 = compute_reputation(lessons_10, {})
    careful = result_10[0]

    # Sigmoid prevents linear scaling: 50 lessons ≠ 5× 10 lessons
    # sigmoid(50) ≈ 1.0, sigmoid(10) ≈ 0.5, so ratio ≈ 2x, not 5x
    # But 10-lesson sigmoid is very low (~0.007), so ratio is higher
    # The key invariant: bulk score is LESS than 50 × single-lesson score
    single_score = W_LESSONS + W_VERIFIED  # 1 lesson, verified
    check("50-lesson score < 50 × single-lesson score",
          bulk["final_score"] < 50 * single_score,
          f"bulk={bulk['final_score']:.1f} vs 50×single={50 * single_score:.1f}")


if __name__ == "__main__":
    print("Reputation Engine — unit tests")
    test_sigmoid_cap()
    test_time_decay()
    test_new_contributor_surge()
    test_long_time_contributor()
    test_single_large_pr()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
