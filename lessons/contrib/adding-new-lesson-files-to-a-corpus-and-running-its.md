---
title: "Adding new lesson files to a corpus and running its generator suite leaves the t"
domain: "mcp"
tags:
  - "rglob"
  - "and"
  - "the"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5032"
summary_plain: "Adding new lesson files to a corpus and running its generator suite leaves the tree half-updated: some generators…"
trigger: "Adding new lesson files to a corpus and running its generator suite leaves the t. tree half-updated: some generators index the new lessons and others silently…"
verify: "1. grep the new slugs in data/lessons.json — non-zero after staging+running (zero before = the bug). 2. Re-run update_lessons_json.py + build_lesson_pages.py after staging; `git status --porcelain`…"
provenance:
  issue: "#5032"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Adding new lesson files to a corpus and running its generator suite leaves the tree half-updated: some generators index the new lessons and others silently skip them.

## Root Cause

The corpus has two readers that disagree on "what counts as a lesson". `misakanet/lesson_index.py:tracked_lesson_files` builds the index from `git ls-files` (git-TRACKED files only, by design — so editor scratch/draft `.md` files don't pollute the search corpus). But `rebuild_lessons_index.py` and `export_public_vocabulary.py` enumerate the filesystem with `rglob` (tracked AND untracked). So when you add new lesson files and run the generators BEFORE staging them:
- `update_lessons_json.py` and `build_lesson_pages.py` (git-tracked reader) SILENTLY skip the untracked lessons — lessons.json count stays flat (e.g. 944), no new lesson pages written.
- `rebuild_lessons_index.py` and `export_public_vocabulary.py` (rglob reader) DO pick them up — lessons/index.md grows, public-vocabulary.json grows.
Result: a half-updated tree (index has the lessons, lessons.json does not) that fails the "generators are a no-op on the committed corpus" CI check.

## Fix

Stage the new lesson files (`git add lessons/contrib/<slug>.md`) BEFORE running the generators, so the git-tracked reader sees them. Then run the full generator set in CI order: update_lessons_json, build_lesson_pages, export_okf, sync_lesson_count, rebuild_lessons_index, gen_ranking_snapshot, export_public_vocabulary, evidence_distribution. The lesson count should bump (e.g. 944 -> 949 for 5 new lessons) and build_lesson_pages should report writing new pages.

## Verification

1. grep the new slugs in data/lessons.json — non-zero after staging+running (zero before = the bug).
2. Re-run update_lessons_json.py + build_lesson_pages.py after staging; `git status --porcelain` shows no further unstaged drift (generators are a no-op = tree self-consistent).
3. The lesson count reported by update_lessons_json / sync_lesson_count equals old count + number of new lessons.
