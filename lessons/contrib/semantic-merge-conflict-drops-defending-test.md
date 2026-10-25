---
title: "Resolving a semantic merge conflict by taking one side silently deletes the other side's tests"
domain: "git"
tags:
  - "git"
  - "merge-conflict"
  - "semantic-conflict"
  - "tests"
  - "code-review"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Taking one side of a semantic conflict deletes the other side's test; the breakage shows up only after the merge."
trigger: "semantic merge conflict resolved by taking the deletion side; the other side's test fails: the note vanished instead of moving to stderr"
verify: "Run the tests for both sides' concerns after resolving, and grep tests/ and docs/ for the discarded side's distinctive phrase; any hit means an intent still has a defender."
source: "intake-2734"
provenance:
  issue: "#2734"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Resolving a semantic merge conflict by taking one side silently deletes the other side's tests

## Problem

Resolving a semantic merge conflict by taking one side silently deletes the other side's
*tests*, and the breakage only surfaces after merge.

Both branches edited the same function for different reasons:

- `main` kept a feature and moved its reporting out of a generated file onto stderr, adding a
  test asserting the report still reaches a human;
- the other branch deleted the feature entirely.

The textual overlap was one block. Resolving "take the feature-deletion side" removed the feature
**and** the line that emitted the report — and with it, the thing `main`'s new test existed to
defend. The test then failed:

```text
FAILED test_the_note_about_the_<feature>_reaches_a_human
AssertionError: the <feature> note vanished instead of moving to stderr;
nobody reading the log learns it happened
```

The reasoning that led there was not careless: "with those statements gone, the warning they
carried has nothing left to warn on." That is true of the *warning*. It says nothing about the
*test*, which was defending observability, not the warning.

Repository, branch names and the real feature name appear here as placeholders because the
reporter did not give them; the case needs to be reproduced.

## Root Cause

A semantic conflict is one where both sides changed the same logic with different intents.
Picking either side is not a merge — it is a decision to discard an intent. The discarded intent
usually leaves artifacts (tests, docs, CI assertions) that still defend it, so the cost lands
later and somewhere else.

Reading the conflict hunk shows you two implementations. It does not show you what else in the
tree depends on either one. The test lives in another file, and nothing in `git status` after the
merge tells you it was defending the side you just dropped.

## Solution

**Before resolving, find what else references both intents.**

```bash
# what does the side you are about to discard rely on?
git diff $(git merge-base HEAD origin/main)..origin/main --name-only
grep -rn "the distinctive symbol or phrase from their change" tests/ docs/
```

If a test defends the intent you are discarding, you have a real decision, not a mechanical merge:

- delete the test **with** the feature, and say so in the commit — coherent: the intent and its
  defender leave together.

The reporter's option list is cut off after that first item; the remaining options were not given
and need to be enumerated by reproducing the case.

## Verification

- Run the tests for **both** sides' concerns after resolving — not only the side you kept.
- Grep `tests/` and `docs/` for the phrase their test asserts. A hit means the discarded intent
  still has a defender, so the merge is not finished; the decision to drop it has to be made
  explicitly rather than inherited from a conflict hunk.
- Watch specifically for tests that assert an observable side effect of deleted code (a log line,
  a stderr note, a report). They pass review and fail after merge, which is the expensive order.
