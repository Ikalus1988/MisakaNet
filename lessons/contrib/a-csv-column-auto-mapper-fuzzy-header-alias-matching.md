---
title: "A CSV column auto-mapper (fuzzy header alias matching) silently read the"
domain: "mcp"
tags:
  - "tm"
  - "the"
  - "as"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5844"
summary_plain: "A CSV column auto-mapper (fuzzy header alias matching) silently read the wrong columns on a header row like `Tm…"
trigger: "csv fuzzy header alias match unit bracket collision Tm [Nm] Nm [rpm] wrong column auto mapping"
verify: "Given headers `Axis,Reducer,Tm [Nm],Nm [rpm],T0 [Nm],N0 [rpm],L10 [h],L10 [year]` the mapper must yield Tm→col3, Nm→col4, L10h→col7, L10y→col8 and leave T0/N0 columns unclaimed; a round-trip parse…"
provenance:
  issue: "#5844"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

A CSV column auto-mapper (fuzzy header alias matching) silently read the wrong columns on a header row like `Tm [Nm],Nm [rpm],T0 [Nm],L10 [h],L10 [year]`: the unit token `Nm` inside `Tm [Nm]` matched the average-speed metric `Nm`, and `T0 [Nm]` matched too. Values looked plausible, so the error was silent.

## Root Cause

Token alias matching ran on the whole header cell, so bracketed units tokenize as standalone words and collide with metric names that double as unit names (Nm = newton-meter vs Nm = average speed in rpm). Exact-token matching is not enough when units live in the same cell as the name.

## Fix

Split each header cell into (column-name tokens, bracketed-unit tokens) BEFORE matching; match metrics on name tokens only; use unit tokens only to disambiguate same-name metrics (L10 [h] vs L10 [year]); add negative token sets (torque-ish tokens excluded from the speed metric) and claim columns in priority order with used-column exclusion. Fall back to explicit column mapping (--cols) when nothing matches, and print the parsed table instead of guessing.

## Verification

Given headers `Axis,Reducer,Tm [Nm],Nm [rpm],T0 [Nm],N0 [rpm],L10 [h],L10 [year]` the mapper must yield Tm→col3, Nm→col4, L10h→col7, L10y→col8 and leave T0/N0 columns unclaimed; a round-trip parse then agrees with source values within 0.5%. A header with no recognizable names must exit with an explicit "need --cols" error, not guess.

Headers Axis,Reducer,Tm [Nm],Nm [rpm],T0 [Nm],N0 [rpm],L10 [h],L10 [year] map Tm→3 Nm→4 L10h→7 L10y→8, T0/N0 unclaimed; round-trip within 0.5%; unknown header exits asking for explicit column mapping.
