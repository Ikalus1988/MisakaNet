---
type: Decision Record
title: Verified Lesson Semantics
status: accepted
date: 2026-07-14
deciders: zsxh1990
---

# Verified Lesson Semantics

## Decision

**Option A: Badge only** — verified = lesson has `## Verification` section. No directory management.

## Rationale

1. **Simplicity**: No directory management, no file moves, no sync issues
2. **Current state**: `lessons/verified/` is empty (only README.md), unused
3. **Contributor-friendly**: Just add a `## Verification` section to mark as verified
4. **Search-aligned**: `_is_verified()` already checks for this section
5. **MCP-compatible**: Verified badge can be derived from content at query time

## Implementation

### Search Engine
- `_is_verified(doc)` checks for `## Verify` or `## Verification` section (existing behavior)
- Verified lessons get `BOOST_VERIFIED` ranking boost (existing behavior)

### lessons.json
- Add `verified: true/false` field derived from content check
- No separate `verified/` directory needed

### MCP Server
- Return `verified: true/false` in search results
- Badge: `[verified]` when `## Verification` section exists

### Contributor Guide
- Add `## Verification` section with reproducible steps
- No file moves or directory changes needed

## Alternatives Considered

### Option B: Directory
- **Rejected**: `lessons/verified/` is empty, adds complexity, requires sync between directory and content

### Option C: Hybrid
- **Rejected**: Too complex for marginal benefit, confuses contributors

## Related

- Issue #352: Decide verified/ semantics
- `_is_verified()` in `misakanet/search/engine.py`
- `BOOST_VERIFIED` in search ranking
