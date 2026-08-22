---
{
  "title": "Claude Code can debug low-level cryptography — ML-DSA signature verification failure",
  "domain": "debugging",
  "tags": [
    "claude_code",
    "cryptography",
    "post_quantum",
    "ml_dsa",
    "debugging",
    "go"
  ],
  "language": "en",
  "status": "published",
  "source": "manual",
  "created": "2026-07-29",
  "confidence": "0.90",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## Problem

An ML-DSA (post-quantum signature algorithm) implementation in Go always rejected valid signatures. All test vectors failed with "invalid signature" errors during verification, despite Sign working correctly.

## Root Cause

During earlier refactoring, `HighBits` and `w1Encode` were merged into a single function for the Sign path, then reused in Verify. However, in Verify, `UseHint` already produces the high bits — meaning the combined function effectively takes the high bits of w1 twice during verification.

The bug manifests as a subtle semantic error where the same data flows through different transformations in Sign vs Verify:

```go
// Sign path: w1Encode(highBits(w)) — correct
// Verify path: w1Encode(highBits(UseHint(...))) — double high bits!
```

## Solution

The fix was to refactor `w1Encode` to accept high bits as input and change the type of the high bits:

```go
// Before: w1Encode computes high bits internally
func w1Encode(w []poly) []poly { ... }

// After: w1Encode takes pre-computed high bits
func w1Encode(w1 []poly) []poly { ... }
```

Steps taken:
- Claude Code identified the non-obvious error by analyzing the mathematical flow of the algorithm
- Rather than reverting the merge, the fix refactored `w1Encode` to accept pre-computed high bits
- This eliminated a round-trip through Montgomery representation and made the code clearer
- Claude Code wrote a hypothesis test reimplementing half of verification to confirm before applying the fix

## Verification

- Existing test suite confirmed: `go test crypto/internal/fips140/mldsa` passes
- Claude Code wrote a hypothesis test that reimplemented partial verification to confirm the root cause
- Two other bugs (wrong Montgomery constants, 32-bit vs 32-byte encoding) were also found one-shot by fresh Claude Code sessions with no prior context

## Notes

This demonstrates that LLMs can debug novel cryptographic implementations by reasoning about mathematical invariants, not just pattern matching. The key insight was that the same function behaved differently depending on its call context (Sign vs Verify), which a pure code-review approach might miss. Fresh sessions with no context can still find these bugs by analyzing the algorithm's mathematical structure.

## References

https://words.filippo.io/claude-debugging/
