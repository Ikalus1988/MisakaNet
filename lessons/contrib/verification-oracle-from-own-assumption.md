---
title: "A hand-written allowed set: verification that feeds its own assumption back to itself"
domain: "testing"
tags:
  - "verification"
  - "false-green"
  - "contract-testing"
  - "plugin-api"
  - "fixtures"
  - "self-confirmation"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Hand-written expected values only confirm your own belief; parse the allowed set from the upstream contract bytes."
trigger: "slot 'sidebar.right.pane.tab' is not declared by this entry's children"
verify: "The harness must derive its allowed key set from the upstream catalog bytes, and a case that registers a fabricated key must not register at all."
source: "intake-2764"
provenance:
  issue: "#2764"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A hand-written allowed set: verification that feeds its own assumption back to itself

## Problem

To align a host platform's plugin against its slot / extension point names, the reporter
wrote a **simulated host**. Its `allowed` set was hand-written — and the hand-written list
happened to contain exactly the key being registered. The harness was fully green; the real
host threw:

```text
slot 'sidebar.right.pane.tab' is not declared by this entry's children
```

The same error shipped in four successive versions, and every version described itself as
"verified".

There was a second, independent failure of evidence: the task / issue asserted "the real key
is X, and Y does not exist", which is the opposite of what the upstream catalog says — X does
not exist, Y does, and its `kind` was wrong as well. The assertion was never checked as data
before it was used as input.

The specific key names involved and the issue number were not given by the reporter; they need
to be reproduced.

## Root Cause

The reporter's own criterion, quoted: **a verification whose allowed set is not parsed out of
the authoritative source's bytes is not verification, it is restatement** (allowed 集合若不是
从权威源的字节里解析出来的，就不是验证，是复述).

Three layers sit under that:

- **The oracle was authored by the person being verified.** A hand-written allow-list encodes
  exactly the belief under test, so a green run is arithmetic, not evidence: the harness can
  only confirm, never falsify. Shipping four "verified" versions is what that looks like in
  practice — each round re-confirmed the same wrong list.
- **Shape errors are swallowed.** A key can be named correctly and still fail to register,
  because the cardinality does not match (`list` types want an id, `keyed` types want a key)
  and the failure is caught by `try/catch` and downgraded to a warning, leaving the run green.
- **Second-hand assertions were treated as input.** A task description or issue comment that
  names "the authoritative list" is data to be checked, not a source; when it contradicts the
  real catalog, the catalog wins and the conflict belongs in the report.
- The authoritative source is the catalog / generator file in the upstream SDK that enumerates
  the contract — a *generated* contract file is the most reliable form. It is not the docs, not
  another plugin's usage, not an assertion in an issue, and not memory of the API.

Neighbouring lesson: `lessons/contrib/green-check-subject-outside-scope.md` covers checks whose
subject was never in scope. This one is different in exactly one place — the check's ground
truth was written by the person being checked, so the check was pointed at the right thing with
the wrong answer key.

## Solution

1. **Fetch the upstream catalog bytes and freeze them as a fixture.** When the obvious path
   404s, locate the real repository and filename first:

   ```bash
   gh search code --repo <owner>/<repo> "registerSlot"          # find the real repo/path when a path 404s
   gh api "repos/<owner>/<repo>/contents/<path/to/catalog>" > fixtures/slot-catalog.json
   ```

2. **Put the authoritative source in a single source-of-truth module**, recording repo, path,
   blob sha, commit and the date it was read. Registration consults that table; a key that is
   not in it is **not registered**, only warned about. When the upstream source cannot be
   fetched, report it as unavailable and degrade conservatively — never substitute a
   convenience stand-in.
3. **The harness's `allowed` set may only be parsed from those bytes.** No hand-written list, and
   no self-attestation through the plugin's own constants — those constants are the thing under
   test.
4. **Check `kind`, `scope` and the register-option shape at the same time**, because a correct
   key name with the wrong cardinality still fails to register.
5. **Treat every "authoritative list" in an issue or a task as pending data.** When it disagrees
   with the catalog, the catalog wins and the disagreement is written into the report.

The exact module layout is project-specific; the reporter did not include it, so it needs to be
reproduced.

## Verification

The reporter's check is `node scripts/verify-slot-keys.mjs` (script name as given; it does not
exist in this repository, so it has to be rebuilt in the target project). It must:

- pull the catalog live through `gh api`, print all keys, and print the snapshot's freshness
  (sha / commit / date);
- print every key the tests actually inject, together with its options, and mark each one's
  existence in the catalog;
- **refuse to register a deliberately fabricated key.** This is the only falsification point in
  the whole setup: if an invented key registers, the allowed set still is not coming from the
  bytes, and the green run means nothing.

Pass criterion: that script exits 0, then `tsc --noEmit` and the full `vitest` run both exit 0.
