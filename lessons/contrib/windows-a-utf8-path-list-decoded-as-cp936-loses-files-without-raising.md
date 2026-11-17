---
title: "A UTF-8 path list decoded as cp936 loses 211 files, and nothing raises"
domain: "windows"
tags:
  - "encoding"
  - "cp936"
  - "subprocess"
  - "git-ls-files"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-11-17"
updated: "2026-11-17"
source: "maintainer"
summary_plain: "git's UTF-8 paths decoded as cp936 become other characters, so 211 lessons leave the index silently."
trigger: "subprocess.run text=True missing encoding cp936 non-ASCII paths silently dropped git ls-files"
verify: "Run the reader with PYTHONUTF8=1 and without it on a cp936 machine: the counts must be equal. 844/801 before the fix, 1055/1012 after."
provenance:
  issue: "#5139"
  source: "measured while reconciling an evidence-distribution table that said 801 lessons for a corpus of 1012"
---

# A UTF-8 path list decoded as cp936 loses 211 files, and nothing raises

## Problem

A corpus of **1012** lessons was reported as **801** by one generator, on one machine only:

```
$ python3 scripts/evidence_distribution.py
- Total lessons: **801**      # the site says 1012
```

Same commit, same files. The same script under WSL printed **1012**. Nothing in the output said a
file had been skipped, and the number looked like a plausible corpus that had simply grown less.

## Root Cause

The index is built from `git ls-files`, and that call asked Python for text without saying which
encoding:

```python
subprocess.run(
    ["git", "-c", "core.quotepath=false", "ls-files", "--", "."],
    cwd=lessons_root, capture_output=True, text=True,
    errors="surrogateescape", check=False, timeout=60,
)
```

`text=True` with no `encoding=` means **the locale codec**, which on a Chinese-locale Windows machine
is `cp936`. The two defences around it were both already in place and both useless here:

- `core.quotepath=false` stops git from octal-escaping `课程.md` into `"\350\257\276.md"`;
- `errors="surrogateescape"` stops a `UnicodeDecodeError` from crashing the call.

But cp936 does not *fail* on UTF-8 bytes. It maps them to different characters ("mojibake"), each one
a perfectly valid `str`. `surrogateescape` therefore never fires, and the decoded names simply do not
correspond to files on disk — the caller's `path.is_file()` filter drops them, silently:

| | tracked files | canonical index |
|---|---|---|
| cp936 (locale codec) | 844 | **801** |
| UTF-8 | 1055 | **1012** |

`PYTHONUTF8=1` fixes it, which is exactly why review did not catch it: CI runners, the hosted worker
and every Linux contributor run a UTF-8 locale, so the defect existed only on a local Chinese-locale
Windows checkout. A silent `−20%` on the corpus is worse than a crash, because a crash gets fixed.

## Solution

Say the encoding. One argument, and the reader means the same thing everywhere:

```python
subprocess.run(
    ["git", "-c", "core.quotepath=false", "ls-files", "--", "."],
    cwd=lessons_root, capture_output=True, text=True, encoding="utf-8",
    errors="surrogateescape", check=False, timeout=60,
)
```

`errors="surrogateescape"` stays: a genuinely non-UTF-8 filename (a stray upload, a test fixture) must
still be representable rather than aborting the index build.

## Verification

Run the same reader twice on the machine that showed the loss, once forcing UTF-8:

```
$ python -c "…tracked_lesson_files / canonical_lessons…"          # 844 / 801   before
$ PYTHONUTF8=1 python -c "…same…"                                 # 1055 / 1012 after
```

Equal counts mean the codec is no longer part of the answer. A structural test pins both defences in
the call (`encoding="utf-8"` **and** `core.quotepath=false`) because either one alone leaves the same
files invisible: `tests/test_lesson_index_discovery.py`.

## The generalisation

`text=True` without `encoding=` is a locale-dependent decision made silently at every call site. Any
subprocess call that *parses* a list of paths from git, `find`, `ls` or a language toolchain belongs to
this class, and only shows up on a machine whose locale is not UTF-8. Grep for it before shipping a
path-parsing helper:

```
grep -rn "subprocess.run(" --include="*.py" . | grep "text=True" | grep -v encoding=
```

The same bytes, a different decoder, and no exception: the failure mode is a smaller answer, not an
error.
