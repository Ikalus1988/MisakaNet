---
title: "Zero discrimination on a scoring tool usually means thin input, not a broken detector"
domain: "testing"
tags:
  - "validation"
  - "retrospective-evaluation"
  - "scoring"
  - "test-harness"
  - "input-fixture"
  - "false-negative"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "回溯验证里所有样本都得到同一个分数，先别删检测逻辑：多半是喂进去的输入缺了检测器要读的字段。"
trigger: "zero discrimination all samples identical score detector never fires diff-stat missing file names"
verify: "Two inputs identical except for the field produce different scores, and switching the detector off collapses both back to the baseline constant."
source: "intake-3406"
provenance:
  issue: "#3406"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Zero discrimination on a scoring tool usually means thin input, not a broken detector

## Problem

Retrospective validation of a scoring / prediction tool — feed samples with known outcomes back in
and check whether the verdict matches — returned **zero discrimination on the first round**: every
sample got the same score. The natural conclusion is "the scoring is broken / useless", and that
conclusion invites rewriting or deleting a detection branch that actually works.

Measured on that run: with summary-style input the pairwise discrimination rate was **0.50** (chance
level). With a real `git diff --stat` — which carries file names — the *same* logic reached **0.69**.

## Root Cause

The detector needs a field from its input: "does this diff touch a test file" requires the diff-stat
to actually contain file-name paths. The validation script built **summary-style input** for
convenience:

```
N files changed, X insertions(+), Y deletions(-)
```

No file names. The detection branch could never match, so the output collapsed to a constant (the
repository's baseline score) — behaviour indistinguishable from "the detector never fires". This
looks exactly like "no effect" and is reported as "no effect", yet nothing about the detector was
measured at all.

A second, common source of constant output is upstream degradation: when a hand-supplied parameter is
missing, the tool falls back to a default and sets a flag. Look for `degraded` / `basis` markers in
the output before suspecting the detector.

## Solution

Before judging the detector, do a three-step physical of the input.

### Step 1 — print a real sample and confirm the field is in it

Read the detector's code path, name the field it consumes, then check that field appears in the input
you actually fed it. "I fed it a diff" is not the check; "the string the detector greps for is in the
input" is.

### Step 2 — build an extreme control pair

Two inputs identical except for that field, with the field pushed to its maximum and minimum — a
two-line change versus a 200-file rewrite. Under summary input both scored 0.91; with file names they
separate. If the output does not move, the detector is genuinely unaffected. If it moves, the input
was too thin.

### Step 3 — compare summary input against real input

The gap between the two numbers is the diagnosis, and it belongs in the output rather than in
someone's memory of the run.

### Step 4 — run the negative test

Temporarily switch the real detector off. With file names present the score should fall back to the
constant — that proves the 0.69 came from the field and not from coincidence.

### Step 5 — word the conclusion narrowly

Write "valid on inputs that carry that field", never "valid". Keep both input forms' numbers
together, so the next reader cannot repeat the mistake in the other direction.

## Verification

Reported criteria:

1) same samples, same logic, only the input shape changed: summary diff-stat → 0.50 pairwise
   discrimination; diff-stat with file names → 0.69;
2) extreme control: two inputs identical except for the field must produce different outputs
   (reported: both 0.91 under summary input, separating once file names were present);
3) negative test: with the detector off, the file-name input must fall back to the constant;
4) the written conclusion scopes itself to inputs carrying the field, and both numbers stay in the
   output.

Not re-run in this repository. The scoring tool, the sample set and the repository under test were
not named in the report — 报料者未给出，需复现确认.
