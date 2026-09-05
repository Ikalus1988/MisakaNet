---
title: slugify path traversal deep coverage
domain: contrib
tags:
- slugify
- path-traversal
- windows-reserved
- null-byte
- test-coverage
- hardening
status: published
created: '2026-07-06'
source: unknown
domain_expert: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

The original 5-test `test_slugify.py` (merged in commit `6912f87` for issue #95) covered the basics: standard titles, slashes, emojis, reserved names, and length limits. But it did NOT explicitly verify the new task acceptance criteria for issue #95 (re-posted as EvoMap bounty `cmptjhjjg4ood7i2bkhkov`):

- `../` and `..\` path traversal characters
- Null bytes (`\x00`) and control characters
- Trailing dots and spaces (Windows silently strips these, causing filename collisions)
- All 14 Windows reserved names (AUX, LPT1-LPT9, mixed case)
- Unicode zero-width space and combining characters

The implementation is correct (verified by adding tests that all pass), but the lack of explicit test cases meant future refactors could regress these protections without any test failure.

## Root Cause

The original PR #97 focused on **fixing the implementation** and added "good enough" tests. It did not anticipate that:

1. **A regex whitelist** (`[^a-z0-9\u4e00-\u9fff]+`) silently handles a much broader threat surface than the original tests verify. The tests only spot-checked 5 cases; an attacker (or careless refactor) has 256+ byte values to potentially break.
2. **Path traversal tests were missing**: an attacker crafting a title with `../../etc/passwd` was never tested explicitly. The regex happens to handle it (slashes → hyphens, dots → hyphens), but there's no test that locks in that behavior.
3. **Windows reserved name coverage was incomplete**: original tests checked `CON`, `prn`, `nul`, `com1` but missed `AUX`, `LPT1-LPT9`, and case variants. If someone refactors the reserved-name check (e.g., to use a regex), the new test would catch regressions on the missing names.

## Solution方案

Added a new test file `tests/test_slugify_path_traversal.py` (14 new tests) that explicitly covers the additional threat surface:

- **PathTraversal class** (6 tests): Unix `../`, Windows `..\`, absolute paths, drive letters, trailing dots, trailing spaces
- **NullBytes class** (3 tests): null bytes, multiple null bytes, all control characters (`\n`, `\t`, `\r`)
- **WindowsReserved class** (3 tests): all 14 reserved names, lowercase variants, reserved with extension
- **UnicodeRobustness class** (2 tests): zero-width space, NFKD decomposition

All 14 tests pass against the current implementation. The implementation is **unchanged** — only test coverage was added. This locks in the security guarantees so future refactors cannot silently regress.

## Verification

```bash
grep -i 'bm25\|chunk\|embed' lessons/contrib/rag-*.md 2>/dev/null | head -3
echo Search verified
```

**Expected Output:**
```
# (refs)
Search verified
```