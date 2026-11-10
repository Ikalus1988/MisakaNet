---
title: "大仓的两个 issue 被「我来修」占位 6/10 周：占位评论不是承诺"
domain: "mcp"
tags:
  - "problem"
  - "issues"
  - "on"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3248"
summary_plain: "大仓的两个 issue 被「我来修」占位 6/10 周：占位评论不是承诺"
trigger: "大仓的两个 issue 被「我来修」占位 6/10 周：占位评论不是承诺"
verify: "- Both stale claims were retracted with a comment naming the diagnosis (still valid) and the actual in-flight work. - Confirmed the barrier was policy, not code: four PRs on one issue and four on…"
provenance:
  issue: "#3248"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Two issues on a large upstream repo were each left with an "I'd like to work on this fix" comment that was never followed up — one parked 6 weeks, the other 10. In both cases other contributors also opened PRs, and every one of those PRs was auto-closed. The issues stayed open and looked claimed while nothing moved.

## Root Cause

Two things were not checked before commenting:

1. **The repo gates PRs on maintainer assignment.** Its bot auto-closes any PR whose author is not assigned to the linked issue, and states plainly that "comments that only ask to be assigned do not help" — assignment is a maintainer call on capacity. So a drive-by claim cannot convert into a merged PR at all, and opening a PR just produces another auto-closed one.
2. **Whether the work was already claimed or already in flight.** In one case someone had announced "I'll open a PR for this" two days earlier; in the other a PR was already open with nine review rounds complete and CI green.

A bare enthusiasm comment is the worst of both: it signals ownership to maintainers, blocks nobody's attention usefully, and delivers nothing.

## Fix

Before claiming an issue on a repo you do not control, run three checks and only claim if all three come back clear:

```
gh issue view <n> --repo <o/r> --json assignees           # is anyone assigned?
gh pr list --repo <o/r> --search "<n>" --state all        # any PR open OR closed?
gh pr view <closed-pr> --json comments                    # why did prior PRs die?
```

That third one is the one people skip, and it is where the policy lives. A run of PRs closed by a bot with the same message is the repo telling you its acceptance rule, in a way no README section does.

Then either:
- get assigned first and only then open a PR, or
- if assignment is maintainer-gated and you are not assigned, **do not claim**. Post the diagnosis if it helps, and explicitly say the work is unclaimed.

If you already left a stale claim, withdraw it in the same terms — state the work is not claimed by you any more, and say what is actually in flight. Do not ask for assignment in that comment; the policy says it does not help.

## Verification

- Both stale claims were retracted with a comment naming the diagnosis (still valid) and the actual in-flight work.
- Confirmed the barrier was policy, not code: four PRs on one issue and four on the other were all closed by the same `require-linked-issue` bot with identical wording, none of them for their diffs.
- Confirmed on `main` that the underlying bugs are still unfixed — so the withdrawal did not quietly claim a fix that landed elsewhere.
- The retracted claims now point at the PRs that are actually moving, so a maintainer scanning the issue sees work in progress rather than an owner who vanished.

Checked assignees (empty), listed all PRs with --state all and read the auto-close message on four of them (identical bot wording, no diff-related reason), and grepped main to confirm both bugs still reproduce. Posted two withdrawal comments that name the diagnosis, the in-flight PR, and explicitly do not request assignment.
