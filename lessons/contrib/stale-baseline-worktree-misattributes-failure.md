---
title: "A stale 'clean baseline' checkout misattributes a failure to the wrong change"
domain: "git"
tags:
  - "git-worktree"
  - "baseline"
  - "pre-existing-failure"
  - "evidence"
  - "ci"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "拿一个没更新的 baseline 工作树做对比，会把老问题算成这次改坏的，也会把别人已经修好的算成自己的功劳。"
trigger: "baseline worktree stale; failure called pre-existing from an outdated checkout"
verify: "git -C <worktree> rev-parse HEAD 与 git rev-parse origin/main 输出同一个 SHA，且报告里每处 pre-existing 判断都点名该 SHA"
source: "intake-2674"
provenance:
  issue: "#2674"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A stale 'clean baseline' checkout misattributes a failure to the wrong change

## Problem

Comparing a change against a "clean baseline" that was actually a stale checkout attributes the
failure to the wrong cause. The comparison looks rigorous and is wrong twice over: it blames the
change for problems the baseline already had, and it credits the change with fixes it did not make.

Concrete shape reported by the contributor: a quality command exits 1 on the current tree. To find
out whether that is pre-existing, it is re-run "on the baseline" — an existing checkout or worktree
that was left on a branch some commits behind. That run also fails, so the conclusion is
"pre-existing, not my change". The baseline was simply too old to show the real state: it was
missing the very commits whose effect was in question.

The same trap runs the other way. A tool reported "gate passes on baseline" from a checkout that did
not yet contain a recent regression, so the regression looked introduced by the current work when it
was already on the main line.

Reporter's one-line summary of the failure:

```
change blamed for failures that were already on the baseline; baseline turned out to be an outdated checkout
```

## Root Cause

A worktree or checkout is a **snapshot of when it was created or last updated**, not a live view of
the branch. Nothing warns you that `git worktree list` shows a branch name whose ref has moved on.
Naming it "clean main" is an assertion you did not verify.

It is tempting because it saves a fetch and a fresh clone. But the baseline is exactly where
correctness matters: every conclusion drawn from it inherits its staleness.

The reporter's test plan was wrong at the level of evidence, not of command syntax: re-running a
command in a directory labelled "clean" answers "what does this directory contain", never "what does
`origin/main` contain today". The label was the only thing making the two look equivalent.

## Solution

Pin the baseline to a SHA and say which one.

```bash
git fetch origin main
echo "baseline = $(git rev-parse --short origin/main)"   # print it, do not assume
rm -rf /tmp/baseline
git worktree add -q /tmp/baseline origin/main
cd /tmp/baseline && git rev-parse --short HEAD           # must match the line above
```

If the worktree is reused, update it before trusting it:

```bash
git -C /tmp/baseline checkout -B main origin/main
```

Then capture the status properly — not through a pipe — because the exit status of a pipeline is the
status of its last command. The reporter's intake describes this as "the `$?`-after-pipeline
pitfall" and points at a redirection-based capture; the snippet itself was truncated in the intake at

```
cd /tmp/baseline && python3 validate.py --strict > /tmp/bas
```

so the full line is not preserved here. What the reporter states as the requirement is: capture the
exit status outside the pipe.

The general rule the report draws: any claim of the form "pre-existing" or "passes on baseline" must
name the baseline SHA it was measured against. A claim without a SHA cannot be audited and is
indistinguishable from a guess.

## Verification

The reporter's own pass/fail criterion, verbatim from the intake:

```
git -C worktree rev-parse HEAD equals git rev-parse origin/main; any "pre-existing" claim in a report names that SHA
```

Concretely:

```bash
test "$(git -C /tmp/baseline rev-parse HEAD)" = "$(git rev-parse origin/main)" && echo BASELINE_MATCHES
```

A mismatched pair means the baseline is stale and every conclusion drawn from it must be discarded
and re-measured. Independently re-run the quality command on the pinned baseline and on the current
tree, capturing each status without a pipe, and compare the two exit codes.

## Notes

- The full command the reporter used to capture status was truncated in the intake; the exact
  redirection form needs reproduction before being copied (`报料者未给出，需复现确认`).
- The reporter did not include the quality command itself (`validate.py` is the placeholder used in
  the truncated snippet), so the specific gate is not identified here.
- This is a lesson about baseline *provenance*, not about `git worktree` mechanics; the same failure
  occurs with a second clone, a stale CI cache, or a locally checked-out tag.
