# Journey Report Absorption Tracker

> Status: active · Source: [#855](https://github.com/Ikalus1988/MisakaNet/issues/855)
> Derived from: #830 → #850, #836, #834, #833, #847, #851

## Summary

6 journey reports from [#830](https://github.com/Ikalus1988/MisakaNet/issues/830) revealed consistent UX friction across the Remote MCP on-ramp. This document tracks absorption of those findings into docs, code, and new issues.

---

## Findings & Absorption Status

| # | Finding | Severity | Source | Status |
|---|---------|----------|--------|--------|
| 1 | Token acquisition undocumented | **Blocking** | [2026-08-06-remote-mcp.md](../journey-reports/2026-08-06-remote-mcp.md) | ✅ Absorbed → `docs/integrations/mcp-remote.md` § Getting a Token |
| 2 | Search empty state confusing | Medium | Multiple reports | ✅ Already resolved — `_smart_fallback()` in `search_knowledge.py` provides closest matches, "Did you mean", domain hints, and contribution links |
| 3 | Post-registration wait/refresh unclear | Medium | Onboarding reports | ✅ Absorbed → `docs/registration-channels.md` § After Registration |
| 4 | Workflow 403 / bot labels misleading | Medium | `docs/maintainer/pr-genius-observation.md` | ✅ Absorbed → `CONTRIBUTING.md` § Understanding CI Bot Activity |
| 5 | README vs issue body discovery path | Low | Multiple reports | ⏳ Deferred to v2.17 |
| 6 | Error messages don't guide to fix (401/403/405) | Low | [2026-08-06-remote-mcp.md](../journey-reports/2026-08-06-remote-mcp.md) | ✅ Absorbed → `docs/troubleshooting.md` § MCP Remote Errors, `docs/integrations/mcp-remote.md` troubleshooting table |

---

## UX-1: Token Acquisition Documentation ✅

**Problem:** `docs/integrations/mcp-remote.md` said `Bearer YOUR_TOKEN` but never explained where to get a token. Every journey reporter flagged this as the #1 blocker.

**Fix:** Added "Getting a Token" section to `docs/integrations/mcp-remote.md`:
- Token source: Glama → Connect → Get API Token
- Self-service: POST `https://misakanet.org/mcp/token` (when available)
- Fallback: Use local stdio MCP (no token needed)

**Files changed:** `docs/integrations/mcp-remote.md`

---

## UX-2: Search Empty State ✅

**Problem:** No results or errors gave no guidance.

**Status:** Already resolved before this absorption cycle. The `_smart_fallback()` function in `search_knowledge.py` provides:
1. Top-3 closest matches by keyword overlap
2. "Did you mean" with relaxed query
3. Domain filter suggestions
4. Broad mode hint (`--broad`)
5. Contribution link for missing lessons
6. Available domain list

No additional code changes needed. The existing FAQ in `docs/troubleshooting.md` § "Search returns nothing" covers the CLI side.

---

## UX-3: Post-Registration Next Steps ✅

**Problem:** After registering a node, users didn't know how long to wait or how to check status.

**Fix:** Added "After Registration" section to `docs/registration-channels.md`:
- Per-channel wait times (Issue ~30s, Email ~3s, Web ~1s)
- How to verify registration (check node profile)
- What happens next (join competitions, submit lessons)

**Files changed:** `docs/registration-channels.md`

---

## UX-4: First-Touch Experience Unification ⏳

**Problem:** README and issue body present different entry points. README emphasizes MCP installation, while issue templates encourage lesson contribution. Newcomers see inconsistent first-touch experience.

**Status:** Deferred to v2.17. Requires cross-surface alignment (README, issue templates, mcp-quickstart, CONTRIBUTING). This is a product-design decision, not a docs-only fix.

**Open issue:** TBD (to be filed by maintainer for v2.17 planning)

---

## UX-5: CI Bot Behavior Documentation ✅

**Problem:** Workflow 403 errors, "pr-genius fail" comments, and auto-merge failures made new contributors think their PR was rejected.

**Fix:** Added "Understanding CI Bot Activity" section to `CONTRIBUTING.md`:
- PR Genius: advisory-only, never blocks merge (see `docs/maintainer/pr-genius-observation.md`)
- Auto-merge: docs-only PRs merge automatically after passing CI
- Workflow 403: usually a token/permission issue, not a rejection
- Bot comments: informational, not negative feedback

**Files changed:** `CONTRIBUTING.md`

---

## UX-6: Actionable Error Guidance ✅

**Problem:** 401/403/405 responses for Remote MCP lacked actionable guidance.

**Fix:** Enhanced `docs/integrations/mcp-remote.md` troubleshooting table and `docs/troubleshooting.md`:
- 401 → "Missing or invalid token. Get a token from Glama or use local stdio."
- 403 → "Invalid origin or missing permissions. Use Claude/Cursor/Glama, or remove Origin header."
- 405 → "Use POST, not GET. MCP Streamable HTTP requires POST."
- Each error now links to the relevant setup section

**Files changed:** `docs/integrations/mcp-remote.md`, `docs/troubleshooting.md`

---

## Verification

- [x] All 6 findings addressed (5 ✅ absorbed, 1 ⏳ deferred)
- [x] Tracker file created at `docs/maintainer/journey-report-absorption.md`
- [x] No code changes required — all fixes are documentation updates
- [x] Cross-references between docs are consistent

## Related

- Tracker issue: [#855](https://github.com/Ikalus1988/MisakaNet/issues/855)
- Source: [#830](https://github.com/Ikalus1988/MisakaNet/issues/830) Journey report collection
- Journey reports: [#850](https://github.com/Ikalus1988/MisakaNet/pull/850), [#836](https://github.com/Ikalus1988/MisakaNet/pull/836), [#834](https://github.com/Ikalus1988/MisakaNet/pull/834), [#833](https://github.com/Ikalus1988/MisakaNet/pull/833), [#847](https://github.com/Ikalus1988/MisakaNet/pull/847), [#851](https://github.com/Ikalus1988/MisakaNet/pull/851)
