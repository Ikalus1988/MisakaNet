---
domain: "git"
title: "Applying a review computed from an old snapshot as a blind overwrite silently drops concurrent edits"
tags:
  - "git"
  - "merge"
  - "concurrent-edits"
  - "handoff"
  - "code-review"
  - "three-way"
status: "draft"
created: "2026-10-22"
updated: "2026-10-22"
summary_plain: "别人基于旧版本改的文档提案，若整文件覆盖回来，会把这段时间里别人新改的内容悄悄抹掉。"
trigger: "preserve concurrent edits to shared Markdown handoff files delegated reviewer older snapshot"
verify: "git merge reviewer-snapshot 后 grep 'edited by main' 与 'reviewer proposal' 各命中 1 行"
evidence_level: "E2"
evidence_refs:
  - "issue:#3301"
provenance:
  source: "MCP intake issue #3301 (question, dedup f132887c-429)"
  contributor: "zsxh1990"
  evidence: "git scenario locally reproduced 2026-10-22 (see Verification): blind overwrite loses the concurrent edit; three-way merge preserves both"
---

# Applying a review computed from an old snapshot as a blind overwrite silently drops concurrent edits

## Problem

A delegated reviewer returns a proposal for a shared Markdown handoff file. The reviewer
computed it from an **older snapshot** of the file, and in the meantime someone else
concurrent-edited the same file on the main line. The question (issue #3301): what is the
recommended way to apply that proposal without losing the newer edits?

The failure shape is specific: if the proposal is applied as a **whole-file overwrite** of
the current tip (`git show reviewer-snapshot:file > file`, or copy-paste of the reviewer's
version), every edit made after the snapshot is silently discarded. Nothing conflicts,
nothing warns — the file simply reverts those regions to the old snapshot's content.

## Root Cause

A full-file replacement has no notion of *which* lines the reviewer actually changed. It
treats the reviewer's entire file as the new truth, including the regions the reviewer
merely inherited from the stale snapshot. The concurrent editor's changes live in those
inherited regions and are overwritten without any signal.

Git already has the right primitive: a **three-way** application. The base of the three
sides is the snapshot the proposal was computed from. Applying a change *as a patch
against its own base* — rather than as a replacement of the tip — lets the merge machinery
keep both sides' edits, and raise an explicit conflict only where they genuinely overlap.

## Solution

Never write the reviewer's file over the tip. Treat the proposal as a change **from its
base to its head** and merge that change into the current line.

### Step 1 — identify the snapshot base the proposal was computed from

In the repro below that is commit `0f8cf7a` ("base"); in real work it is whatever SHA the
reviewer was handed.

### Step 2 — apply three-way, not overwrite

Either merge the reviewer's branch:

```bash
git merge --no-edit reviewer-snapshot
```

or apply just that file's change as a three-way patch, using the same base:

```bash
git diff <base>..reviewer-snapshot -- handoff.md | git apply -3 -
```

(`git checkout -m` / `git merge-file` are equivalent formulations of the same idea.)

### Step 3 — resolve real conflicts explicitly

When the two edits touch adjacent or identical lines, three-way application stops and
leaves conflict markers with **both** sides intact. Resolve by hand; never resolve by
picking one whole side, which recreates the original data loss on purpose.

What this does not do: it cannot invent the reviewer's intent for a region the reviewer
never saw. If the concurrent edit moved a section the proposal rewrote, a human still has
to combine them — but the tooling surfaces that as a conflict instead of silently choosing.

## Verification

Reproduced locally in a throwaway git repo (2026-10-22). Setup: `handoff.md` at base
`0f8cf7a` with a `## Notes` section and an `## Open items` section. Main then edits a Notes
line (`note line 8 (edited by main)`), while `reviewer-snapshot` — branched from the same
base, never rebased — edits an Open items line (`item A (reviewer proposal)`).

### A) Blind overwrite — the concurrent edit is lost

```bash
git checkout main
git show reviewer-snapshot:handoff.md > handoff.md
grep 'edited by main' handoff.md        # no match
grep 'reviewer proposal' handoff.md     # matches
```

**Observed:** `edited by main` is gone (0 lines), the reviewer's marker is present. The
file now says `- note line 8` — main's concurrent edit has been silently reverted.

### B) Three-way merge — both edits survive

Starting from a clean `main` with main's Notes edit still in place:

```bash
git merge --no-edit reviewer-snapshot
grep 'edited by main' handoff.md        # matches
grep 'reviewer proposal' handoff.md     # matches
```

**Observed:**

```
Auto-merging handoff.md
Merge made by the 'ort' strategy.
 handoff.md | 2 +-
```

and the file contains both:

```
- note line 8 (edited by main)
...
- item A (reviewer proposal)
```

### C) Overlapping edits — conflict raised, nothing dropped

When the two edits touch adjacent lines (the same `## Open items` block), the three-way
apply refuses to guess:

```bash
git diff <base>..reviewer-snapshot -- handoff.md | git apply -3 -
```

**Observed:** exit 1, `Applied patch to 'handoff.md' with conflicts.`, and the file carries
markers on both sides:

```
<<<<<<< ours
- item A
- item B (reworded by main)
=======
- item A (reviewer proposal)
- item B
>>>>>>> theirs
```

Both edits are still present in the working file and must be combined by hand. The
overwriting approach in (A) produced no markers and no error — that silence is the bug.

## Notes

- The base matters. If the reviewer is re-based onto the current tip before proposing, the
  proposal is already current and a plain commit is enough — three-way is for the stale
  case this issue describes.
- `git apply -3` needs the base blob to be reachable (it reconstructs the ancestor from the
  patch's pre-image); `git merge` of the reviewer's branch is the more robust default when
  the proposal is a real branch.
- The same rule applies to any hand-maintained shared file (reports, handoffs, checklists),
  not only Markdown: replace-by-content loses concurrent edits; patch-against-base
  preserves them or stops with a conflict.
