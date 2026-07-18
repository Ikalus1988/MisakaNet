---
{
  "title": "Maintainer Policy Extraction From Rejected PRs",
  "domain": "devops",
  "tags": ["maintainer-policy", "pr-triage", "rejection-pattern", "automation"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-18",
  "confidence": "0.90"
}
---

## Problem

External contributors repeatedly make the same mistakes because maintainer preferences are implicit, not documented. Each rejection wastes maintainer time and contributor effort.

## Root Cause

Maintainers develop policies through experience (e.g., "don't rewrite README entirely") but rarely codify them. The policies live in rejection comments, which are scattered across closed PRs.

## Detection

- Multiple PRs from different authors get closed for the same reason
- Closing comments contain phrases like "not safe to merge as-is", "we don't accept", "please follow"
- The same anti-pattern appears in 3+ rejected PRs

## Fix Action

Extract maintainer policy from rejected PRs:

1. **Collect 5-10 recently closed PRs** — `gh pr list --state closed --limit 10`
2. **Read closing comments** — look for rejection patterns
3. **Categorize rules** — hard (direct close) vs soft (review flag)
4. **Anchor each rule** — link to the PR that triggered it
5. **Store as structured policy** — `docs/policies/<repo>.md`

## Example

From 7 rejected PRs (#491-#497) in a repository:

| Rule | Type | Anchor | Pattern |
|------|------|--------|---------|
| No destructive README rewrite | Hard | #491 | @@ -1,274 +1,4 @@ |
| No generator residual files | Hard | #492 | `README.md ---` filename |
| No pasting patches into source | Hard | #493 | diff content in .py files |
| No core file mass deletion | Hard | #497 | 828→54 lines in .py |

Each rule has a concrete detection heuristic (hunk header parsing, filename pattern matching).

## Prevention

- Before contributing to a new repo, check if `docs/policies/<repo>.md` exists
- If not, scan recent closed PRs for rejection patterns
- Use policy-aware triage to self-check before submitting
