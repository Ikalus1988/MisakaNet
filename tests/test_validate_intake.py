"""Tests for validate_intake.py (Issue #1252)."""
from __future__ import annotations

import json
import pytest
from scripts.validate_intake import validate_intake, ValidationResult


def test_high_quality_intake():
    """Well-structured intake should score high."""
    body = """
## Problem

When running the MCP server with Python 3.14, the server crashes on startup with a TypeError.

## Error

```
TypeError: 'str' object has no attribute 'get'
  File "scripts/mcp_server.py", line 42
    setup_logger(fmt=LoggingFormat.JSON, level=get_settings().get("CONFIG.LOG_LEVEL", "DEBUG"))
```

## Root Cause

The dynaconf library returns a string instead of a dict when the configuration key uses dotted notation.

## Fix

Replace `get_settings().get("CONFIG.LOG_LEVEL")` with `get_settings()["CONFIG"]["LOG_LEVEL"]` or use environment variables:

```python
import os
log_level = os.environ.get("MISAKA_LOG_LEVEL", "DEBUG")
```

## Verification

1. Set `MISAKA_LOG_LEVEL=INFO` in environment
2. Run `python3 scripts/mcp_server.py`
3. Verify logs show INFO level
"""
    result = validate_intake(body)
    assert result.quality_score >= 70
    assert result.word_count >= 50
    assert result.has_code is True
    assert result.has_error_msg is True


def test_low_quality_intake():
    """Minimal intake should score low."""
    body = """
## Problem

Doesn't work.

## Fix

Fixed it.
"""
    result = validate_intake(body)
    assert result.quality_score < 50
    assert len(result.issues) > 0


def test_missing_required_fields():
    """Missing problem/error/fix should fail."""
    body = """
## Background

This is some background information.

## Environment

Python 3.12, Ubuntu 22.04
"""
    result = validate_intake(body)
    assert result.quality_score < 40
    assert any("Missing required field" in issue for issue in result.issues)


def test_empty_body():
    """Empty body should score 0."""
    result = validate_intake("")
    assert result.quality_score == 0
    assert result.word_count == 0


def test_word_count():
    """Word count should exclude code blocks."""
    body = """
## Problem

This is a problem description with enough words to pass the minimum threshold.

## Error

```
Error: Some error message that should not be counted in the word count
because it is inside a code block and we only count regular text.
```

## Fix

This is the fix description that explains how to resolve the issue in detail.
"""
    result = validate_intake(body)
    assert result.word_count < 100  # Code block excluded


def test_code_detection():
    """Should detect code blocks."""
    body = """
## Problem

Some problem.

## Fix

Run this command:

```bash
python3 scripts/mcp_server.py
```
"""
    result = validate_intake(body)
    assert result.has_code is True


def test_error_detection():
    """Should detect error patterns."""
    body = """
## Problem

Getting an error.

## Error

Error: FileNotFoundError: /tmp/test.db

Traceback (most recent call last):
  File "test.py", line 1
"""
    result = validate_intake(body)
    assert result.has_error_msg is True


def test_json_output():
    """JSON output should be valid."""
    body = """
## Problem

Test problem with enough words to pass the minimum word count threshold.

## Error

Error: Some error message

## Fix

This is the fix that explains the solution in detail with enough words.
"""
    result = validate_intake(body)
    # Test format_report with JSON
    from scripts.validate_intake import format_report
    json_output = format_report(result, output_json=True)
    parsed = json.loads(json_output)
    assert "quality_score" in parsed
    assert "issues" in parsed
    assert "suggestions" in parsed


def test_suggestions_present():
    """Should provide suggestions for improvement."""
    body = """
## Problem

Short problem.
"""
    result = validate_intake(body)
    assert len(result.suggestions) > 0


if __name__ == "__main__":
    test_high_quality_intake()
    test_low_quality_intake()
    test_missing_required_fields()
    test_empty_body()
    test_word_count()
    test_code_detection()
    test_error_detection()
    test_json_output()
    test_suggestions_present()
    print("All tests passed ✓")
