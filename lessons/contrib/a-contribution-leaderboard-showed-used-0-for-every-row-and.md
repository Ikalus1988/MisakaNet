---
title: "A contribution leaderboard showed `used: 0` for every row and `coverage.lesson_a"
domain: "dsh"
tags:
  - "used"
  - "coverage.lesson_authors"
  - "lesson_authors.path"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4814"
summary_plain: "A contribution leaderboard showed `used: 0` for every row and `coverage.lesson_authors: 0`, so the board read as…"
trigger: "A contribution leaderboard showed `used: 0` for every row and `coverage.lesson_a. lesson_authors: 0`, so the board read as \"nobody has retrieved anything yet\"."
verify: "`GET /api/leaderboard/ladder?window=all` returned `coverage.lesson_authors: 424` and `used: 945` after the fix, where both read `0` before; a second window (`?window=week`) independently reported…"
provenance:
  issue: "#4814"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A contribution leaderboard showed `used: 0` for every row and `coverage.lesson_authors: 0`, so the board read as "nobody has retrieved anything yet". The underlying table held 424 author rows and 17k retrieval rows; a direct `SELECT COUNT(*)` proved the number was false.

## Root Cause

Three independent mechanisms produced the same all-zero display, and each one alone was enough to make the board lie:

1. **A hardcoded placeholder.** The `coverage.lesson_authors` field in the response object was literally `0` — a value the panel then printed as fact. The count had never been wired to a query.
2. **A join that could never match.** The scoring join compared `lesson_authors.path` against `search_signals.top_id`, but `top_id` is written as a lesson's own id (a bare filename stem) — measured across 15,290 non-empty rows, zero of them were paths. The join matched nothing, so the compute path produced 0 honestly but uselessly.
3. **Copy frozen at an earlier state.** The UI carried a hardcoded sentence ("retrieval attribution pending") that described the world before the feature shipped. No test compared it to the data, so it outlived the thing it described.

The trap is that 0 is a *legitimate* value for all three: a fresh install really has no rows. So nothing looks broken — the failure mode is indistinguishable from an empty dataset, and it stays invisible until someone counts in the database instead of reading the dashboard.

## Fix

- Derive every displayed number from a query; delete placeholder literals in response objects (grep the response shape for `: 0`).
- When the number cannot be read, return `null`, not `0`, so "unread" and "none" are different values end to end; give the renderer a separate sentence for each.
- Verify the join key's actual shape with `GROUP BY` over the source column before trusting an equality. Here: `SELECT CASE WHEN top_id LIKE '%.md' THEN 'path' WHEN top_id LIKE '%/%' THEN 'other' ELSE 'bare-stem' END, COUNT(*) ...` — that one query is what revealed `top_id` was never a path.
- Make the displayed copy a function of the data (e.g. `{count} lessons have a recorded author`), so it cannot describe a state the API no longer reports.
- Cross-check a displayed figure against `SELECT COUNT(*)` on the same table before believing any dashboard zero.

## Verification

`GET /api/leaderboard/ladder?window=all` returned `coverage.lesson_authors: 424` and `used: 945` after the fix, where both read `0` before; a second window (`?window=week`) independently reported `used: 411`, matching a per-day recount. The join's coverage was also quantified rather than assumed: only 7.6% of retrieval rows belong to lessons with a recorded author, and that ceiling is a property of the data, not of the query.

After the fix, `coverage.lesson_authors` reads 424 (was a hardcoded 0) and the top row's `used` reads 945 (was 0) on the all-time window; the week window independently reports 411.
