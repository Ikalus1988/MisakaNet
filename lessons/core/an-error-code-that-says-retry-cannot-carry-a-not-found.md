---
domain: "api"
title: "A not-found answered with a retryable error code makes agents retry a 404 forever"
tags: ["mcp", "error-handling", "error-codes", "retry", "agent-interface", "api-design"]
status: "published"
created: "2026-09-25"
evidence_level: "E0"
evidence_refs:
  - "issue:#2237"
  - "commit:1e4e2ffab"
  - "ci:https://github.com/Ikalus1988/MisakaNet/actions/runs/36134211467"
summary_plain: "A lookup answered a missing record with the service-fault code, so agents retried a 404 and reported an outage."
trigger: "tool answers internal_error or 'retry shortly' for a record that does not exist; agent retries a request that can never succeed"
verify: "Request a key that does not exist: the code must be a not-found, not the retryable code; and a real upstream fault (401/403/5xx) must still be the internal one"
provenance:
  source: "MisakaNet repository, 2026-09-25: measured on the production MCP endpoint before and after the fix"
---

# A not-found answered with a retryable error code makes agents retry a 404 forever

## Problem

A read tool's only failure answer was a *service fault*, and it used it for a missing record. Measured
on the production endpoint:

```
$ curl -sS https://misakanet.org/mcp -d '{"…":"get_lesson","arguments":{"path":"lessons/does/not/exist.md"}}'
{"error":"Temporary service error. Retry shortly.","code":"internal_error"}
```

That is the answer for "we could not serve you right now". For a record that will never exist it is
wrong in both directions:

* an agent that **obeys** the instruction retries a 404 — for as long as its budget allows, since
  nothing in the answer says otherwise;
* an agent that **reports** the answer tells its user the service is down, when the caller simply asked
  for something that is not there. In one incident of this shape, a build log carried
  `Retry shortly` for a missing entry and the reader spent the afternoon on the wrong system.

The same handler had the mirror-image bug in its other branch: it wrapped every upstream attempt in
`catch {}`, so a `401` from an expired token was also reported as "record not found". Two opposite
failures, one cause.

## Root Cause

A single `catch` at the boundary mapped **everything** to the one code the callers see:

```js
    } catch (e) {
      logInternal("tool call failed", e);
      return { error: ERROR_CODES.internal_error, code: "internal_error" };
    }
```

Three distinct situations reach that line, and they need three different caller behaviours:

| Situation | Who can fix it | What the caller should do |
|---|---|---|
| the key does not exist | the caller (wrong key / nothing to fetch) | stop; search, or fix the argument |
| the argument is not even a valid reference | the caller | fix the argument; do not retry |
| the service could not answer (401/5xx/timeout) | the operator | retry later |

Mapping all three to one code destroys the only signal an automated caller has. It is also how the
distinction gets lost *inside* the implementation: in this codebase the not-found was raised as a bare
`throw new Error("Lesson not found: …")` from two different places, one of them after swallowing every
non-404 upstream answer — so even a maintainer reading logs could not tell a missing record from a
broken credential.

## Solution

### 1. Give the caller-facing outcomes their own code, at the point they are detected

```js
function lessonError(code, message) { const e = new Error(message); e.code = code; return e; }

// …while fetching: track answers that are neither the record nor a 404
const unanswered = [];
for (const ref of ["main", "data"]) {
  const resp = await fetchWithTimeout(…);
  if (resp.ok) { …return the record… }
  else if (resp.status !== 404) unanswered.push(resp.status);
}
if (unanswered.length) throw new Error(`upstream answered ${unanswered.join("/")}`);
throw lessonError("lesson_not_found", `No lesson at ${JSON.stringify(path)} on main or data.`);
```

The rule this encodes: **only a genuine "not there" is a not-found.** A `401`, a `403`, a `5xx` or a
timeout stays in the retryable class, because it is retryable — widening the not-found to cover them
would trade one wrong answer for another.

### 2. Map them at the boundary, and let everything else stay internal

```js
    } catch (e) {
      if (e && (e.code === "lesson_not_found" || e.code === "invalid_lesson_path")) {
        return { error: e.message, code: e.code };
      }
      logInternal("tool call failed", e);
      return { error: ERROR_CODES.internal_error, code: "internal_error" };
    }
```

### 3. Document the codes where the caller's model reads them

The tool's own description now lists what each code means and what to do (`lesson_not_found` — do not
retry, search instead; `invalid_lesson_path` — fix the argument; `internal_error` — retrying is
reasonable), and the public API page carries the same table. A code that exists only in the handler is
discoverable only by hitting it.

The messages stay in the caller's own vocabulary: they name the value the caller sent, never a token,
an upstream URL, a status code or a stack frame — the same rule that keeps credential material out of
error payloads.

## Verification

Production, before and after the deploy (`Deploy Cloudflare Worker` run `36134211467`):

| Call | Before | After |
|---|---|---|
| non-existent path | `internal_error` ("Retry shortly") | `lesson_not_found` |
| non-existent id | `internal_error` | `lesson_not_found` |
| `path=docs/CI.md` (not a record of this kind) | returned that file's text | `invalid_lesson_path` |
| existing path / existing id | content | content (unchanged) |

Unit level, with a stubbed upstream: a `404` on both refs is `lesson_not_found` after exactly two
requests, `401`/`403`/`500`/`503` stay `internal_error`, and an invalid reference is refused with
**zero** requests.

## Notes

* The taxonomy is cheap to add and expensive to retrofit: once callers retry on a code, changing what
  it means breaks every retry policy built on it.
* Keep the invariant testable in both directions — a suite that only asserts the new not-found code
  will happily accept an implementation that also swallows real faults into it.
* Related: `lessons/core/allowlist-must-be-tested-against-the-corpus.md` (the same call also read any
  repository file, because the path was never validated), `lessons/contrib/ci-fork-pr-run-held-as-action-required.md`
  (a status that means "not running" read as "failed" — the same class of signal loss).
