---
domain: "testing"
title: "a pytest -k mask deselects more tests than you meant, and hides that it did"
tags: [pytest, test-selection, deselect, skip, ci, masking, collect-only]
status: "published"
evidence_level: "E2"
summary_plain: "A pytest -k mask strips tests by name substring, so it silently drops tests you meant to keep and still shows green."
trigger: "pytest -k deselected more tests than expected; test mask hid passing tests; -k green while skipping tests; collected fewer tests without failure"
verify: "python3 -m pytest --collect-only -q -k \"not test_score_merge\" on a file with test_score_merge and test_score_merge_by_id reports 2 deselected, not 1."
provenance:
  issue: "#3405"
  source: "MCP intake (claude-code), contributor-reported"
---

# a pytest -k mask deselects more tests than you meant, and hides that it did

## Problem

CI skipped the tests that "cannot run locally" with a selection expression like:

```bash
pytest -k "not A and not B and not C and not D"
```

The intent was to exclude **four** tests. `pytest --collect-only` measured the expression actually
**deselecting 11** — seven more than intended. Those seven were not broken or environment-dependent
at all: each already called `pytest.skip` itself. Separately, one of the four the mask was
*supposed* to remove always passed. So the suite reported green while silently switching off tests
that were either healthy or already handling their own precondition. The change that looked like
"exclude the four I can't run here" was actually "exclude a set nobody had ever listed".

The damage is not the four tests you knowingly dropped — it is the seven that were already
skipping themselves and the one that was passing. Those tests were still *being maintained as
tests*: they would have caught a regression the moment someone fixed the environment. Under the
mask they never ran, and nothing in the output said so.

## Root Cause

**`-k` matches a substring against the test's name, not "the test you were thinking of".** A
node id is file path + class + function, and `-k` runs a boolean over that string. So:

- `not test_score_merge` also deselects `test_score_merge_by_id`, `test_score_merge_v2` — every
  test whose name *contains* the fragment;
- it takes down an entire class: `not TestScoreMerge` removes **all** methods under
  `TestScoreMerge`;
- tests with the same name in several files are collected together and all go.

pytest is right that a deselected test is not a failure — deselection is a *selection* decision,
so the exit code is still `0`. That is exactly why the gap between "4 I meant" and "11 it took"
survives: **the only artifact that would have shown the set is the collection report, and the
mask removed those lines from it too.** A green suite and a correct suite look identical.

The tempting shortcut is also the wrong tool. An environment-missing test is not "a test I don't
want to run" — it is a test that *did not run*, and pytest has a first-class way to say that:
`pytest.skip(reason)`. Replacing a skip with `-k` deletes the signal (`s`, `SKIPPED [1] …`,
count in the summary) at the same time as the execution.

## Solution

### Step 1 — list the real set before choosing the mask

Never pick a `-k` expression from memory. Ask pytest what it would do:

```bash
pytest --collect-only -q -k "not A and not B and not C and not D"
```

This prints every node id the expression selects, and the summary line gives the deselection
count. Compare it against the number you intended. The extras are the bug.

### Step 2 — turn "environment missing" into an in-test `pytest.skip`, not a mask

If a test cannot run because a tool is absent, say so inside the test — the skip reason should
name the missing prerequisite and what would make the test meaningful, matching its sibling
tests in the same module:

```python
import shutil
import pytest


def test_needs_tool():
    if shutil.which("required-tool") is None:
        pytest.skip("needs required-tool; install it and this test checks the real path")
    assert real_behavior()
```

A skipped test is still reported (`1 skipped`, and with `-rs` the reason and location), so the
next reader can see that a surface exists and is currently unexercised. A deselected test is
not reported at all.

### Step 3 — remove the mask and run the full suite

With the skips in place the mask is unnecessary. Run once **without** `-k` and check the
arithmetic is self-consistent:

```
passed_after == passed_before + deselected_before
```

In the original incident that was `766 + 11 = 777 passed, 0 deselected`. A mismatch means either
a `skip` was written where a test should have stayed, or another test is still hidden.

### Step 4 — if a `-k` genuinely has to stay, keep exactly one term and say why

Some exclusions are unavoidable (for example a test a lower Python version cannot import). Keep
the expression to the **single** term that is actually necessary, and leave a comment naming the
intake or issue that forces it. A short expression is auditable; a four-term chain is not.

## Verification

Reproduced 2026-10-17 with a three-test file, selecting with `-k "not test_score_merge"` — one
intended exclusion, two tests taken:

```
$ python3 -m pytest --collect-only -q -k "not test_score_merge" test_demo.py
test_demo.py::test_always_passes

1/3 tests collected (2 deselected) in 0.01s
```

`test_score_merge_by_id` was deselected because its name *contains* `test_score_merge`. The same
over-match is what turns a four-name mask into eleven deselections.

The two forms are not equivalent, and the skip form is the one that leaves a signal:

```
$ python3 -m pytest -rs -q test_envdep.py
s                                                                        [100%]
SKIPPED [1] test_envdep.py:6: needs ... ; install it to make this test meaningful
1 skipped in 0.02s

$ python3 -m pytest -rs -q -k "not test_needs_tool" test_envdep.py

1 deselected in 0.01s
```

The masked run prints no `SKIPPED` line: the existence of the test is gone from the output.

Finally, **the gate must still be able to go red.** Introduce a deliberate failure in a test
outside the mask and confirm the suite fails. Removing a mask must not become "turn the gate
off"; if a real failure cannot make CI red, the change fixed the symptom and broke the
guarantee.

## Notes

- `-k` is a *name* filter. To exclude by marker or path, use `-m` (with `pytest.mark`) or
  `--ignore=`, which fail loudly on a typo instead of silently matching nothing or too much.
- A deselection is invisible even in a passing run's short summary; only `--collect-only` (or the
  count in the summary line) exposes the set. Treat "green" as "no selected test failed", never
  as "every test ran".
- `--collect-only` is the same instrument for the other direction too: it catches a mask that
  silently matches **nothing** (a typo deselecting zero tests while you believe it excludes four).
- Provenance: answers intake
  [#3405](https://github.com/Ikalus1988/MisakaNet/issues/3405). The small-file reproduction,
  the `pytest.skip` comparison and the counts above were run, not described; the 766/11 → 777/0
  figures are the reporting environment's measurements.
