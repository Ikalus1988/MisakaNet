---
title: "A fixture dated six days ago is a test that reddens main on its own"
domain: "testing"
tags:
  - "test-fixtures"
  - "time-bomb"
  - "flaky"
  - "ci"
status: "published"
evidence_level: "E1"
created: "2026-11-17"
updated: "2026-11-17"
source: "maintainer"
summary_plain: "A fixture with an absolute date left the required audit check red on main for every pull request."
trigger: "test passes then fails with no code change fixture absolute date default week window expires audit red on main"
verify: "Rewrite the fixture as now-minus-n-days, run the suite today, then run it with the clock moved forward a week: the result must not change."
provenance:
  issue: "#5140"
  source: "found when a pull request's audit leg failed on a test its diff did not touch"
---

# A fixture dated six days ago is a test that reddens main on its own

## Problem

Pull request #5139 failed its required `audit` check on a test the diff never touched:

```
not ok 137 - rows are scored by the ladder module and ranked
  Expected values to be strictly equal: 1 !== 2
  location: workers/contribution-ladder-endpoint.test.mjs:58
```

`audit` is required, so from that moment **every** pull request in the repository was red, and no
commit had done anything wrong. The same test passes on the machine where it was written six days
earlier.

## Root Cause

The fixture handed the endpoint rows with literal timestamps, and asked for the default window:

```js
const { env } = envWith([
  { node_id: 'MisakaA', kind: 'lesson',   n: 3, last: '2026-11-11T00:00:00Z' },
  { node_id: 'MisakaA', kind: 'question', n: 2, last: '2026-11-11T00:00:00Z' },
  { node_id: 'MisakaB', kind: 'lesson',   n: 1, last: '2026-11-10T00:00:00Z' },
]);
const { body } = await ladder(env);
assert.equal(body.total, 2);
```

`ladder` cuts by `week` unless told otherwise. On 2026-11-11 both nodes had rows inside seven days and
`total` was 2. On 2026-11-17 neither did, the endpoint returned no rows for one node, and `total`
became 1 — the assertion is about **the wall clock**, not about the code under test.

The property the test needs is "a row inside the window". It wrote down "the date someone wrote the
fixture" instead, and those are the same thing only on the day of authorship.

## Solution

Make the fixture relative to now:

```js
const recent = (daysAgo) => new Date(Date.now() - daysAgo * 86400000).toISOString();
```

and use `recent(1)` / `recent(2)` where the literals were. A test that pins a *window* has to move with
the window; a date is a snapshot of the author's afternoon.

The dated observation in a neighbouring comment (`observed on the live board 2026-11-14`) stays — it
records when something was seen, which is history, not a fixture.

## Verification

Two runs, and the second one is the point:

1. today: `node --test workers/contribution-ladder-endpoint.test.mjs` → 12 pass, 0 fail;
2. with the clock moved forward a week (`faketime`, or a stubbed `Date.now`) → still 12 pass.

A relative fixture cannot be re-verified by waiting, so the second run is the only honest check.

## The generalisation

Any test whose fixture carries an absolute timestamp and whose subject filters, sorts, expires or
windows by time is a **scheduled failure**. It is worse than a flaky test, because it is deterministic
and permanent once it trips: the red never clears, and it lands on whoever runs CI next rather than on
whoever wrote it.

Two cheap habits retire the whole class:

- fixtures express *relations* ("one day ago", "inside the window", "before the epoch I set"), never
  calendar dates;
- a test that needs "now" takes it as an argument or stubs it, so the test body never depends on when it
  runs.

`grep -rn "20[0-9][0-9]-[01][0-9]-[0-3][0-9]T" tests/ workers/*.test.mjs` is the inventory: a timestamp
in a fixture is a date on a fuse.
