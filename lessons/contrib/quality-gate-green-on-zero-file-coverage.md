---
title: "A quality gate is green on zero files: 0/302 coverage behind exit 0"
domain: "ci"
tags:
  - "quality-gate"
  - "coverage"
  - "file-discovery"
  - "exit-code"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "质量门禁只认得一种文件格式，语料换成另一种后它一个文件都没读过，却仍然绿灯退出 0。"
trigger: "quality gate exits 0 while coverage of its own corpus is 0/302"
verify: "校验脚本每次运行都打印 coverage: N/M，空匹配集在阻断模式下退出非 0；删掉一条必填字段必须让校验失败"
source: "intake-2673"
provenance:
  issue: "#2673"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A quality gate is green on zero files: 0/302 coverage behind exit 0

## Problem

A quality gate reported green while its actual subject matter was 100% uncovered — because the gate
only knew how to read one file format and the corpus was stored in another.

As reported: the gate validated markdown documents that carry a `rounds` block. The corpus it was
supposed to police was 302 records stored as plain JSON with no frontmatter. So the gate's validation
path never touched them: measured coverage was 0/302 for both required evidence fields, and the
command still exited 0.

Nobody noticed for weeks, because green is green.

The reporter's one-line statement of the failure:

```
quality gate exits 0 while coverage of its own corpus is 0/302
```

## Root Cause

The gate was written against the first batch of data (markdown with frontmatter), and the corpus
later grew a second shape (JSON records). The gate's file discovery matched `*.md`; the JSON records
fell outside the glob and were simply never opened.

Two things made this invisible:

1. **A gate that sees zero files exits 0.** There is no difference between "checked 302 records, all
   good" and "checked 0 records".
2. **The gate had no coverage counter.** Nothing said "I looked at N of M".

A gate with no line of sight is indistinguishable from a passing gate. The exit code is a claim about
the files the gate opened; it is not a claim about the files that exist.

## Solution

The four measures the reporter landed on:

- **Enumerate what the gate is supposed to cover, and print the count every run.**
  `evidence coverage: 0/302 (0.0%)` turns an invisible gap into a number that cannot be ignored.
- **Fail on "found nothing" when something is expected to be found.** If the corpus is non-empty and
  the gate matched zero records, that is a gate defect, not a pass.
- **Check file-format coverage explicitly** when a corpus can have more than one shape. A glob that
  silently drops one shape is the bug.
- **Separate the modes deliberately.** Reporting the gap should be cheap and always on; blocking
  should be opt-in during a backfill period. Otherwise the fix for a false green is to make it a
  false red.

Shape of the discovery fix, in the reporter's terms: for every accepted file format, assert that the
discovery step matched a non-zero share of the corpus, and make a zero match a hard failure in
blocking mode rather than a clean exit.

## Verification

The reporter's verification, as written in the intake (the snippet was truncated at the point shown;
the remainder is not reproduced here):

```bash
# 1) the gate reports coverage
python3 validate.py | grep -E 'coverage: [0-9]+/[0-9]+'
#    → coverage: 0/302 (0.0%)
```

and the criteria stated in the intake's `Verification` field:

```
gate prints "coverage: 0/302 (0.0%)"; missing field exits 1 with blocking enabled and 0 without; empty corpus is reported not passed
```

So three checks must all hold after the fix: the coverage line is printed on every run, a record that
is missing a required field fails with blocking enabled and only reports without it, and an empty
corpus is reported as a defect instead of passing silently.

## Notes

- `validate.py` is the reporter's placeholder name for the gate script; the real path was not given
  (`报料者未给出，需复现确认`).
- The second half of the verification snippet (the "record missing the required field" case) was cut
  off in the intake — reproduce it locally before quoting a command from it.
- The same defect class covers any gate whose input set is discovered by glob: `*.md` vs `*.json`,
  `tests/` vs `test/`, one directory level vs recursive. The count of opened files is the only
  reliable evidence that the gate saw the corpus.
