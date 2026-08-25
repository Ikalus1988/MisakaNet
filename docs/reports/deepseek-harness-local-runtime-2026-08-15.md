# DeepSeekHarness Local Runtime Field Test Report

**Date:** 2026-08-15
**Repo:** Ikalus1988/MisakaNet
**Branch:** main

---

## Environment

| Property | Value |
|----------|-------|
| OS | Windows (to be filled after test run) |
| Python | 3.10+ (to be filled after test run) |
| Git SHA | (to be filled after test run) |
| MisakaNet Version | v2.17.0+ (to be filled after test run) |

---

## 1. CLI Verification

### `python3 scripts/misakanet_cli.py doctor`

```
$ python3 scripts/misakanet_cli.py doctor
# Output to be captured after test run
```

**Expected:** Exit 0, overall healthy
**Actual:** (to be filled after test run)

### `python3 scripts/misakanet_cli.py smoke`

```
$ python3 scripts/misakanet_cli.py smoke
# Output to be captured after test run
```

**Expected:** Exit 0, search returns results
**Actual:** (to be filled after test run)

### `python3 scripts/misakanet_cli.py validate`

```
$ python3 scripts/misakanet_cli.py validate
# Output to be captured after test run
```

**Expected:** Exit 0, all tools detected
**Actual:** (to be filled after test run)

---

## 2. DSH Configuration

### DSH Config File Location

```
# Path to be filled after test run
```

### Config Snippet (pointing to misakanet adapter)

```json
{
  "adapters": {
    "misakanet": {
      "type": "local",
      "endpoint": "http://localhost:8080",
      "tools": ["search", "get_lesson", "queue_lesson", "explain", "health", "validate"]
    }
  }
}
```

**Actual config:** (to be filled after test run)

---

## 3. Real DSH Runtime Calls

### 3.1 `deepseek.recovery.search` for "DCO"

**Command:**
```bash
# Command to be filled after test run
```

**Result:**
```json
{
  "results": [
    {
      "path": "lessons/dco-signoff.md",
      "score": 0.95,
      "snippet": "DCO sign-off required for all commits..."
    }
  ],
  "total": 1
}
```

**Expected:** Returns results for "DCO"
**Actual:** (to be filled after test run)

### 3.2 `deepseek.recovery.get_lesson` for a known lesson

**Command:**
```bash
# Command to be filled after test run
```

**Result:**
```markdown
# DCO Sign-off Lesson

## Problem
Commits without DCO sign-off fail CI checks.

## Solution
Use `git commit -s` to add Signed-off-by trailer.

## Verification
Run `git log --format="%H %s" --grep="Signed-off-by"`
```

**Expected:** Returns non-empty content
**Actual:** (to be filled after test run)

### 3.3 All 6 Adapter Tools Callable

| Tool | Callable | Result |
|------|----------|--------|
| search | (to be tested) | |
| get_lesson | (to be tested) | |
| queue_lesson | (to be tested) | |
| explain | (to be tested) | |
| health | (to be tested) | |
| validate | (to be tested) | |

---

## 4. Summary

| Check | Status | Notes |
|-------|--------|-------|
| CLI doctor | ⬜ Pending | |
| CLI smoke | ⬜ Pending | |
| CLI validate | ⬜ Pending | |
| DSH config exists | ⬜ Pending | |
| DSH config points to adapter | ⬜ Pending | |
| search("DCO") returns results | ⬜ Pending | |
| get_lesson returns content | ⬜ Pending | |
| All 6 tools callable | ⬜ Pending | |

---

## 5. Notes

- This report documents the local runtime field test for MisakaNet's DeepSeekHarness recovery adapter integration.
- No API keys required - all tests run against local MisakaNet instance.
- Remote MCP endpoint not tested (out of scope).
- This does not constitute official DeepSeekHarness certification.

---

*Report generated as part of issue #1048*
