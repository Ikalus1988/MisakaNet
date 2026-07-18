---
{
  "title": "Learn From Merged PRs Before Submitting",
  "domain": "devops",
  "tags": ["pr-submission", "pattern-learning", "repository-culture", "first-contribution"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-18",
  "confidence": "0.92"
}
---

## Problem

Submitting a PR without studying the repository's merge history leads to format mismatches, missing requirements, and unnecessary review cycles.

## Root Cause

Each repository has implicit conventions for PR format, body structure, required badges, and diff granularity. These conventions are not always documented — they live in the pattern of merged PRs.

## Detection

- PR gets bot comments asking for missing elements (badges, format)
- PR body is long and argumentative while merged PRs are concise
- Diff touches more files or lines than typical merged PRs
- Reviewer asks "why didn't you follow the existing format?"

## Fix Action

Before submitting to an unfamiliar repository:

1. **Fetch 5-10 recently merged PRs** — `gh pr list --state merged --limit 10`
2. **Study the diff pattern** — how many files, how many lines added
3. **Study the body pattern** — length, structure, required elements
4. **Check for required badges/configs** — Glama, CI status badges, etc.
5. **Match your PR to the observed pattern**

## Example

Repository `awesome-mcp-servers` (91k stars):

Merged PRs all follow this exact pattern:
```
- [owner/repo](url) [![badge](glama-badge-url)](glama-link) emoji - One line description. `pip install xxx`
```

Body: 1-3 sentences, no arguments about category placement.

A PR that deviates (missing badge, long body arguing about placement) gets bot-flagged and waits 14+ days.

## Prevention

- Always read 5+ merged PRs before first contribution
- Copy the exact format of the most recent merged PR in the same section
- Keep body under 5 sentences for list-addition PRs
