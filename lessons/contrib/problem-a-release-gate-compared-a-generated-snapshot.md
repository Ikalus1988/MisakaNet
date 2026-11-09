---
title: "Problem A release gate compared a **generated snapshot** against what its genera"
domain: "mcp"
tags:
  - "problem"
  - "release"
  - "gate"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3939"
summary_plain: "A release gate compared a **generated snapshot** against what its generator would produce, and failed — every single…"
trigger: "Problem A release gate compared a **generated snapshot** against what its genera. A release gate compared a **generated snapshot** against what its generator…"
verify: "Mutate in **both** directions — a fix that only turns the gate green is worth nothing: | mutation | before | after | |---|---|---| | only `fetchedAt` changed | red | **passes** | | one real key…"
provenance:
  issue: "#3939"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

A release gate compared a **generated snapshot** against what its generator would produce, and failed — every single day — even when the upstream source had not changed. The entire diff was one line: `fetchedAt: '<today>'`. The generator always rewrote the fetch date to the current day, and the check compared the regenerated text **whole-text**, so the gate was effectively asking "did you run this today?" instead of "is the upstream content still what we have?".

A gate that cries wolf every morning is worse than no gate: people stop reading it, and the day it reports real drift nobody is looking.

## Root Cause

Two kinds of value were treated as one. `fetchedAt` records **when we fetched** — it is a property of our run. `blobSha` / `keyCount` / the key set record **what upstream has** — properties of the content. Only the second kind is drift.

The comparison was a whole-text equality check (`regen.text !== srcText`), which cannot tell the two apart.

## Fix

Split them:
1. Normalise the run-time field out of **both** sides before comparing (`fetchedAt: '...'` → `fetchedAt: '<normalized>'`).
2. Make the generator bump the run-time field **only when the content actually changed**, so a refresh no longer churns a line of git history on every run.

## Verification

Mutate in **both** directions — a fix that only turns the gate green is worth nothing:

| mutation | before | after |
|---|---|---|
| only `fetchedAt` changed | red | **passes** |
| one real key deleted | red | red ("104 key(s) in the snapshot vs 105 parsed") |
| restore | — | green |

The second row is the one that keeps the fix honest: normalising must not weaken the check's ability to see real drift. The gate then exits 0 and reports "all claims hold against the live tree".

Change only the timestamp field in the generated file and confirm the gate passes; delete one real entry and confirm it still fails with a key-count diff naming the mismatch. Both directions were run and the gate exited 0 afterwards with "all claims hold against the live tree".
