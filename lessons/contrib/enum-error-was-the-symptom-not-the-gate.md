---
title: "A validator's error names the symptom, not the gate; and a check script must not write to disk"
domain: "ci"
tags:
  - "gates"
  - "json-schema"
  - "required-fields"
  - "enum"
  - "check-script"
  - "dirty-worktree"
  - "exit-code"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "报错点名的那个字段往往只是症状，真正挡路的是整块必填字段；另外 check 脚本不该写盘，否则跑一次就弄脏工作树。"
trigger: "AUTOMATIC_POLICY_REJECTED must be compatible, incompatible, or unknown"
verify: "修完后 git status --porcelain 为空；且本地校验删掉任一 required 字段会立刻红并点名缺哪个字段"
source: "intake-3688"
provenance:
  issue: "#3688"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A validator's error names the symptom, not the gate; and a check script must not write to disk

## Problem

Two independent incidents with the same shape: **the error a validator prints is not the criterion
the validator checks**, so fixing the printed error burns a round trip and the rejection comes back
looking unchanged.

### Scenario A — an external source scanner

A repository was rejected by a fixed source scanner with this message, verbatim:

```
AUTOMATIC_POLICY_REJECTED: entries[0].compatibility.dshReleases.0.1.5-rc.1 must be compatible, incompatible, or unknown
```

It names one field and one enum. The field was changed to a value inside the allowed set and pushed
again — **rejected again**. The gate that was actually deciding was the same object's `required`
list: four properties were declared required and **none of them had been written**. The named field
was already legal at that point.

### Scenario B — a self-written check script wired into the release gate

A script named `verify-*.mjs` validated a release manifest and was added to the release gate. Two
things were wrong with it:

- It **rewrote the artifacts it was checking on every run** (the snapshot plus a source file). So
  "just run the check" dirtied the worktree, and `git add -A` then staged the regenerated target as
  part of this changeset.
- It **could not distinguish "the snapshot is out of step" from "the check never ran"**: a missing JS
  dependency also exited `2`, so the gate reported an environment failure as a content failure.

The reporter did not include the scanner's config, the schema file, or the `verify-*.mjs` source.
Those need reproduction to confirm; the commands below are shapes, not transcripts.

## Root Cause

**Scenario A.** A schema validator stops at the *first* failing keyword it reaches. `enum` on a
single property can be evaluated and reported before the object-level `required` check, so the
message points at the property that failed first, not at the predicate that decides admission.
Fixing that keyword removes the message and moves the failure to the next one — from outside, "still
rejected". A message of the form `must be X, Y or Z` is an enum complaint; it says nothing about
whether the object itself passes `required` or `additionalProperties: false`.

**Scenario B.** `check` and `refresh` are two contracts sharing one entry point. A check answers "does
the tree match the expected value" and must be read-only; a refresh writes. Making write the default
gives every invocation a side effect, and that side effect is indistinguishable from a real edit —
worst of all inside a gate, where `git add -A` is the natural next command.

Then one exit status was made to carry two meanings. `exit 2` for both "content mismatch" and
"could not run" forces the caller to guess, and the guess hides the environment problem inside a
content report.

## Solution

### Step 1 — Validate the whole object, not the named field

When a validator names a single field, inspect the schema for the object it belongs to — `required`,
`additionalProperties`, `oneOf` — before editing. The shape of the check is:

```bash
# illustrative shape only — the reporter's scanner/schema paths were not provided
jq '{required: .required, additionalProperties: .additionalProperties}' manifest.schema.json
jq 'keys' manifest.json        # diff against the required list, by hand
```

Pass criterion: the enum complaint is gone **and** the object reports no missing required property.
Add "no required property is absent" to your local validate step so the next omission is named
exactly ("missing required field: X"), not discovered as an enum error one round later.

### Step 2 — Split check from refresh

Keep the default entry point read-only; move writing behind an explicit flag.

```bash
node scripts/verify-manifest.mjs --check      # read-only: report differences, exit non-zero
node scripts/verify-manifest.mjs --refresh    # explicit second action: rewrite the snapshot
```

Pass criterion: after running the check, `git status --porcelain` is **empty**. A check that leaves
a modified file behind has become a generator.

### Step 3 — Separate the two failure kinds in the exit path

Content out of step and "the check could not run" must not share an exit status *and* must not share
a message. Give the environment branch its own prefix naming what is missing:

```
manifest out of step: keyCount 41 != 40
manifest could not run: cannot resolve 'yaml' — install dependencies first
```

Pass criterion: each branch is reachable on its own, and the missing-dependency message names the
missing module instead of saying "inconsistent".

## Verification

- **Scenario A:** run the scanner's own schema validation over the object and print `required`
  together with the resolved values. In the reporter's case all four required fields were absent
  while the named enum was already legal; after filling all four, validation passed. Deleting any one
  of them again must turn the local validate step red and name the missing field.
- **Scenario B:** `git status --porcelain` after the default (check) path must produce no output.
  Then deliberately corrupt `keyCount`: the check must go red for the *content* reason, and go green
  when restored.
- **Exit codes:** trigger the content branch and the missing-dependency branch separately; the two
  messages must not overlap.

## Notes

- Related shape, different failure: a script that always exits 0 in a gate slot —
  `lessons/contrib/report-only-verification-script-cannot-be-a-gate-step.md`.
- A validator that reports only the first failing keyword is a usability defect of the validator, but
  the caller still has to assume it: read the schema, not the message.
