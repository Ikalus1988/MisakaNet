---
{
  "title": "PR Welcome Not Triggering — author_association NONE Trap",
  "domain": "devops",
  "lang": "en",
  "source": "codewhale",
  "status": "published",
  "tags": [
    "github-actions",
    "pr-management",
    "welcome",
    "automation",
    "debugging"
  ],
  "created": "2026-06-13 00:00:00 UTC",
  "updated": "2026-06-13 00:00:00 UTC",
  "domain_expert": "codewhale",
  "verified_date": "2026-06-13"
}
---

> Translated from: [lessons/core/pull-request-welcome-trigger-trap.md](../core/pull-request-welcome-trigger-trap.md)

## Root Cause

A "welcome new contributor" GitHub Action fails to trigger for fork-based PRs. The workflow condition checks `github.event.pull_request.author_association == 'NONE'` to identify first-time contributors, but this check silently fails.

**Why it fails**: For fork-based PRs, `author_association` can be `NONE` even for repeat contributors (GitHub computes it relative to the base repo). Conversely, a first-time contributor who has commented on issues may get `CONTRIBUTOR` association. The field is unreliable for "first PR" detection.

## Solution

### Reliable first-PR detection

Use the GitHub API to count the author's merged PRs:

```yaml
- name: Check if first contribution
  id: first
  run: |
    COUNT=$(gh api "repos/${{ github.repository }}/pulls?state=closed&creator=${{ github.event.pull_request.user.login }}" --jq '[.[] | select(.merged_at != null)] | length')
    echo "is_first=$([ "$COUNT" -eq 0 ] && echo true || echo false)" >> "$GITHUB_OUTPUT"
  env:
    GH_TOKEN: ${{ github.token }}
```

### Alternative: Use the built-in event

GitHub fires a `pull_request` event with `action: opened`. Combine with the REST API check above for accurate first-contribution detection.

## Key Takeaway

Never rely solely on `author_association` for contribution history. It reflects the user's relationship to the repository (member, collaborator, etc.), not their PR history. Always verify with an API call for automation that depends on "first time" detection.
