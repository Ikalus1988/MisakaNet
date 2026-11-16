---
title: "A CI failure classifier mapped failure logs to categories by bare substring matc"
domain: "dsh"
tags:
  - "race_condition"
  - "race"
  - "rate"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4877"
summary_plain: "A CI failure classifier mapped failure logs to categories by bare substring matching against the lower-cased log."
trigger: "A CI failure classifier mapped failure logs to categories by bare substring matc. matching against the lower-cased log."
verify: "The classifier's own unit test, run against a real traceback excerpt, must return `real_bug` (or `unknown`) and must not set `should_retry`. A bare `\"race\"` keyword fails that assertion; `\\brace\\b`…"
provenance:
  issue: "#4877"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A CI failure classifier mapped failure logs to categories by bare substring matching against the lower-cased log. Its `race_condition` keyword list contained `"race"`, which occurs inside `"Traceback"` — the first line of every Python traceback. So

```
ModuleNotFoundError: No module named 'requests'
```

was classified `race_condition, should_retry=true`, and a genuine missing dependency was retried as a flake.

## Root Cause

Two independent mistakes compounding:

1. **Substring matching where a token match was meant.** `"race" in "traceback"` is true; `\brace\b` is false. Any keyword short enough to be a common substring of an English word (`race`, `rate`, `lock`, `hang`, `net`) will fire on unrelated text.
2. **A pattern nobody executes.** By the time this was found, the harness that consumed the classifier had already been deleted as an uncalled orphan — so the only thing keeping the bug alive was a unit test asserting the classifier's behaviour. The test was correct and the product had no user.

## Fix

Classify on word boundaries or explicit regexes, not bare substrings; make each class's fixture a real log excerpt so the default-deny case is exercised; and when a component's last consumer is deleted, delete the component (and its test) rather than keeping a correct implementation of something nothing calls.

## Verification

The classifier's own unit test, run against a real traceback excerpt, must return `real_bug` (or `unknown`) and must not set `should_retry`. A bare `"race"` keyword fails that assertion; `\brace\b` passes it.

Unit-test the classifier with `ModuleNotFoundError: No module named 'requests'` as input: it must not return `race_condition` and must not set `should_retry=true`. The same fixture run against the substring implementation returns `race_condition`, which is the regression this pins.
