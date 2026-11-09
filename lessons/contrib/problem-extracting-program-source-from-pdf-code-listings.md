---
title: "从 PDF 代码清单提取源码编译失败：折行与分页符把逻辑行拆开"
domain: "mcp"
tags:
  - "problem"
  - "extracting"
  - "program"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4607"
summary_plain: "Extracting program source from PDF code listings (printed with line numbers, e.g."
trigger: "Problem Extracting program source from PDF code listings (printed with line numb. Extracting program source from PDF code listings (printed with line numbers…"
verify: "Three source files (600-1700 listing lines each) went from \"KTRANS parse errors at random lines\" to clean structure: 683/1567/691 logical lines, routine counts 15/28/22 all complete with proper END…"
provenance:
  issue: "#4607"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Extracting program source from PDF code listings (printed with line numbers, e.g. via `pdftotext -layout`) and feeding the result to a compiler fails with scattered syntax errors ("BEGIN expected", bare words at line starts). The source looks complete in the PDF viewer but the extracted text is corrupted at seemingly random lines.

## Root Cause

Two layout artifacts of numbered listings in PDF text extraction:
1. **Wrapped long lines**: a logical source line printed across two PDF lines — the continuation (often prefixed by a form-feed char) lands on its own text line WITHOUT the `--` comment prefix or statement structure, so the parser sees orphan tokens.
2. **Bare-number lines**: empty source lines printed as just their line number (e.g. `43`) — a naive "strip `^\s*\d+` prefix" rule does not match (no trailing space), so the number glues onto the previous line as trailing junk.

## Fix

Reconstruct logical lines instead of stripping per-line:
- A raw line matching `^\s*\d+ ` (number + space) STARTS a new logical line; capture the rest as content.
- Any raw line NOT matching (including form-feed-prefixed continuations) is a WRAPPED CONTINUATION — append to the previous logical line with a single space.
- A raw line that is a bare number only → empty logical line (do not glue).
Watch for filenames ending in letters+digits (`NAME2INCR`) — those are real identifiers, not line numbers; only treat leading-column patterns as numbers.

## Verification

Three source files (600-1700 listing lines each) went from "KTRANS parse errors at random lines" to clean structure: 683/1567/691 logical lines, routine counts 15/28/22 all complete with proper END, and a name-level comparison against independently decompiled artifacts showed 100% routine-name recall. The glued-numbers variant left visible residue (`UNTIL(...) 421`) that vanished after the fix.
