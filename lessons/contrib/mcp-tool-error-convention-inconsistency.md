---
{"title": "MCP tool ERROR convention — inconsistency between failure paths causes silent data corruption", "domain": "mcp", "tags": ["mcp", "error_handling", "convention", "git", "commit_message"], "language": "en", "status": "published", "source": "https://dev.to/enjoy_kumawat/i-gave-my-mcp-tool-an-error-convention-i-only-taught-it-to-one-of-its-two-failure-paths-4619", "created": "2026-07-29", "confidence": "0.85"}
---

## Problem

An MCP tool `generate_commit_message` converts git diffs into Conventional Commit messages via `claude -p`. It had two distinct failure paths returning plain strings in different formats. A caller checking for the `ERROR:` prefix would miss the timeout failure and silently use the timeout error message as a real commit message.

## Root Cause

The timeout handling in `_claude()` was added on a different day from the empty-diff guard in `generate_commit_message`. Each fix addressed only the specific bug it targeted. The timeout branch returned `"claude -p timed out after 20s"` — lacking the `ERROR:` prefix convention that was later introduced for the empty-diff case.

This is a sequencing bug: two independent fixes each introduced a return-string convention, but they didn't agree on the format because they were written at different times.

## Solution

Add the `ERROR: ` prefix to the timeout return string in `_claude()`:

```python
except subprocess.TimeoutExpired:
    return "ERROR: claude -p timed out after 20s"
```

This makes both failure paths consistent so `.startswith("ERROR:")` works as a complete contract.

## Verification

not specified in source

## Notes

The broader lesson: when you establish a convention (like `ERROR:` prefix for failures), every failure path must follow it — including ones added before the convention existed. A regression test should enumerate the full subprocess boundary: empty input, timeout, missing executable, non-zero exit, and other failure modes.

## References

https://dev.to/enjoy_kumawat/i-gave-my-mcp-tool-an-error-convention-i-only-taught-it-to-one-of-its-two-failure-paths-4619
