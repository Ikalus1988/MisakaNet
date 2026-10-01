---
domain: "development"
title: "A source that does not exist must not resolve to a default — the bug that reports 'pending' forever"
tags:
  - "design"
  - "error-handling"
  - "defaults"
  - "fail-loudly"
  - "state-derivation"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "intake-2605"
summary_plain: "读取一个不存在的来源时返回默认值，会把「事实不存在」伪装成「状态是默认那个」：功能永远显示 pending、永远不报错。缺席要么是错误，要么必须写明为什么等于那个值。"
trigger: "missing file returns default never errors feature stuck pending silent fallback .get default state derivation"
verify: "delete the source (file, key, row) and the feature raises or reports the absence — it does not keep reporting its default state"
provenance:
  issue: "#2605"
---

## Problem

A feature derives its state from a source that does not exist, and reports the **default** instead of failing.
Two shapes were reported in the same project, weeks apart:

* reading a file that is not in the repository — the reader returned an empty/default value, so the feature
  reported "pending" for every record, forever;
* reading frontmatter keys that no record actually has — the lookup returned the default, so the summary said
  everything was unconfigured rather than that the field was never written.

In both cases there was no error to notice, the logs were clean, and the tests passed. The only symptom was a
screen that never changed.

## Root Cause

The code conflates two different facts:

* **absence** — "the source is not there". This is information, and at the boundary that knows what the source
  *means*, it is usually a **bug or a broken assumption**;
* **default** — "if a value is missing, treat it as X". This is a **decision** about semantics, and it is only
  correct where someone can say *why* X is the right meaning of missing.

Written as a one-liner, the decision wins silently:

```python
state = read_source().get("state", "pending")     # absence and "pending" become the same answer
```

Every layer that does this compounds it: a missing file yields `{}`, `{}` yields the default, the default yields
"pending", and "pending" is a legitimate-looking state, so nothing downstream can tell that the input was never
there. The failure is not that the default is wrong — it is that **the reason for the default was never
established**.

The reason this keeps shipping is that the fallback is the convenient path: it makes the happy-path test pass,
it makes an unpopulated environment "work", and it turns a loud missing-file error into a quiet empty result.
It is exactly the trade that makes a feature impossible to debug later.

## Solution

Make the absence visible at the boundary, and let only the layer that knows the semantics decide:

```python
def load_state(path: Path) -> State:
    if not path.exists():
        raise SourceMissing(path)          # absence is a fact, not a value
    return parse(path.read_text(encoding="utf-8"))

def state_for(record, state: State) -> str:
    # here absence has a *documented* meaning: this record never declared a state
    return state.by_id.get(record.id, Decision.default_for_undeclared())
```

Three rules that keep it honest:

1. **Separate the three outcomes**: present, absent, unreadable (permission, parse error). Collapsing them is
   what hides the difference between "nobody wrote it" and "I could not read it".
2. **Default only where you can write the sentence.** If the answer is "because a record that never declared a
   state is pending until someone claims it", fine — put that sentence in a comment or a test name. If you
   cannot write it, you are hiding an absence.
3. **Test the missing case explicitly.** The test that matters is the one where the source is **absent**: delete
   the file (or the key) and assert that the feature raises, or reports *absent* — never that it still reports
   its default. An assertion that cannot distinguish those is the "cannot fail" test again.

If your platform makes absence an exception already (`KeyError`, `FileNotFoundError`), do not catch it just to
return the default somewhere far from the place that knows why. Let it travel to the boundary that can act on
it.

## Verification

The check is a deletion, not a reading:

```bash
rm -rf <the source the feature derives from>       # the file, the table, the key
<run the feature>
# PASS: it raises, or reports the absence, and says which source was missing
# FAIL: it reports "pending" (or any other legitimate-looking state) with no error
```

Do this once for **each** shape: a missing whole source, and a missing field inside a source that exists. The
second is the one that hides longest, because the file is there and only the key is not.

## What not to do

- Do not reach for `.get(key, default)` as a reflex; reach for it only after deciding what absence means.
- Do not catch the exception and return the default one layer above where it was raised — that discards the
  only place that knew the difference.
- Do not conclude "it never happens in practice". A missing file is exactly what happens when a build step,
  a packaging rule, or a `.gitignore` forgets to ship it — and the default is what hides it until production.
- Do not fix the symptom by making the default more informative ("pending (source missing)"). That is the same
  silence with a longer string; fail instead.

## For agents working on this

When a feature reports a value that never changes, check whether its input is actually present before debugging
the logic — and say which of the three (present / absent / unreadable) you observed. If you are the one writing
the fallback, write down why absence equals that value, or make it an error. "It made the test pass" is the
reason the bug exists.
