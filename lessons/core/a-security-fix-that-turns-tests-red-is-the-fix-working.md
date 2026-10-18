---
domain: "security"
title: "A security fix that turns tests red is the fix working — rewrite the test that encoded the leak as the contract"
tags: ["security", "regression-testing", "credential-leak", "api-key", "access-log", "test-contract"]
status: "published"
evidence_level: "E1"
summary_plain: "A security fix removed the URL path carrying the API key, but two tests still expected it, so the fix looked like a bug."
trigger: "security fix turns tests red; assert response.status_code == 200 on removed api_key query parameter; test_query_parameter_success; credential in access log"
verify: "Run the auth test file before the rewrite: only the tests naming the removed query-parameter path fail; after the rewrite they assert the refusal and the replacement's new cases pass."
provenance:
  source: "intake #3270 (claude-code), 2026-10-17: a security fix removed a credential-carrying query-parameter path and two tests that asserted it returns 200"
  issue: "#3270"
---

# A security fix that turns tests red is the fix working — rewrite the test that encoded the leak as the contract

## Problem

A security fix deliberately removed a credential-carrying code path: an API key accepted as a
query parameter (`GET /api/memories?api_key=...`). Uvicorn logs the whole request line, query
string included, so the key ended up in the access log — a place nobody audits and rotates. The
fix removed the query-parameter path and left the key in a header, where it is not logged.

The suite immediately went red. Two tests still asserted that the removed path **works**:

```python
assert response.status_code == 200
```

…executed against exactly the request the fix now refuses. Read cold, the diff looked like the
security change had broken authentication — a regression introduced by the fix.

## Root Cause

When a leaky path is also the convenient one — no header plumbing, one call, works pasted into a
browser URL — it accumulates callers *and tests*. Those tests are written from the working
behaviour, not from the security property, so they record the leak as the contract.

That makes them look authoritative after the fix: `main` is green, the branch is red, and the red
assertions sit in the auth file, which reads as "this change broke auth". The tempting resolution
is to make the suite green again by restoring the query-parameter path — which undoes the security
fix while every test passes. The regression ships silently, because the tests that would have
caught it are the ones that were edited to expect it.

In this case the trade-off was named in the test's own comment — *"Useful for quick scripts, though
less secure"* — so the risk was known and had been accepted as the contract instead of flagged as
debt. A comment that documents a security trade-off is a marker to write the refusal test, not a
licence to keep the behaviour.

## Solution

### 1. Rewrite the test to assert the refusal, and put the reason in the docstring

Keep the old test name. A person searching "why did query auth stop working" then finds the
assertion **with** the explanation, instead of turning it back to `200`.

```python
async def test_query_parameter_success(self, client):
    """`api_key` as a query parameter is refused.

    This used to return 200 and is why the key ended up in the access log:
    uvicorn logs the whole request line. The query-parameter name is kept
    in the test title deliberately — a reader looking for "why did query auth
    stop working" finds the answer here.
    """
    assert client.get("/api/memories?api_key=dummy").status_code == 401
```

### 2. Add tests for the replacement in the same change

Removing a capability without a test for what replaced it leaves the suite silent about the new
contract. Cover that the new credential works, and that a single-use ticket cannot be replayed.

### 3. Check which tests your change was *supposed* to break

If exactly the tests naming the removed behaviour fail and everything else passes, that is
evidence the change did what it intended. The failure set is the receipt: a test that only passes
because it asserts the leak is a candidate for this rewrite, not a specification to preserve.

## Verification

- Ran the affected file before the rewrite: exactly the two leak-encoding tests failed; wrong-key,
  bearer-fallback and multi-endpoint auth all passed unchanged. That failure set matched the
  intended change precisely.
- After the rewrite: 29 passed in the auth/ticket area, including new cases proving the replacement
  authenticates and that a second use of a single-use ticket fails.
- Full suite minus an unrelated flake: no new failures attributable to the change.
- Stashed the change to confirm the one remaining suite failure is pre-existing on a clean tree, so
  it is not reported as caused by this work.

## Notes

- The same shape appears whenever a fix removes a convenient path: uploads by filesystem path
  instead of a handle, `?token=` links, debug backdoors. The tests that encode the removed path are
  exactly the ones the fix is expected to break.
- Red tests after a security change are a question, not a verdict. Ask which behaviour is the
  contract — the leak, or its refusal — before editing the assertion.
- Related: `lessons/core/allowlist-must-be-tested-against-the-corpus.md` (a test whose world was
  smaller than the real corpus), `lessons/core/agentcap-registry-secret-safe-validation-failure-metadata.md`.
