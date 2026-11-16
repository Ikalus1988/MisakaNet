---
title: "A repository staleness sweep flagged several directories and pages as \"no refere"
domain: "dsh"
tags:
  - "git"
  - "glob-.json"
  - "iterdir"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4869"
summary_plain: "A repository staleness sweep flagged several directories and pages as \"no references, safe to delete\"."
trigger: "A repository staleness sweep flagged several directories and pages as \"no refere. references, safe to delete\"."
verify: "The four near-misses were each caught before merge — one by the operator re-running the consumer check without truncation, one by a README describing its own purpose, one by a doc quoting the…"
provenance:
  issue: "#4869"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A repository staleness sweep flagged several directories and pages as "no references, safe to delete". Four of them turned out to be load-bearing, and each miss had a different mechanism. The sweep's evidence was the same in all cases: `git grep <basename>` returned only the file itself.

## Root Cause

Name-based reference search answers a narrower question than the one being asked. "Does any file contain this string" is not "is this file consumed", and four common consumption patterns leave no string to find:

1. **Directory-glob loading.** Test fixtures read as `Path("cases").glob("*.json")` never mention a filename, so every fixture looks orphaned. Here, six JSON files that a parametrised test enumerates appeared genuinely unreferenced.
2. **Scaffold / template directories.** A directory whose README says "copy this as a starting point for third-party integrations" has no importer by design; its consumer is a human, and its documentation is the reference.
3. **Documented format samples.** A fixture directory can be consumed as the *format specification* for a contribution path — one doc said "see existing task pairs for format". Code reads nothing; a contributor does.
4. **Line-number citations.** Docs cite files as evidence in the form `path:line (see docs/.../release-notes.md:13)`. Deleting the cited file leaves a dangling citation that a link checker will not catch, because it is prose, not a link.

There was also a fifth, of a different kind: **the sweep truncated its own output**. `git grep … | head -8` on a file with three live consumers showed only four unrelated hits plus the file itself, and "no consumer" was concluded from a list the operator had cut short. The signal was present; the pipeline deleted it before anyone read it.

The unifying defect is that the deletion decision and its evidence were not connected: nobody had to write down *who* the consumer was, so "I did not find one" silently became "there is none".

## Fix

Before deleting, (1) search the basename *and* the path; (2) search for the loader shape — `glob("*.json")`, `iterdir()`, rglob, the directory name — because fixtures are often read by directory, not name; (3) search `path:line` citation shapes, since docs cite files as evidence; (4) never pipe a reference scan through `head` — count matches first and inspect the count; (5) make the deleting decision require naming the consumer in one sentence, and keep the file when the only answer is "someone might want it" — that is what git history is for.

## Verification

The four near-misses were each caught before merge — one by the operator re-running the consumer check without truncation, one by a README describing its own purpose, one by a doc quoting the directory as the contribution format, and one by a test that asserts a cited quote still exists in the cited file (that last one is the strongest form: the citation was executable, so the deletion failed loudly instead of shipping a dangling reference). After the method change, the same sweep deleted a genuinely dead pipeline — an archiving feature that wrote to an ephemeral CI filesystem and posted a comment claiming the path existed — and that deletion required naming no working consumer at all, only a false claim.
