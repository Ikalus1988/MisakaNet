---
domain: "contrib"
title: "slugify path traversal deep coverage"
verification: "metadata-normalized"
{"title": "Slugify: deep coverage of path traversal, null bytes, and reserved names", "domain": "scripts", "tags": ["slugify", "path-traversal", "windows-reserved", "null-byte", "test-coverage", "hardening"], "domain_expert": "unknown"}
---

## 问题

The original 5-test `test_slugify.py` (merged in commit `6912f87` for issue #95) covered the basics: standard titles, slashes, emojis, reserved names, and length limits. But it did NOT explicitly verify the new task acceptance criteria for issue #95 (re-posted as EvoMap bounty `cmptjhjjg4ood7i2bkhkov`):

- `../` and `..\` path traversal characters
- Null bytes (`\x00`) and control characters
- Trailing dots and spaces (Windows silently strips these, causing filename collisions)
- All 14 Windows reserved names (AUX, LPT1-LPT9, mixed case)
- Unicode zero-width space and combining characters

The implementation is correct (verified by adding tests that all pass), but the lack of explicit test cases meant future refactors could regress these protections without any test failure.

## 根因

The original PR #97 focused on **fixing the implementation** and added "good enough" tests. It did not anticipate that:

1. **A regex whitelist** (`[^a-z0-9\u4e00-\u9fff]+`) silently handles a much broader threat surface than the original tests verify. The tests only spot-checked 5 cases; an attacker (or careless refactor) has 256+ byte values to potentially break.
2. **Path traversal tests were missing**: an attacker crafting a title with `../../etc/passwd` was never tested explicitly. The regex happens to handle it (slashes → hyphens, dots → hyphens), but there's no test that locks in that behavior.
3. **Windows reserved name coverage was incomplete**: original tests checked `CON`, `prn`, `nul`, `com1` but missed `AUX`, `LPT1-LPT9`, and case variants. If someone refactors the reserved-name check (e.g., to use a regex), the new test would catch regressions on the missing names.

## 修复方案

Added a new test file `tests/test_slugify_path_traversal.py` (14 new tests) that explicitly covers the additional threat surface:

- **PathTraversal class** (6 tests): Unix `../`, Windows `..\`, absolute paths, drive letters, trailing dots, trailing spaces
- **NullBytes class** (3 tests): null bytes, multiple null bytes, all control characters (`\n`, `\t`, `\r`)
- **WindowsReserved class** (3 tests): all 14 reserved names, lowercase variants, reserved with extension
- **UnicodeRobustness class** (2 tests): zero-width space, NFKD decomposition

All 14 tests pass against the current implementation. The implementation is **unchanged** — only test coverage was added. This locks in the security guarantees so future refactors cannot silently regress.

## 验证

Ran both test suites locally with `PYTHONIOENCODING=utf-8`:

```text
$ python3 -m unittest tests.test_slugify -v
... 5 tests in 0.002s
OK

$ python3 -m unittest tests.test_slugify_path_traversal -v
... 14 tests in 0.021s
OK

$ python3 search_knowledge.py "slugify"
[scripts]   Slugify filename sanitation crash on Windows and WSL
             ███████░░░ 70%
            📄 lessons/slugify-windows-path-sanitation.md

[scripts]   Slugify: deep coverage of path traversal, null bytes, and reserved names
             █████████░ 100%
            📄 lessons/contrib/slugify-path-traversal-deep-coverage.md  ← this lesson
```

Total: **19 tests, 2 lessons, 100% search recall** for the term `slugify`.
