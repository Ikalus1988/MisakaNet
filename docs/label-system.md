# Label System

How MisakaNet organizes issues and PRs.

## Issue Labels

### Pool — where does this issue belong?

| Label | Meaning | Review path |
|-------|---------|-------------|
| `pool:quick` | Docs, FAQ, journey, translation | Fast merge, skip deep review |
| `pool:deep` | Infrastructure, CI, MCP, integration | Needs design + maintainer review |
| `pool:roadmap` | Long-term architecture reference | Not active bounty |
| `pool:experiment` | Experimental, may be removed | May or may not land |

### Priority — when does this get done?

| Label | Meaning | Action |
|-------|---------|--------|
| `priority:now` | Active this sprint | Maintainer is tracking |
| `priority:next` | Queued after current work | Will open up soon |
| `priority:later` | Backlog, no timeline | Pick up when ready |

### Status — what's blocking this?

| Label | Meaning | What to do |
|-------|---------|------------|
| `status:ready` | Ready for someone to pick up | Go ahead |
| `status:needs-design` | Needs a proposal first | Open a design issue before coding |
| `status:blocked` | Blocked by dependency | Wait for blocker to resolve |
| `status:canonical` | Single entry point for this topic | Don't open duplicates |

### Contributor entry

| Label | Meaning |
|-------|---------|
| `good first issue` | Beginner-friendly, small scope |
| `help wanted` | Maintainer wants help |
| `bounty` | Has a reward (check issue for amount) |

---

## PR Labels

### Scope — what files changed?

| Label | Meaning | Review path |
|-------|---------|-------------|
| `docs-only` | Only docs changed | Fast merge |
| `tests-only` | Only tests changed | Fast merge |
| `lessons-only` | Only lesson files changed | Schema + DCO check only |
| `workflow-change` | CI/workflow files touched | Test CI carefully |

### Risk — how dangerous is this?

| Label | Meaning | Action |
|-------|---------|--------|
| `risk:high` | Touches core files or large deletions | Maintainer must review |

### Shape — what does the patch look like?

| Label | Meaning | Action |
|-------|---------|--------|
| `shape-safe` | Clean patch, normal review | Proceed |
| `shape-risk` | Suspicious patterns detected | Review shape first |
| `generated-file` | Contains auto-generated files | Confirm if intentional |
| `destructive-rewrite` | Replaces large sections | Must be approved |

*Shape labels are mutually exclusive. Highest priority wins.*

### Quality gate

| Label | Meaning | Condition |
|-------|---------|-----------|
| `needs-dco` | Missing Signed-off-by | Author must amend commit |
| `needs-rebase` | Has merge conflicts | Author must rebase |
| `ready-to-merge` | All gates passed | Maintainer can merge |

`ready-to-merge` requires ALL of:
- All CI checks passed
- No merge conflicts
- No `shape-risk` / `destructive-rewrite` / `generated-file`
- No `needs-dco`

---

## Quick Reference

**As a contributor, look for:**
- `priority:now` + `status:ready` → pick these up first
- `good first issue` → beginner-friendly
- `bounty` → has reward

**As a maintainer, filter by:**
- `pool:quick` → fast merge queue
- `pool:deep` + `priority:next` → prepare for next sprint
- `ready-to-merge` → can merge right now
