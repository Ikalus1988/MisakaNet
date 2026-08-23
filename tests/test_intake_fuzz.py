"""Hypothesis fuzz tests for intake redaction (Issue #1182).

Tests that redaction never leaks secrets on arbitrary input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from hypothesis import given, strategies as st, settings, HealthCheck
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

pytestmark = pytest.mark.skipif(not HAS_HYPOTHESIS, reason="hypothesis not installed")


def _get_redact_function():
    """Get redact function."""
    try:
        from scripts.intake_redact import redact_text
        return redact_text
    except ImportError:
        return None


# Known secret patterns that should never survive redaction
SECRET_PATTERNS = [
    r"ghp_[a-zA-Z0-9]{36}",      # GitHub token
    r"sk-[a-zA-Z0-9]{48}",       # OpenAI key
    r"AKIA[a-zA-Z0-9]{16}",      # AWS key
    r"xoxb-[a-zA-Z0-9-]+",       # Slack token
]


def contains_secrets(text: str) -> bool:
    """Check if text contains known secret patterns."""
    import re
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


@given(text=st.text(min_size=0, max_size=10000))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_redaction_never_crashes(text):
    """Redaction should never crash on arbitrary input."""
    redact = _get_redact_function()
    if redact is None:
        pytest.skip("redact_text not available")

    try:
        result = redact(text)
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"Redaction crashed on input {repr(text[:100])}: {e}")


@given(text=st.text(alphabet=st.characters(blacklist_categories=("Cs",))))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_redaction_handles_unicode(text):
    """Redaction handles all unicode without error."""
    redact = _get_redact_function()
    if redact is None:
        pytest.skip("redact_text not available")

    try:
        result = redact(text)
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"Redaction crashed on unicode input: {e}")


@given(text=st.from_regex(r"ghp_[a-zA-Z0-9]{36}", fullmatch=True))
@settings(max_examples=20)
def test_redaction_removes_github_tokens(text):
    """GitHub tokens should be redacted."""
    redact = _get_redact_function()
    if redact is None:
        pytest.skip("redact_text not available")

    result = redact(text)
    assert "ghp_" not in result or "***" in result


@given(text=st.from_regex(r"sk-[a-zA-Z0-9]{48}", fullmatch=True))
@settings(max_examples=20)
def test_redaction_removes_openai_keys(text):
    """OpenAI keys should be redacted."""
    redact = _get_redact_function()
    if redact is None:
        pytest.skip("redact_text not available")

    result = redact(text)
    assert "sk-" not in result or "***" in result


@given(payload=st.dictionaries(
    keys=st.text(min_size=1, max_size=50),
    values=st.text(min_size=0, max_size=1000),
    min_size=0,
    max_size=10,
))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_redaction_dict_never_leaks(payload):
    """Dict redaction should never leave secrets."""
    redact = _get_redact_function()
    if redact is None:
        pytest.skip("redact_text not available")

    # Redact each value
    redacted = {k: redact(str(v)) for k, v in payload.items()}

    # Check no secrets survive
    for key, value in redacted.items():
        assert not contains_secrets(str(value)), f"Secret found in {key}"


@given(text=st.sampled_from([
    "",
    " ",
    "\x00",
    "ghp_" + "a" * 36,
    "sk-" + "b" * 48,
    "token: " + "c" * 40,
    "Bearer " + "d" * 40,
    "password=secret123",
    "api_key: my_secret_key",
]))
@settings(max_examples=20)
def test_redaction_edge_cases(text):
    """Edge case inputs should not crash."""
    redact = _get_redact_function()
    if redact is None:
        pytest.skip("redact_text not available")

    try:
        result = redact(text)
        assert isinstance(result, str)
    except Exception as e:
        pytest.fail(f"Redaction crashed on edge case: {e}")


if __name__ == "__main__":
    if HAS_HYPOTHESIS:
        test_redaction_never_crashes()
        test_redaction_handles_unicode()
        test_redaction_removes_github_tokens()
        test_redaction_removes_openai_keys()
        test_redaction_dict_never_leaks()
        test_redaction_edge_cases()
        print("All intake fuzz tests passed ✓")
    else:
        print("hypothesis not installed, skipping fuzz tests")
