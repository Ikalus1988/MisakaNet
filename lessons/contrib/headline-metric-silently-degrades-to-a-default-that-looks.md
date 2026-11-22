---
title: "Headline metric silently degrades to a default that looks measured: (1) the read"
domain: "mcp"
tags:
  - "merge_rate"
  - "external_merge_rate_30"
  - "headline"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-2735"
summary_plain: "Headline metric silently degrades to a default that looks measured: (1) the reader looks up a config key nothing ever…"
trigger: "Headline metric silently degrades to a default that looks measured: (1) the read. reader looks up a config key nothing ever writes (writer stores `merge_rate`…"
verify: "Re-ran the issue's CLI repro: merge_probability now equals repo_context.merge_rate when present (0.2), and the no-rate path returns degraded=true with a reason; unit tests assert both paths plus…"
provenance:
  issue: "#2735"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Headline metric silently degrades to a default that looks measured: (1) the reader looks up a config key nothing ever writes (writer stores `merge_rate`, reader looks up `external_merge_rate_30`), so the measured value is ignored and a tier-based default is returned with no flag; (2) the schema field the reader prefers is a URL string where a numeric rate is expected, so type confusion can also poison the value.

## Root Cause

writer/reader key drift + no type coercion + fallback not self-declaring. Fix: resolve rate across all candidate keys with numeric-only coercion (reject URL strings), and make the fallback declare itself in the output (basis=measured|tier_estimate|unknown, degraded=true + reason naming the missing keys and the default used); CLI renders "(estimate)" when degraded. Verification: before, analyze with repo merge_rate=0.2 returned 0.35 (tier default) with empty comparison; after, returns 0.2 basis=measured; without a rate returns the default with degraded=true + reason. Generalizable rule: grep the key a reader looks up against what writers actually store; coerce config values by type; never return a fallback metric without labeling it.

## Fix

Multi-key lookup (external_merge_rate_30 / external_merge_rate / merge_rate) with coerce-to-(0,1]-float that rejects non-numeric strings; return merge_probability_basis + merge_probability_degraded + reason in the result; CLI marks "(estimate)"; tests pin measured==merge_rate and the degraded flags.

## Verification

Re-ran the issue's CLI repro: merge_probability now equals repo_context.merge_rate when present (0.2), and the no-rate path returns degraded=true with a reason; unit tests assert both paths plus URL-string rejection.
