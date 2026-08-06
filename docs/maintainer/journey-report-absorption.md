# Journey Report UX Findings — Absorption Tracker

Date: 2026-08-06
Source: #830 journey reports (#850, #836, #834, #833, #847, #851)

## Summary

Journey reports from 6 contributors revealed consistent UX friction points. This tracker ensures findings are absorbed into docs, issues, or lessons — not just recorded.

## Findings Matrix

| ID | Finding | Severity | Source | Absorbed? | Action |
|----|---------|----------|--------|-----------|--------|
| **UX-1** | Token acquisition undocumented | Blocking | #850, #836, #834, #833, #847 | ❌ | Need: docs update or self-service token flow |
| **UX-2** | Search empty state confusing | Medium | #850, #836 | ❌ | Need: better "no results" messaging |
| **UX-3** | Post-registration wait/refresh unclear | Medium | #850 | ❌ | Need: UX copy in registration flow |
| **UX-4** | README vs issue body discovery path | Low | #850 | ❌ | Need: unified first-touch strategy |
| **UX-5** | Workflow 403/bot label misleading | Medium | #850, #836 | ❌ | Need: docs explaining CI behavior for new contributors |
| **UX-6** | Error messages don't guide to fix | Low | #834, #833 | ❌ | Need: actionable error responses |

## Detail per Finding

### UX-1: Token Acquisition (Blocking)

**Problem**: `docs/integrations/mcp-remote.md` says `Bearer YOUR_TOKEN` but never explains where to get it. Every journey report flagged this as the #1 blocker.

**Current state**: Token is set via Cloudflare dashboard (manual, maintainer-only). No self-service flow.

**Options**:
1. A: Add "Contact maintainer for token" to docs (quick fix)
2. B: Create `/api/token` endpoint with email registration
3. C: Use Glama's hosted endpoint (if #817 works) — no token needed
4. D: Public read-only token (no auth for search/get_lesson)

**Decision**: Pending. Option A is minimum viable.

### UX-2: Search Empty State

**Problem**: When search returns no results, users see `{"results": [], "source": "fallback"}` or `{"error": "No search engine available..."}`. Neither is helpful.

**Fix**: Return a structured message with:
- "No lessons found for your query"
- Suggestion: try broader keywords
- Link to contribute a lesson

### UX-3: Post-Registration Flow

**Problem**: After submitting a registration, users don't know:
- How long to wait
- Whether to refresh
- How to check if registration was accepted
- Where to find their Misaka ID

**Fix**: Add clear next-steps in registration response and docs.

### UX-4: Discovery Path

**Problem**: Some contributors found MisakaNet through issues (bounty), not README. The first-touch experience differs:
- Issue-first: sees bounty → forks → tries to contribute → confused by setup
- README-first: sees product → tries MCP → confused by token

**Fix**: Unify the first-touch experience regardless of entry point.

### UX-5: Workflow 403 / Bot Label

**Problem**: New contributors see:
- `pr-genius: fail` — thinks their PR is rejected
- `Workers Builds: misakanet-web: fail` — thinks they broke something
- `auto-merge: fail` — thinks merge is blocked

These are all non-blocking or expected for first-time contributors, but the labels are misleading.

**Fix**: Add to CONTRIBUTING.md:
- "pr-genius is advisory-only, never blocks merge"
- "Workers Builds failure is a known transient issue"
- "auto-merge requires maintainer approval for first-time contributors"

### UX-6: Error Messages

**Problem**: Error responses like `{"error": "Unauthorized"}` don't tell the user what to do next.

**Fix**: Include actionable guidance:
- 401 → "Get a token from [link] or contact maintainer"
- 405 → "Use POST method for MCP requests"
- 403 → "Origin not allowed. Use an approved MCP client."

## Absorption Status

| Finding | Issue Created | Docs Updated | Lesson Created | Code Fix |
|---------|--------------|--------------|----------------|----------|
| UX-1 | ❌ | ❌ | ❌ | ❌ |
| UX-2 | ❌ | ❌ | ❌ | ❌ |
| UX-3 | ❌ | ❌ | ❌ | ❌ |
| UX-4 | ❌ | ❌ | ❌ | ❌ |
| UX-5 | ❌ | ❌ | ❌ | ❌ |
| UX-6 | ❌ | ❌ | ❌ | ❌ |

## Next Steps

1. Create issues for each finding (or group related ones)
2. Prioritize UX-1 (blocking) and UX-5 (misleading CI)
3. Update docs for quick wins (UX-2, UX-3, UX-5, UX-6)
4. Defer UX-4 to v2.17 (needs product decision)
