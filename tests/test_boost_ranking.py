"""Feature #228: Boost core/verified lessons in search ranking.

Verifies the four boost factors (core/verified/recent/draft) and their
integration with the BM25 ranking pipeline.
"""
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from misakanet.search.engine import (
    BOOST_CORE,
    BOOST_VERIFIED,
    BOOST_RECENT,
    BOOST_DRAFT,
    BOOST_RECENT_DAYS,
    CachedDoc,
    _compute_boost,
    _is_core,
    _is_verified,
    _is_recent,
    _rank_docs_impl,
)


# ── Constants exposed at module level (AC: "module-level constants") ──

def test_boost_constants_exposed():
    """All four boost values must be defined as module-level constants."""
    assert BOOST_CORE == 0.15
    assert BOOST_VERIFIED == 0.10
    assert BOOST_RECENT == 0.05
    assert BOOST_DRAFT == -0.20
    assert BOOST_RECENT_DAYS == 30


# ── Per-factor helpers ──

def _make_doc(path: str, content: str = "", status: str = "published",
              mtime: float = 0.0) -> CachedDoc:
    """Build a CachedDoc without going through disk I/O."""
    return CachedDoc(
        filename=Path(path).name,
        filepath=Path(path),
        content=content,
        mtime=mtime,
        status=status,
    )


def test_is_core_true_for_lessons_core_path():
    """AC: 'Lesson is in lessons/core/' gets core boost."""
    doc = _make_doc("lessons/core/foo.md")
    assert _is_core(doc) is True


def test_is_core_false_for_contrib_path():
    """AC: contrib lessons should NOT be marked as core."""
    doc = _make_doc("lessons/contrib/foo.md")
    assert _is_core(doc) is False


def test_is_verified_true_for_verify_section():
    """AC: 'Has ## Verify or ## Verification section' gets verified boost."""
    content = "---\ntitle: x\n---\n## Problem\n\n## Fix\n\n## Verify\nok\n"
    assert _is_verified(_make_doc("lessons/core/x.md", content)) is True


def test_is_verified_true_for_verification_section():
    """Both 'Verify' and 'Verification' section headers must trigger boost."""
    content = "---\ntitle: x\n---\n## Verification\nok\n"
    assert _is_verified(_make_doc("lessons/core/x.md", content)) is True


def test_is_verified_false_without_section():
    """A lesson missing the verify section is not verified."""
    content = "---\ntitle: x\n---\n## Problem\n\n## Fix\n"
    assert _is_verified(_make_doc("lessons/core/x.md", content)) is False


def test_is_recent_true_for_just_updated():
    """Lessons updated within 30 days are 'recent'."""
    now = time.time()
    assert _is_recent(_make_doc("lessons/core/x.md", mtime=now - 86400)) is True
    assert _is_recent(_make_doc("lessons/core/x.md", mtime=now)) is True


def test_is_recent_false_for_old_lessons():
    """Lessons older than 30 days are not recent."""
    now = time.time()
    old = now - (BOOST_RECENT_DAYS + 5) * 86400
    assert _is_recent(_make_doc("lessons/core/x.md", mtime=old)) is False


def test_is_recent_false_when_mtime_missing():
    """A zero mtime (unknown age) is treated as not-recent, not recent."""
    assert _is_recent(_make_doc("lessons/core/x.md", mtime=0.0)) is False


# ── _compute_boost: factor sum ──

def test_compute_boost_plain_doc_is_zero():
    """A non-core, non-verified, non-recent, non-draft doc has zero boost."""
    doc = _make_doc(
        "lessons/contrib/x.md",
        content="---\ntitle: x\n---\n## Problem\n",
        mtime=0.0,
        status="published",
    )
    assert _compute_boost(doc) == 0.0


def test_compute_boost_core_only():
    doc = _make_doc("lessons/core/x.md", mtime=0.0, status="published",
                    content="## Problem\n")
    assert _compute_boost(doc) == BOOST_CORE


def test_compute_boost_verified_only():
    doc = _make_doc("lessons/contrib/x.md", mtime=0.0, status="published",
                    content="## Verify\nok\n")
    assert _compute_boost(doc) == BOOST_VERIFIED


def test_compute_boost_recent_only():
    now = time.time()
    doc = _make_doc("lessons/contrib/x.md", mtime=now - 86400, status="published",
                    content="## Problem\n")
    assert _compute_boost(doc) == BOOST_RECENT


def test_compute_boost_draft_only():
    doc = _make_doc("lessons/contrib/x.md", mtime=0.0, status="draft",
                    content="## Problem\n")
    assert _compute_boost(doc) == BOOST_DRAFT


def test_compute_boost_core_verified_recent_stacks():
    """A core+verified+recent lesson stacks all three positive boosts."""
    now = time.time()
    doc = _make_doc("lessons/core/x.md", mtime=now - 86400, status="published",
                    content="## Verify\nok\n")
    expected = BOOST_CORE + BOOST_VERIFIED + BOOST_RECENT
    assert _compute_boost(doc) == expected


# ── AC: ranking integration ──

def test_rank_core_above_contrib_with_equal_bm25():
    """AC: 'Core lessons rank higher than contrib with equal BM25 scores'.

    Two lessons with the same content, only one in core/. The core lesson
    should rank above the contrib lesson.
    """
    shared = "shared keyword alpha beta gamma delta epsilon"
    now = time.time()
    core = _make_doc("lessons/core/x.md", content=shared, mtime=now, status="published")
    contrib = _make_doc("lessons/contrib/x.md", content=shared, mtime=now, status="published")
    scored = _rank_docs_impl("alpha", [contrib, core])
    # core must come first
    assert scored[0][1].filepath == core.filepath
    assert scored[0][0] > scored[1][0]


def test_rank_verified_above_unverified_with_equal_bm25():
    """AC: 'Verified lessons get a small boost over unverified'.

    Both docs have the same character count so BM25 length normalization
    can't dominate — only the verify-boost can tip the ranking.
    """
    # '## Verify' = 9 chars, '## Validation' = 14 chars; pad to match.
    verified_content = "alpha beta gamma\n## Verify\nok\npadding here ok\n"
    unverified_content = "alpha beta gamma\n## Validation\nok\npad here ok\n"
    now = time.time()
    verified = _make_doc("lessons/contrib/a.md", content=verified_content,
                         mtime=now, status="published")
    unverified = _make_doc("lessons/contrib/b.md", content=unverified_content,
                           mtime=now, status="published")
    assert len(verified.content) == len(unverified.content), (
        f"lengths must match: verified={len(verified.content)} "
        f"unverified={len(unverified.content)}"
    )
    scored = _rank_docs_impl("alpha", [unverified, verified])
    assert scored[0][1].filepath == verified.filepath
    assert scored[0][0] > scored[1][0]


def test_rank_boost_values_observable_in_score():
    """The boost must be reflected as a numeric score delta.

    With identical content, the core+verified+recent doc should score
    at least (BOOST_CORE + BOOST_VERIFIED + BOOST_RECENT) above a plain doc.
    """
    shared = "alpha beta gamma delta epsilon content body text"
    now = time.time()
    full = _make_doc("lessons/core/a.md", content=shared + "\n## Verify\nok\n",
                     mtime=now, status="published")
    plain = _make_doc("lessons/contrib/b.md", content=shared,
                      mtime=0.0, status="published")
    scored = _rank_docs_impl("alpha", [plain, full])
    # The score gap between full and plain must be at least the sum of the
    # three positive boosts (other components cancel because content matches).
    gap = scored[0][0] - scored[1][0]
    expected_min = BOOST_CORE + BOOST_VERIFIED + BOOST_RECENT
    assert gap >= expected_min, f"gap={gap}, expected>={expected_min}"


def test_rank_filtered_docs_unaffected_by_existing_logic():
    """Existing filtering (titles_only / broad_only) must still work."""
    docs = [
        _make_doc("lessons/contrib/a.md", content="alpha", mtime=0.0, status="published"),
        _make_doc("lessons/contrib/b.md", content="alpha", mtime=0.0, status="published"),
    ]
    # No exceptions, no regressions on the basic ranking path.
    scored = _rank_docs_impl("alpha", docs, titles_only=True, broad_only=False)
    assert len(scored) == 2
