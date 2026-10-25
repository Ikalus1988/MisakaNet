---
domain: "meta"
title: "An issue's inventory goes stale: check every acceptance item against the tree before writing code"
tags:
  - "issue-triage"
  - "acceptance-criteria"
  - "stale-state"
  - "pull-request"
  - "tests"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3477"
summary_plain: "The issue said no parity test existed, but upstream already had it; check each acceptance item against the tree first."
trigger: "issue says nothing checks locale parity but the test already exists / stale counts in the issue body / half the goal landed via another PR"
verify: "Before coding, each acceptance item is checked against the tree: the named test exists and passes, and the PR adds only the untested half."
provenance:
  issue: "#3477"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# An issue's inventory goes stale: check every acceptance item against the tree before writing code

## Problem

Implementing an issue whose **current-state description was stale**. The body said:

> locales have 100 keys, nothing checks parity, no test exists

The live tree already had **154 keys**, full key coverage, and `tests/test_site_i18n.py` — the
parity test — landed through an unrelated PR. Writing code from the issue body alone would have:

- duplicated an enforcement that already existed, and
- invented copy the parent explicitly forbade.

An issue body is a snapshot taken at filing time; the repository keeps moving while the issue sits
in the queue. Nothing in "implement this issue" tells you to re-measure, so the default action is
to build what the prose says, not what the tree lacks.

## Root Cause

The issue is a **description**, while the acceptance items are supposed to be **observables**. When
the two diverge, the description wins by default because it is the only text in front of the
implementer: counts age, "no test exists" stops being true the moment someone else adds one, and
half of a goal list can be closed by a side PR without the issue being updated.

There is a cheap signal that is ignored: a "add a test for X" item names a file. If that file
already exists, the half is done — regardless of what the prose says.

## Solution

Treat the acceptance items, not the prose, as the spec; diff each one against the worktree before
writing anything.

1. **For each acceptance item, diff the live tree** — not the issue's counts or its "nothing checks
   this" claims.
2. **For "add a test for X", grep `tests/` for the filename the issue names.** An existing file
   that arrived through a side PR means that half is complete.
3. **Identify the untested half of the goal list and add only that.** In the measured case, key
   parity was already enforced while "no hardcoded copy in the section" had zero enforcement — the
   only deliverable left.
4. **State the pre-existing state in the PR body** so the reviewer understands why the diff is
   smaller than the issue implies.
5. **Keep negative-test evidence even when the gate already existed**: delete a key, watch the test
   go red, restore it, watch it go green.

Useful pre-flight commands (as reported):

```bash
gh issue view <N>
git log --diff-filter=A -- tests/test_site_i18n.py   # did the named test file arrive already?
grep -rn "def test_" tests/ | grep -i "<area>"
pytest tests/ -q                                     # what is already green today?
```

## Verification

The evidence that the triage was done, and not just claimed:

- The PR diff is **one test file** — no duplicated parity test, no invented copy.
- The PR body records what already existed (the parity test and the 154-key coverage) and what the
  change adds (enforcement of "no hardcoded copy in the section").
- The red run and the green restore are pasted in the PR body: deleting a key produced `3 failed`,
  including the parity test naming the deleted key; restoring it returned to green.
- `pytest tests/` collection lists the new test node ids, so the added enforcement is discoverable
  rather than implied.
