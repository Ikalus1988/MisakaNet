---
domain: "meta"
title: "Scope parallel PRs by who owns the fact, not by file path, or two green PRs merge into a red main"
tags:
  - "pull-request"
  - "parallel-work"
  - "scope"
  - "contract-test"
  - "i18n"
  - "ci"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3482"
summary_plain: "Split PRs by file path leave other copies of one fact out of scope, so both pass CI and main breaks after merge."
trigger: "two PRs each green but main red after merge / managed count hardcoded in index.html and locales / contract test added in one PR violated by another"
verify: "Run PR A's contract test against PR B's artifact, not each branch: it fails on the residue and passes once the copy goes through the managed key."
provenance:
  issue: "#3482"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Scope parallel PRs by who owns the fact, not by file path, or two green PRs merge into a red main

## Problem

Two parallel PRs, each with a green CI, produced a red `main` after merge. The scoping rule was
**file paths**: `docs/locales/*` went to one issue, `docs/index.html` to another.

Case 1 — a managed number. The count "MCP tool count" was hardcoded in both `docs/index.html` and
`docs/locales/{en,zh}.json`. The PR that fixed the HTML could not touch the language packs, which
are what the site actually renders, so the site kept showing the old value.

Case 2 — a new contract crossed by another PR. One PR added a contract test saying "inside the
Quickstart block, no hardcoded UI copy may exist unless it goes through `data-i18n`". Another PR
added hardcoded bilingual link copy to that same block. Each PR was green on its own branch; after
merge the new test failed:

```
quickstart_prose() leftovers: 'Generate a pairing code / 生成配对码' —
test_quickstart_ui_copy_is_not_hardcoded_in_the_html would FAIL
```

## Root Cause

Scope was cut along **file paths**, but the unit that can break `main` is a **fact or contract**,
and one fact has several faces in a repository:

- the HTML fallback value rendered when i18n does not run;
- each locale JSON file (`en`, `zh`, ...);
- the SSOT script that is supposed to own the number;
- inline templates inside a worker;
- test fixtures that pin the expected copy.

A path boundary splits those faces across two issues. Each PR then verifies *its own branch*, and
no PR is responsible for the combination — so the failure only exists after the merge, where no
branch's CI can see it.

## Solution

Cut parallel scope by **fact / contract ownership**, not by file path.

1. Name the fact the issue governs (a managed count) or the contract it introduces ("no hardcoded
   copy in this block").
2. Grep for **every face** of that fact or contract: HTML fallback, locale JSON, SSOT script,
   worker inline templates, test fixtures.
3. Assign **each face to the same issue**, even when the files live in different directories.
4. For a new contract, make the closing evidence cross-PR: the contract test must be run against
   the other PR's artifacts, not only against its own branch.

## Verification

Cross-run the test rather than trusting per-branch green:

```bash
# point issue A's contract test at issue B's artifact, from a clean checkout of B's tree
pytest tests/test_site_i18n.py -k quickstart_prose
# FAILS, printing the two leftover strings — this reproduces the collision
```

- The conflict is confirmed when the test fails against the other PR's artifact while both PRs are
  individually green.
- It is resolved when issue B moves the copy to a `data-i18n` key plus bilingual entries and the
  same test reports `11 passed`.
- For a managed number, the check is that the SSOT function and every face agree, e.g.
  `grep -nE '7 tools|7 个工具' docs/locales/*.json` returning nothing while `canonical_mcp_tools()`
  returns `8`. In the reported case that grep returned two hardcoded spots — the language pack was
  the unmanaged second face.
