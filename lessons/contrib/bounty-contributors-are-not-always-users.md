---
{
  "domain": "growth",
  "title": "Bounty Contributors Are Not Always Users",
  "tags": ["bounty", "contributors", "growth", "feedback", "community"],
  "status": "published",
  "source": "generalized contributor funnel analysis",
  "created": "2026-07-17",
  "confidence": "0.88"
}
---

## Problem

Bounty or task labels can attract contributors who submit valid pull requests but never become users of the product, readers of the knowledge base, or members of the community.

A merged PR from a task-driven contributor does not prove the contributor found the core knowledge useful.

## Root Cause

Bounty-driven traffic often follows a shallow path:

```text
find task -> claim task -> clone repo -> submit PR -> leave
```

The desired knowledge loop is different:

```text
hit problem -> search lesson -> solve problem -> leave feedback -> contribute experience
```

When these paths are confused, maintainers may mistake temporary labor for community adoption.

## Solution

### 1. Separate task execution from usefulness proof

Track these metrics separately:

| Metric | Meaning |
|---|---|
| PR merged | Task completed |
| Repeat contributor | Relationship forming |
| Lesson cited in PR | Knowledge was used |
| Feedback issue | User engaged with knowledge |
| Helpful vote | Lightweight usefulness signal |

### 2. Ask one low-friction follow-up question

After a PR is merged, ask for signal, not more work:

```text
Did any lesson, doc, or search result help while working on this PR?
A short yes/no is already useful.
```

If the answer is no, that is still useful evidence. It means the contribution path did not intersect the knowledge path.

### 3. Reduce PR template friction

For small fixes, use a lightweight template:

```md
## What changed?

## Why?

## Checklist
- [ ] I tested or checked the change
- [ ] I signed off commits if required

## Optional: did any lesson help?
```

### 4. Avoid misleading reward language

If an issue has a bounty label but no explicit funded reward, say so clearly. Ambiguous reward expectations damage trust.

## Verification

- Contributor follow-up response rate is measured.
- Repeat contributors are tracked separately from one-time task submitters.
- Release notes do not use PR count as proof of lesson usefulness.

## Next Agent Prompt

Before calling a contributor a user, check whether they used the product's core value path. A task completed under a bounty label is not the same as adoption.
