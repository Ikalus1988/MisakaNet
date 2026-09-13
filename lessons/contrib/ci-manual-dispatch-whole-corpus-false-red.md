---
title: "A manual CI run that sweeps the whole corpus always fails, so nobody trusts the red"
domain: "devops"
tags: ["github-actions", "ci", "workflow-dispatch", "false-positive", "legacy-debt"]
status: "published"
evidence_level: "E2"
created: "2026-09-13"
provenance:
  source: "MisakaNet maintainer run 34758013963, 2026-09-13"
---

# A manual CI run that sweeps the whole corpus always fails, so nobody trusts the red

## Problem

A maintainer dispatched the PR-audit workflow by hand to answer one question:
"do the tests still pass on `main`?" The test suite answered cleanly —
`1170 passed, 15 skipped` — and the run still finished red:

```
Audit failed: lesson schema validation failed.
##[error]Process completed with exit code 1.
```

The schema gate was not auditing anything related to the question. With no pull
request in the event payload, it had fallen back to validating **every** lesson
in the repository, where a large legacy fraction fails by design. Every manual
dispatch of that workflow ended the same way, so the red check carried no
information: the maintainer had to read the log to find out whether the failure
belonged to the thing being audited.

## Root Cause

The audit step was written for one trigger and silently reused for another:

```bash
if [ "${{ github.event_name }}" = "pull_request" ]; then
  mapfile -t TARGETS < <(git diff --name-only "$BASE_SHA" "$HEAD_SHA" -- 'lessons/**/*.md' 'lessons/*.md')
else
  mapfile -t TARGETS < <(find lessons -name '*.md' | sort)   # ← whole corpus
fi
```

On a PR the check is meaningful: only changed files are judged, and legacy debt
in untouched files is not the contributor's problem. The `else` branch was
written as a fallback for "some other event", but there is only one other event —
the manual dispatch, which has no PR context at all. So the fallback turned a
scoped, per-change gate into a corpus-wide gate that the corpus can never pass,
and the verdict logic (`if [ "$SCHEMA" = "fail" ]; then exit 1`) faithfully
reported failure.

The generalisable defect is not the schema rule. It is a **fallback that changes
the gate's scope instead of declining to run**: a check that fails for reasons
outside the thing under audit teaches everyone to ignore it, and the next real
failure is then ignored too.

## Solution

Make the scope an explicit property of the trigger, and let the gate decline
rather than substitute a different question:

```bash
PR_NUM="${{ github.event.inputs.pr_number }}"
if [ "${{ github.event_name }}" = "pull_request" ]; then
  mapfile -t TARGETS < <(git diff --name-only "$BASE_SHA" "$HEAD_SHA" -- 'lessons/**/*.md' 'lessons/*.md')
elif [ -n "$PR_NUM" ]; then
  # manual audit of one PR: judge that PR's lessons only
  mapfile -t TARGETS < <(gh pr diff "$PR_NUM" --repo OWNER/REPO --name-only | grep -E '^lessons/.*\.md$' || true)
else
  TARGETS=()
  echo "No PR context — schema gate skipped. Pass the pr_number input to audit a specific PR."
fi
```

Rules that follow from this incident:

- A gate's scope should come from the audited object (this PR, this commit), never
  from "whatever is in the working tree" as a fallback.
- If the scope cannot be determined, **skip and say so**; do not silently widen it.
- Give the manual trigger a way to name its target (here a `pr_number` input),
  otherwise the maintainer's only option is a run that cannot pass.
- Distinguish "the code is bad" from "the run is red". A red check must be
  actionable within the run itself.

## Verification

1. Dispatch the workflow with no inputs; confirm the schema step prints
   "schema gate skipped" and the overall verdict is green when the other gates
   pass. MisakaNet evidence: the manual dispatch of `7fcb00aef` (2026-09-13),
   which was previously red for exactly this reason in run 34758013963.
2. Dispatch it with the `pr_number` input set to an open PR that touches a lesson
   and confirm the schema step validates only that PR's files (the `gh pr diff`
   listing appears in the log).
3. Open a normal PR and confirm the changed-file scope is unchanged — this fix
   must not weaken the gate on real pull requests.
