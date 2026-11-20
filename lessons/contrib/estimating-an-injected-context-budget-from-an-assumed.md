---
title: "Estimating an injected context budget from an assumed render format is off by 3x"
domain: "devops"
tags:
  - "token-budget"
  - "estimation"
  - "prompt-injection"
  - "calibration"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5439"
summary_plain: "A status script estimates how much of a long-term memory plugin's prompt budget is consumed."
trigger: "Estimating an injected context budget from an assumed render format is off by 3x. A status script estimates how much of a long-term memory plugin's prompt…"
verify: "The estimate stays within about 5% of the measured injected block. In this case the error went from 3x to 21 characters out of 1845 (about 1%), after adding truncation and fixed overhead."
provenance:
  issue: "#5439"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A status script estimates how much of a long-term memory plugin's prompt budget is consumed. Three successive attempts, all wrong:

- v1 summed only pinned entries (text + metadata): 745 / 2000 — far below reality.
- v2 added the plugin's recent-N entries as well: 1973 / 2000 — now far above.
- The plugin actually injected 1845 / 2000.

Each version looked internally consistent and was still wrong, because each was built from an assumption about what gets rendered rather than from the rendered text.

## Root Cause

The formula encoded "what I know exists", not "what the plugin actually emits". Three things were missing, and each one pushed the error in a different direction:

1. Non-pinned recent entries also consume the budget (v1 missed this → too low).
2. The budget fills until it is full and then truncates; it does not try to fit everything (v2 missed this → too high).
3. There is fixed overhead outside the entries: section heading, and the trailing "N more not shown" hint (both versions missed this).

Because the errors were in opposite directions, neither version looked consistently biased, which made the mistake harder to notice than a single wrong constant would have been.

## Fix

1. Capture the real rendered block once (the actual injected text) and measure it. Use that number as ground truth before writing any formula.
2. Decompose it: fixed overhead / per-entry overhead / per-entry text. Only then reverse-engineer the formula from the observed value.
3. If the algorithm is not fully visible or can change between versions, stop pretending to be exact: label the output "approximate", and prefer a threshold alarm (e.g. >90% of budget) over a precise number nobody can verify.
4. Keep the estimate honest in the output text itself, not in a comment — the number gets quoted later without the comment.

## Verification

The estimate stays within about 5% of the measured injected block. In this case the error went from 3x to 21 characters out of 1845 (about 1%), after adding truncation and fixed overhead.
