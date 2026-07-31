# Runtime Smoke Test Report - 2026 Q4

**Date:** 2026-07-30  
**Tester:** Automated Smoke Test Suite  
**Scope:** Failure-memory entry points (Cursor, Claude Code, misaka CLI)

---

## Executive Summary

This report documents smoke testing of MisakaNet's runtime failure-memory integration across three primary entry points: Cursor IDE rules, Claude Code playbook, and the `misaka` CLI tool. Testing focused on verifying that failure detection, lesson retrieval, and intake submission workflows function correctly in real-world scenarios.

**Overall Status:** ✅ All core entry points operational with documented edge cases.

---

## Test Environment

- **MisakaNet Version:** Current main branch
- **Test Repository:** Internal test suite with intentional failures
- **Python Version:** 3.11.x
- **Node Version:** 20.x LTS
- **Test Date Range:** 2026-07-28 to 2026-07-30

---

## 1. Cursor IDE Integration

### Test Case: `.cursor/rules/misakanet-failure-memory.mdc`

**Objective:** Verify that Cursor's AI assistant triggers failure-memory lookup when encountering test failures or build errors.

#### Test Procedure
1. Created intentional test failure: `test_division_by_zero` in `tests/test_math.py`
2. Ran test via Cursor's integrated terminal
3. Invoked Cursor AI with prompt: "Fix this test failure"
4. Observed whether `.mdc` rule triggered lesson retrieval

#### Results

✅ **PASS** - Rule triggers correctly on real failures

**Observed Behavior:**
- Cursor AI detected `ZeroDivisionError` traceback pattern
- Rule file correctly instructed AI to query MisakaNet lessons
- AI response included: "Checking MisakaNet for similar failures..."
- Retrieved 2 relevant lessons:
  - `lesson-2024-03-15-division-guards.md` (exact match)
  - `lesson-2024-06-22-input-validation.md` (related pattern)

**Sample AI Response:**
```
I found a MisakaNet lesson about this exact error pattern. 
The recommended fix is to add input validation before division:

if denominator == 0:
    raise ValueError("Cannot divide by zero")
```

#### Edge Cases Discovered

⚠️ **Partial Coverage:**
- **Catches:** Python exceptions, TypeScript compile errors, Rust panic patterns
- **Misses:** Silent logic errors (wrong output, no exception), performance regressions, flaky tests that pass on retry

**Recommendation:** Rule file should be updated to prompt for lesson lookup even when tests pass but behavior seems incorrect.

---

## 2. Claude Code Integration

### Test Case: `CLAUDE.md` Playbook After 2 Failed Attempts

**Objective:** Verify Claude Desktop/Code triggers MisakaNet consultation after repeated failure.

#### Test Procedure
1. Created failing test: `test_async_timeout` (intentional race condition)
2. Asked Claude to fix it (Attempt 1)
3. Applied suggested fix, test still failed (Attempt 2)
4. Observed whether playbook triggered on Attempt 3

#### Results

✅ **PASS** - Playbook triggers after 2 failed attempts

**Observed Behavior:**
- After second failure, Claude's response included:
  ```
  I notice this is the second failed attempt. Per the CLAUDE.md playbook,
  I should consult MisakaNet for institutional knowledge about async timeout patterns.
  ```
- Retrieved lesson: `lesson-2025-11-08-asyncio-timeout-context.md`
- Suggested fix used `asyncio.timeout()` context manager (correct pattern)
- Test passed on Attempt 3

#### Edge Cases Discovered

⚠️ **Partial Coverage:**
- **Catches:** Repeated identical failures, test flakiness patterns
- **Misses:** Different failures on each attempt (e.g., first attempt = syntax error, second = logic error), failures in different files

**Recommendation:** Playbook should track failure *context* (file + error type) rather than just attempt count.

---

## 3. `misaka run` CLI Integration

### Test Case: `misaka run -- python -m pytest` on Failing Test

**Objective:** Verify CLI wrapper detects failures and displays relevant lessons inline.

#### Test Procedure
1. Created failing test: `test_json_parse_error` (malformed JSON input)
2. Ran: `misaka run -- python -m pytest tests/test_parser.py::test_json_parse_error -v`
3. Observed output for lesson suggestions

#### Results

✅ **PASS** - Shows relevant lessons after test failure

**Terminal Output:**
```
$ misaka run -- python -m pytest tests/test_parser.py::test_json_parse_error -v

======================== test session starts =========================
tests/test_parser.py::test_json_parse_error FAILED              [100%]

============================== FAILURES ==============================
_______________________ test_json_parse_error _______________________

    def test_json_parse_error():
>       result = parse_config("{invalid json}")
E       json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes

========================== 1 failed in 0.12s =========================

🔍 MisakaNet found 3 relevant lessons:

  1. lesson-2024-09-12-json-validation-before-parse.md
     "Always validate JSON structure before parsing to provide better error messages"

  2. lesson-2025-02-03-pydantic-safe-parsing.md
     "Use pydantic's parse_obj_as with try/except for robust config parsing"

  3. lesson-2024-11-20-json-schema-validation.md
     "Pre-validate against JSON schema to catch malformed input early"

💡 Run 'misaka lesson show lesson-2024-09-12-json-validation-before-parse.md' for details
```

#### Edge Cases Discovered

⚠️ **Partial Coverage:**
- **Catches:** Python exceptions, pytest failures, cargo test failures, npm test failures
- **Misses:** Warnings (non-fatal), deprecation notices, tests marked `xfail`, skipped tests

**Recommendation:** Add `--strict` flag to surface lessons for warnings and skipped tests.

---

## 4. `misaka capture` CLI Integration

### Test Case: `misaka capture --summary "test error"` Submits Redacted Intake

**Objective:** Verify intake submission redacts sensitive data and reaches backend.

#### Test Procedure
1. Triggered error with sensitive data: `test_api_key_leak` (hardcoded API key in traceback)
2. Ran: `misaka capture --summary "API key validation error in test suite"`
3. Verified redaction in submitted payload
4. Checked backend intake queue

#### Results

✅ **PASS** - Submits redacted intake successfully

**Redaction Verification:**

Original traceback:
```python
AssertionError: Expected API key 'sk-proj-abc123XYZ...', got None
```

Submitted intake (redacted):
```python
AssertionError: Expected API key '[REDACTED_API_KEY]', got None
```

**Backend Confirmation:**
- Intake ID: `intake-2026-07-30-1423-a7f9`
- Status: `pending_review`
- Redacted fields: API keys, file paths (converted to relative), user home directories

#### Edge Cases Discovered

⚠️ **Partial Coverage:**
- **Redacts:** API keys (regex patterns), absolute paths, email addresses, IP addresses
- **Misses:** Custom secret formats (e.g., `CUSTOM_TOKEN=abc123`), secrets in base64, PII in test data (names, SSNs)

**Recommendation:** Add `--redact-config` flag to specify custom regex patterns for project-specific secrets.

---

## 5. Failure Coverage Analysis

### What MisakaNet Catches

✅ **Well-Covered Failure Types:**
1. **Python exceptions** - All standard library exceptions, common third-party (requests, pydantic)
2. **Test framework failures** - pytest, unittest, jest, cargo test
3. **Build errors** - Rust compiler errors, TypeScript type errors, webpack failures
4. **Runtime panics** - Rust panics, Node.js uncaught exceptions
5. **Assertion failures** - All major test assertion libraries

### What MisakaNet Misses

❌ **Gap Areas:**

1. **Silent Logic Errors**
   - Test passes but produces wrong output
   - Off-by-one errors that don't throw exceptions
   - **Mitigation:** Requires property-based testing integration or manual capture

2. **Performance Regressions**
   - Test passes but runs 10x slower
   - Memory leaks that don't cause OOM immediately
   - **Mitigation:** Add `misaka benchmark` subcommand to track performance baselines

3. **Flaky Tests (Intermittent)**
   - Test passes 80% of the time, fails randomly
   - Race conditions that only trigger under load
   - **Mitigation:** `misaka run --repeat 10` to detect flakiness patterns

4. **Configuration Errors**
   - Wrong environment variable, test passes in dev but fails in CI
   - Missing dependencies not caught by package manager
   - **Mitigation:** Add environment diff detection to `misaka capture`

5. **Deprecation Warnings**
   - Code works but uses deprecated APIs
   - Future breaking changes not flagged
   - **Mitigation:** Add `--warnings-as-lessons` flag to `misaka run`

6. **Integration Test Failures (External Services)**
   - Third-party API down, test fails but not a code issue
   - Database connection timeout (infrastructure, not code)
   - **Mitigation:** Add `--context external-service` flag to skip lesson lookup

---

## Recommendations

### High Priority
1. **Cursor Rule Enhancement:** Add logic error detection prompt ("Does this output look correct?")
2. **Claude Playbook:** Track failure context, not just attempt count
3. **CLI Redaction:** Support custom secret patterns via config file

### Medium Priority
4. **Flakiness Detection:** `misaka run --repeat N` to identify intermittent failures
5. **Warning Capture:** `--strict` mode to surface lessons for non-fatal issues
6. **Performance Tracking:** `misaka benchmark` subcommand for regression detection

### Low Priority
7. **Integration Test Context:** `--external-service` flag to skip irrelevant lessons
8. **Lesson Gap Analysis:** Auto-generate reports on uncaught failure patterns

---

## Conclusion

All three primary entry points (Cursor, Claude Code, `misaka` CLI) successfully trigger failure-memory workflows in real-world scenarios. The system reliably catches exception-based failures and provides relevant lessons. Key gaps exist around silent logic errors, performance issues, and flaky tests—areas that require proactive instrumentation rather than reactive error handling.

**Next Steps:**
1. Implement high-priority recommendations (Cursor rule + Claude playbook improvements)
2. Create lesson gap analysis automation (track which failures don't match any lessons)
3. Expand redaction patterns based on user feedback

---

**Report Author:** MisakaNet QA Team  
**Review Status:** Ready for maintainer review  
**Related Issues:** #683
