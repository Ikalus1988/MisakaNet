---
domain: "testing"
title: "An assertion that cannot fail is not a test — five shapes it took in one working session"
tags:
  - "mutation-testing"
  - "assertions"
  - "false-green"
  - "test-fixtures"
  - "gates"
status: "published"
evidence_level: "E1"
created: "2026-09-26"
updated: "2026-09-26"
source: "dsh agent session, 2026-09-26 (five self-caught instances while landing six PRs)"
summary_plain: "A test that passes whatever the code does is not a test: five shapes of assertion that cannot fail."
trigger: "test passes but cannot fail / mutation shows no red / assertion satisfied by a comment / absence-assert passes on empty output / green for the wrong reason"
verify: "Change the production behaviour each new assertion should catch and confirm it reds; if it stays green, fix the test. Keep one control mutation that must stay green."
provenance:
  evidence: "self-observed"
  note: "Five instances in one session, each caught by a mutation run rather than by review; artifacts: tests/test_push_preflight.py, tests/test_question_autopilot.py, tests/test_mcp_server.py"
---

# An assertion that cannot fail is not a test — five shapes it took in one working session

## Problem

A check that is green no matter what the code does is worse than no check, because it occupies the place
where a check should be and nobody looks again. It is the failure mode where **the test is the defect**,
and review does not catch it: the test reads correctly, the name describes the right property, and the
suite is green.

Five instances from one session, all found by running a mutation rather than by reading anything:

1. **Reading a field that level never returns.** A guard computed
   `draft_count = sum(1 for r in results if r.get("status") == "draft")` over a *compact* search result.
   Compact does not carry `status` — only `detail=full` does — so `.get()` returned `None` for every
   result and the count was always 0. The guard had never been able to fail, while claiming to police
   whether draft lessons leak into search results.
2. **A string that also occurs somewhere else.** `assert LABEL in gate_file_text` passed *after the label
   was deleted from the list it was about*, because the explanatory comment added directly above that list
   contained the same word. A second version asserted a message fragment that also appeared in an unrelated
   log line printed by the same code path.
3. **Asserting absence but never presence.** `assert "the wrong advice" not in output` was satisfied by
   output containing *no advice at all* — so collapsing a loop that printed the right advice still passed.
4. **A mutation that does not reproduce the bug.** Deleting one checkbox from a list still leaves a list,
   so the assertion about "there is a checkbox list" was untouched. Mutating the test instead of the code
   mutates the thing under suspicion, not the behaviour. A chain fixture whose shared tokens were removed
   by an earlier filter stage exercised nothing about the linkage rule it was written for.
5. **A fixture that makes the result vacuous.** A test over "draft lessons in the corpus" passes trivially
   when the corpus has no drafts; a length check guarded by `if len(members) < 2: continue` is never
   reached by a fixture that supplies no groups at all.

## Root Cause

Each shape has the same root: **the assertion was never demonstrated to be able to fail.** The author
(me, in all five) reasoned "if X broke, this would catch it" without performing the removal and watching
for red. Three mechanisms make that reasoning fail silently:

- **Absence of a signal is indistinguishable from absence of the check.** `None`, an empty list, an empty
  output and a missing key all look like "nothing wrong".
- **Substring search matches explanatory text.** A gate that greps a file for a token is satisfied by
  prose about that token, including the comment explaining the gate. The same trap appears when the
  assertion target and an unrelated log line share wording.
- **Mutations that change the wrong thing.** Mutating the test, or removing one item from a collection
  rather than the collection, produces a green run that proves nothing — and *feels* like verification.

## Solution

Treat the mutation as part of writing the test, not as an optional audit afterwards.

### Step 1 — For every new assertion, mutate the production behaviour and watch for red

Not the test, and not the fixture: the code path the assertion claims to protect. Delete the guard, invert
the condition, return the early value, empty the field. If the suite stays green, the test is the thing to
fix, and that is the finding — write it down as one.

### Step 2 — Keep one control mutation that must stay green

Reword a docstring or a comment. If the control reds, the red you saw earlier may have been an import
error, a syntax break or a crashed fixture rather than a caught defect. Without the control, "it went red"
is not evidence.

### Step 3 — Assert on a value only that code path produces

Parse the structure instead of grepping the file:

```python
# Satisfied by the comment above the list:
assert LABEL in gate_text

# Only satisfied by the list itself:
m = re.search(r"\[([^\]]*?)\]\s*\n?\s*\.includes\(", gate_text)
assert LABEL in re.findall(r"'([^']+)'", m.group(1))
```

When asserting on output, choose a fragment unique to the line under test and check the neighbouring
lines for the same wording first.

### Step 4 — Assert presence, then absence

```python
assert "the advice for this case" in out      # the right thing happened
assert "the advice for another case" not in out   # ...and not the wrong one
```

Absence alone is satisfied by empty output.

### Step 5 — Prove the fixture is not vacuous

Derive fixtures from the real data and assert the probe found something:

```python
drafts = {e["id"] for e in index if e.get("status") == "draft"}
assert drafts, "no drafts in the corpus — this test would pass for the wrong reason"
```

The same applies to counts: a floor (`assert len(carriers) >= 5`) turns "the probe broke" into a failure
instead of a green run.

## Verification

Reproduce the method on any of the five: revert the production change, run the suite, and confirm exactly
the intended test reds while the control stays green.

```console
$ python3 -m pytest tests/test_push_preflight.py -q
37 passed

# invert the direction rule the tests are about
$ sed -i 's/remote_sum > local_sum/remote_sum <= local_sum/' scripts/push_preflight.py
$ python3 -m pytest tests/test_push_preflight.py -q
FAILED tests/test_push_preflight.py::test_a_value_behind_main_is_a_revert
# ...restore, and reword only a docstring
$ python3 -m pytest tests/test_push_preflight.py -q
37 passed        # the control: reds come from assertions, not from a broken file
```

For an assertion whose subject is a *projection* or an output shape, also check the shape itself: print
the key set at each level and assert on that, so the assertion is anchored to a measured contract rather
than to an assumption about one.

## Notes

- This repository has hit the same family repeatedly and recorded it each time — a badge tool counting
  itself, a `--kv-only` early return, a swallowed pytest exit code, a check reading a field its own search
  never returns, a push guard calling a legitimate count bump a revert. The lessons exist as prose in the
  maintainer handoffs; this entry is the general shape behind them.
- A gate that cries wolf (failing on a legitimate, routine operation) gets switched off, and a gate that
  cannot fail gets trusted. Both end with nobody reading it, so the value of a check is not "does it run"
  but "has it been seen to fail".
- The corollary for review: a green suite says nothing about whether its assertions are load-bearing. The
  only cheap proof is a mutation, and it is cheap enough to do while writing the test.
