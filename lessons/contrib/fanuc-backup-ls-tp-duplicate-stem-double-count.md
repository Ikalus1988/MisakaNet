---
title: "FANUC backup checks count every metric twice when the .ls and .tp copies of one program both stay in the input"
domain: "fanuc"
tags:
  - "fanuc"
  - "backup-analysis"
  - "double-counting"
  - "duplicates"
  - "ls-file"
  - "tp-file"
  - "dedup"
  - "regression-test"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "备份目录里同一程序既有 .ls 又有 .tp 时引擎把两份都算一遍，所有计数整齐翻倍；先查重复份，别先怀疑统计函数。"
trigger: "every count exactly doubled remark 13 lines becomes 26 duplicate .ls .tp same stem FANUC backup checker"
verify: "Text-only gives 90 files / remark 13 lines; both formats before the fix give 166 / 26; after dedup the verdict matches text-only, and 3300 real directories sweep with 0 mismatches."
source: "intake-3192"
provenance:
  issue: "#3192"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# FANUC backup checks count every metric twice when the .ls and .tp copies of one program both stay in the input

## Problem

A backup directory held the same program twice — a text `.ls` and a binary `.tp` with the same name and
stem — and the check engine analysed both as independent files. The same program was therefore counted
twice, and the reported metrics doubled exactly:

- remark-related counts: from 1 处 MI 包指令被屏蔽 / 13 行 remark to **2 处 / 26 行**;
- CALL suppression: from 8 处 / 13 行 to **16 处 / 26 行**;
- plus one extra false positive that was not in the text-only run.

Two more surfaces collided silently: the source viewer indexed files by filename, and the export ZIP stored
entries by filename, so the two same-name files overwrote each other.

Measured on one real directory: **90** text versions and **76** binary versions, with all 76 colliding by
name — a 100% collision rate on the binary side.

## Root Cause

The collection layer had no "one logical unit, one representation" normalisation: both representations went
into the analysis engine as-is. The engine accumulates per file, so any metric that counts occurrences
doubles exactly when the same program is present twice. That exact-doubling is the fingerprint — it is what
distinguishes "duplicate input" from "a bug in the aggregation maths", which would move the numbers
unevenly.

Name-keyed tables are the second, quieter half of the failure: anything that maps a filename to a single
entry (ZIP entries, the source viewer index, a cache map) can hold one of the pair, and which one survives
depends on iteration order.

## Solution

1. Normalise at the entry point: deduplicate by logical unit *before* analysis and statistics. In this
   implementation, dedup by filename and keep the copy with more information — the binary side is dropped
   when a text side of the same name exists.
2. Write the doubling down as a criterion: when every count is exactly ×2, look for a duplicate copy before
   suspecting the counting logic. The reporter's own path to the bug was the opposite — they re-read the
   remark aggregation code repeatedly, and only noticed the exact ×2 pattern later.
3. Verify name collisions separately from the counts. Any place that builds a table keyed by filename needs
   its own test, because the damage there is a silent overwrite, not a doubled number.

## Verification

Three-way comparison in the same directory:

1. text-only input → **90** files / remark **13** lines;
2. both representations, before the fix → **166** files / remark **26** lines;
3. after dedup → the verdict matches run 1.

Five new unit tests lock the dedup rule: same name drops the binary side; a name with no counterpart is
kept; matching is case-insensitive; the same name in *different* directories is not removed; an all-binary
input is kept as-is.

The full sweep over **3300** real directories reported **0** mismatches against the text-only baseline.

## Notes

- The report gives the counts and the rule, not the per-file logs: which metric produced the extra false
  positive, and the exact files involved, are not in the intake — 报料者未给出，需复现确认.
- "Keep the copy with more information" is the reporter's rule; the unit-test list shows that in practice
  the text side wins when both exist. Whether that is right for binary-only payloads (for example a `.tp`
  whose text side is a stale export) is not answered by the report.
- Related: `lessons/contrib/fanuc-ls-parser-comment-and-segment-boundary.md` covers parsing the text side
  correctly once it has been selected.
