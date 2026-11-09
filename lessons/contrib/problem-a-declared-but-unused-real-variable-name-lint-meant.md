---
title: "「声明了却没用」的变量名 lint 报出上万条噪声：共享 VAR 声明与 TYPE 块淹没 4 条真信号"
domain: "mcp"
tags:
  - "problem"
  - "declared"
  - "unused"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4608"
summary_plain: "A \"declared but unused real variable name\" lint — meant to catch name-binding breaks where a declaration keeps its…"
trigger: "Problem A \"declared but unused real variable name\" lint — meant to catch name-bi. A \"declared but unused real variable name\" lint — meant to catch…"
verify: "Same corpus, same lint: 12,146 hits → 4 hits, and all 4 were genuine orphan/binding-break candidates. A hand-crafted negative fixture (declared BOOLEAN never used elsewhere) is still caught. The…"
provenance:
  issue: "#4608"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

A "declared but unused real variable name" lint — meant to catch name-binding breaks where a declaration keeps its real name but usages render under a synthetic name — reported 12,146 hits across a 300-file decompiled corpus, drowning the 4 real signals. A variant that scanned TYPE blocks added 69 more false hits per file (structure field names like X/Y/Z/W/P/R).

## Root Cause

Three noise sources, each structural:
1. **Shared-declaration bloat**: every module declares the whole shared VAR file (cross-module persistent vars), so most declarations are legitimately unused in any single module.
2. **TYPE block fields** match a generic `name : TYPE` declaration regex but are struct definitions, not variables.
3. **Cross-module usage via string references** (SET_VAR('...','name') call sites) makes name-usage case-insensitive and string-scoped — case-sensitive body matching misses them.

## Fix

Scope the lint until the signal-to-noise is real:
1. Skip TYPE/STRUCTURE blocks entirely (track block state; VAR/ROUTINE/BEGIN ends a TYPE block).
2. Narrow to a rare declaration type (BOOLEAN) where shared-bloat is smallest.
3. **Global two-pass filter**: first collect all candidate names per file, then check each name's usage (case-insensitive, including string literals) across the ENTIRE scanned corpus; only names unused everywhere — true orphans — are reported.
Keep such lints warn-level in quality gates (a warning channel), and run the strict version as a standalone census tool.

## Verification

Same corpus, same lint: 12,146 hits → 4 hits, and all 4 were genuine orphan/binding-break candidates. A hand-crafted negative fixture (declared BOOLEAN never used elsewhere) is still caught. The lint also went into a quality gate as warn-only, where a full 86-module regression stayed green while the negative fixture was flagged.
