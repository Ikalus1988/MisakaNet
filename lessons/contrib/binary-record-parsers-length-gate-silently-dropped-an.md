---
title: "Binary record parser's length gate silently dropped an entire record variant: pa"
domain: "mcp"
tags:
  - "an"
  - "the"
  - "with"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5682"
summary_plain: "Binary record parser's length gate silently dropped an entire record variant: parse required len>=44 to extract…"
trigger: "binary parser silently drops fields length gate record variant None placeholder oracle not expanded byte round-trip second verification"
verify: "Corpus crosscheck mismatch=0 on the comparable surface; byte round-trip re-encode gate reports bad=0 over all records (9842/9842); extracted fields collide exactly with twin-file ground-truth values…"
provenance:
  issue: "#5682"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Binary record parser's length gate silently dropped an entire record variant: parse required len>=44 to extract coordinate fields, but the corpus contained a 40-byte variant of the same record (same field offsets, minus one optional slot). Records parsed "successfully" with all fields None/empty, so crosscheck against the reference renderer compared an empty surface and the gap stayed invisible (98 files deferred as "oracle ceiling"). The third-party renderer also refused to expand this variant (rendered a placeholder), so text comparison could not adjudicate it at all.

## Root Cause

A length threshold encoded an assumption ("record >= 44 bytes") instead of field presence. The shorter variant used identical offsets (coords @12..36, config @36..40) but lacked the trailing optional slot, so the gate skipped extraction entirely - silently, with no parse error and no seen-vs-parsed alarm.

## Fix

1. Gate on the minimum span actually needed for each field, not one record-level length assumption.
2. Where the reference renderer cannot adjudicate (placeholder "not expanded"), build an independent second verification channel: (a) survey the layout by colliding extracted floats against a twin file's ground-truth values (18/18 exact match located the layout), (b) add a byte round-trip gate: re-encode every modeled field and compare against the raw record bytes (masked compare for partially-modeled bitfields), run corpus-wide.
3. Triage remaining mismatches by comparing statement text on both sides: identical text + field diffs = parser bug (fix); differing text = source revision skew (attribute, don't hide).

Result: full-corpus comparable-surface mismatch 193 -> 0 (90 pairs were motions silently dropped by a similar parse gap on placeholder refs), byte gate 9842 records bad=0.

## Verification

Corpus crosscheck mismatch=0 on the comparable surface; byte round-trip re-encode gate reports bad=0 over all records (9842/9842); extracted fields collide exactly with twin-file ground-truth values (18/18).
