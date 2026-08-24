---
{
  "title": "Schemas coupled across repos break CI until the counterpart PR merges",
  "domain": "development",
  "tags": [
    "schema",
    "ci",
    "pr",
    "validation",
    "maintenance"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-11 00:00:00 UTC",
  "updated": "2026-08-11 00:00:00 UTC"
}

provenance:
  source: "unknown"
  contributor: "ElevaSync Solutions"
  merged_at: "2026-08-11"
  evidence: "post-publication"
---

# Schemas coupled across repos break CI until the counterpart PR merges

## Problem

A data repository changed a CSV header (e.g. renaming a column) and its CI failed with `'old_name' is a required property` / `Additional properties are not allowed ('new_name')`. The data change was valid; the validator being used came from a sibling tooling repo that still expected the old schema. No amount of data-side fixing cleared the check.

## Root Cause

The schema and the data lived in different repositories (a `data` repo + a `json-tools`/validator repo). CI on the data repo referenced the tooling repo's validator at its default branch, so the data PR stayed red until the *counterpart* schema PR in the tools repo was merged. Operators misread this as a data bug.

## Solution

Treat schema+data as one atomic change and communicate the pairing.

### Step 1
Check which repo actually owns the validator before "fixing" data. If a `schema.json`/validator lives upstream, the data change cannot go green alone.

### Step 2
Open the two PRs as a pair and note the coupling in both PR bodies: "schema-coupled: merge #A with #B".

### Step 3
If the tools PR is a prerequisite, merge it first, then rebase the data PR onto the new `main` so CI runs against the updated schema.

### Step 4
Optionally run the validator locally against your branch (extract it from the tools repo) to prove your data passes the target state.

## Verification

1. Data branch passes when pointed at the updated validator/tools branch.
2. Both PRs merge in dependency order (tools first).
3. CI is green post-merge for both.

## Notes

A red check is not always your fault — verify whether the failing check is schema-coupled to another repo before rewriting data. Rebase your data PR after the tools PR merges rather than squashing it pre-emptively.
