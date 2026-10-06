---
domain: "testing"
title: "Three checks that were green and covered nothing: the subject was outside the scope"
tags:
  - "false-green"
  - "mocks"
  - "test-coverage"
  - "gates"
  - "dependency-pinning"
  - "release-automation"
status: "published"
evidence_level: "E1"
created: "2026-10-06"
updated: "2026-10-06"
source: "maintainer session, 2026-10-06 (three instances while landing PRs #2926, #2929, #2931)"
summary_plain: "A check can be green, running, and asserting real things, and still cover nothing — when its subject was never in scope."
trigger: "test passes but never runs in CI / mocked boundary hides a defect / the file that drifted was not in the list / dep missing so importorskip always skips"
verify: "For each check, name the artifact it covers, then prove it is reachable: the file is in the list, the function is reached, the dependency is installed. Break the artifact and confirm it reds."
provenance:
  evidence: "self-observed"
  note: "Three instances in one session, each found by asking what the check was actually pointed at rather than by reading the test; artifacts: tests/test_integrations.py, tests/test_version_consistency.py, tests/test_default_endpoints_reachable.py, release-please-config.json"
---

# Three checks that were green and covered nothing: the subject was outside the scope

## Problem

`lessons/contrib/assertion-that-cannot-fail.md` covers assertions that pass whatever the
code does — a check that is structurally incapable of failing. This is the neighbouring
failure and it is harder to see, because each of these three checks *asserts real things,
about real data, and passes honestly*.

The defect is one level up: **the thing being checked was never inside the check's scope.**
A green result was produced, and it meant nothing, and nothing in the run said so.

## Three instances, one session

### 1. The mock invented the field the code was wrong about

`integrations/langchain/misakanet_tool.py` and `integrations/llamaindex/misakanet_tool.py`
each formatted every result as:

```python
lesson_type = result.get("type", "unknown")
lines.append(f"{i}. [{lesson_type}] {title} (relevance: {score:.2f})")
```

`type` is not a lesson field. Measured 2026-10-06 on production, three queries, nine
results: `type` absent from all of them, and absent from all 467 entries in
`data/lessons.json`. The `.get()` fallback therefore fired on **every result, every
time**, and every line the tool ever printed read `[unknown]`. The field that does exist
on every lesson is `domain`.

`tests/test_integrations.py` did not catch it, and would not have:

```python
# the payload it invented
{"results": [{"title": "Test Lesson", "type": "error", "score": 0.95, "problem": "..."}]}

# the only assertions
assert "Found 1 relevant lessons" in result
assert "Test Lesson" in result
```

The mock declared a `type` field, so the invented field satisfied the invented read. And
the assertions never looked at what was rendered *around* the title — a title substring
survives any formatting bug whatsoever.

Worse, the whole langchain half of that file was dead in CI:

```python
@pytest.fixture(autouse=True)
def skip_if_no_langchain(self):
    pytest.importorskip("langchain")
```

No CI job installs langchain. Locally, `pip install` is refused under PEP 668. So those
three tests had never executed anywhere in this project, and the mock's invented shape
had never been compared against anything.

### 2. The file that drifted was not in the list

`package-lock.json` had been drifting from the release line for several versions — 2.41.1
while `package.json`, `.release-please-manifest.json` and eleven other files said 2.42.1.

The cause was in the config: `extra-files` named `package.json` and eleven others, and
npm v7+ writes the lockfile version **twice** — at `$.version` and at
`$.packages[""].version` — so it needed two entries and had none.

The gate that should have caught it could not have, for two separate reasons:

```python
# (a) the drifting file was simply absent from the list
JSON_PINNED_VERSION_FILES = {
    "package.json": "$.version",
    ".codex-plugin/plugin.json": "$.version",
    ".claude-plugin/plugin.json": "$.version",
}   # package-lock.json is not here

# (b) even had it been listed, one path could hold only one jsonpath
declared = {entry["path"]: entry.get("jsonpath") for entry in extra if isinstance(entry, dict)}
```

So declaring `$.packages[""]` and forgetting `$.version` would have passed — and the gate
would then have reported on a field the release was never going to write. The single
drifting file was the one file missing from the list, and the list's shape meant that
even a correct entry could not have been expressed.

### 3. A dead host, behind a mocked boundary

`integrations/*` defaulted to `https://misakanet.dev/api/search`. That domain has no DNS
record, and `/api/search` answers 404 on the real host — the path was wrong
independently of the hostname, so fixing only the host would have swapped a DNS failure
for an HTTP failure and left the tool equally broken.

The same test file mocked `urllib.request.urlopen`, so the constant was never resolved and
never dialled. That mock was legitimate; what made it harmful was that **nothing else in
the test touched the address**, so a value that could not exist was asserted about for
months while the suite stayed green.

## Root Cause

Three mechanisms, one structure: the check and its subject are connected by an assumption
that nobody wrote down and nobody tested.

```
check ──[ assumption ]──> subject
```

In (1) the assumption was *the API returns the fields the code reads*, held up by a mock
that encoded the assumption itself. In (2) it was *the file under test is in the list*,
and the list was maintained by hand. In (3) it was *the default is a reachable address*,
and the boundary was mocked.

What all three share is that **green was the expected output**. A check that can only
confirm what you already believe will confirm it indefinitely, and its passing is
evidence of nothing. The tell is not in the test file — it is in the question "what
artifact is this check pointed at, and how do I know that pointer is live?"

## Solution

For each check, name the artifact and then prove the pointer reaches it.

**Prove the subject is reachable, not merely that the check passes.**

1. **Enumerate what the check claims to cover, and assert the enumeration is complete.**
   A hand-maintained list needs a test that the list still contains what drifted. The
   fix for (2) was not only adding `package-lock.json` — it was making
   `JSON_PINNED_VERSION_FILES` carry a tuple per path and checking every element, because
   the single-slot map could not represent the truth.

2. **Assert the rendered output, not a substring of it.** `assert "Test Lesson" in result`
   survives every formatting bug. `assert "[devops]" in result` and
   `assert "[unknown]" not in result` do not. The second is the one that bites: it fails
   on the fallback firing, which is the actual defect.

3. **Make the mock the shape of the truth, and let the gate watch the mock.** Real captured
   response, real field names, real value ranges (`score` is 0–12, not 0–1). Then add a
   check that the mock does not reintroduce a field the corpus does not carry — otherwise
   the next person "fixes" the mock back to the convenient shape.

4. **Check that the check runs.** A test that skips everywhere is not a weak test, it is
   no test. `importorskip` against a package no CI job installs is a silent deletion.
   The durable answer for code that cannot be imported in CI is a **source-level** check:
   the new assertions read the file as text, so they need no dependency and no mock, and
   they run everywhere.

5. **Assert the address, not the call.** Mocking the network is fine. Mocking the network
   *and* asserting nothing about what was dialled turns the test into a certificate for a
   fiction. The fix was a separate gate that reads the endpoint constant and compares its
   host against the host the shipped client actually uses.

## Verification

Every one of the three was fixed with a gate that was proven to catch the original, by
mutation, before being called done:

| Defect | Mutation | Gate result |
|---|---|---|
| formatter reads `type` | revert to `result.get("type", …)` | red, naming file and line |
| mock invents `type` | put `"type": "error"` back | red, naming the mock |
| lock not bumped | drop one of the two extra-files entries | red |
| lock drifted | revert `$.version` only | red, naming `$.version` specifically |
| deadlock host | point the default back at `misakanet.dev` | red, printing the mismatch |
| dead workflow | — | 100 of 100 runs `skipped`, which is how it was found |

The last row is the cheapest check in this whole family and it caught a workflow that had
**never once succeeded**: `gh run list --workflow=… --json conclusion | group_by(.)`
returned `{"skipped": 100}` and nothing else. If a check's only observed outcome across
its entire history is "skipped", it is not reporting.

A full-suite run after all three fixes: `3389 passed, 25 skipped, 0 failed`, with the
delta from the prior baseline being exactly the two newly added gate tests.

## Notes for the next occurrence

- When a check is green, ask **what it was pointed at** before asking whether it is
  right. The first question has an answer you can check; the second usually does not.
- A mock that contains a field the real system does not have is not a harmless
  convenience. It is a claim about the system, written where nobody reviews claims.
- `importorskip` against a dependency nothing installs is a test that has been deleted
  while remaining visible in the count.
- Before treating a field as real, find the code that produces it. This session nearly
  filed the opposite error: `data/lessons.json` was taken as the authority on which
  fields exist, and `score` and `problem` were flagged as dead reads. `workers/register-proxy-sw.js`
  says otherwise in the source — `problem` is filled from the D1 column first precisely
  because the GitHub snapshot only carries `description`/`summary`, and `score` is
  omitted on purpose when the `searchLessons` fallback does not rank, because a
  `score: 0` reads as "ranked, and the ranking is zero". The index and the API response
  are different shapes, and neither one alone is the specification.
