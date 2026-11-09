---
title: "对比 upstream 跑测试判断「有没有改坏」：editable install 让测试始终导入自己的源码树"
domain: "mcp"
tags:
  - "problem"
  - "comparing"
  - "my"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3938"
summary_plain: "Comparing \"my branch\" against \"upstream\" to decide whether I broke something, by checking out upstream into a separate…"
trigger: "Problem Comparing \"my branch\" against \"upstream\" to decide whether I broke somet. Comparing \"my branch\" against \"upstream\" to decide whether I broke…"
verify: "Two numbers that must be read side by side, from the *same* interpreter with the source path forced: upstream tests x upstream code : 36 passed all tests x my code : 37 passed (upstream's 36 + my 1…"
provenance:
  issue: "#3938"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Comparing "my branch" against "upstream" to decide whether I broke something, by checking out upstream into a separate worktree and running its tests there — while the virtualenv I ran them with had an **editable install pointing at my own repo** — measured the wrong thing entirely: it ran *upstream's tests against my code*. It reported 23 failures and I nearly concluded "upstream is red too, so this is pre-existing" and shipped a regression.

## Root Cause

An editable install resolves the package to the *source tree* it was installed from, regardless of the working directory or the checkout you run the tests from. `cd <PATH> && pytest` still imports `myrepo/src/...`. The cwd changes; the import path does not.

The tell was in the traceback paths: failures inside the "clean upstream" run printed `src/mylib/module.py` — my source path — not the worktree's. Reading one traceback instead of only the summary count is what caught it.

## Fix

Before trusting a cross-tree comparison, **prove which source is actually imported**:

```
PYTHONPATH=<PATH> python -c "import mylib; print(mylib.__file__)"
```

and only then run the suite with the same `PYTHONPATH` forced. Never rely on cwd to select source when an editable install exists.

Also fix the fixture-shaped part separately: the change itself had been too rigid — it read attributes that only *some* of upstream's fixtures provide (there were two fixture shapes in the same file: some set the fields, some build a minimal object). Making the code tolerate the absent attributes rather than editing upstream's many fixtures kept the diff small and the tests honest.

## Verification

Two numbers that must be read side by side, from the *same* interpreter with the source path forced:

  upstream tests x upstream code : 36 passed
  all tests     x my code        : 37 passed  (upstream's 36 + my 1 new)

Before the fix, the same comparison (but mis-measured) read 23 failed vs 20 failed. The corrected measurement shows the branch adds one passing test and breaks nothing — which the earlier one made look like "both sides broken".

Run `python -c "import pkg; print(pkg.__file__)"` under the same interpreter/venv used for the tests, from the worktree, and confirm the printed path is inside the worktree — not the editable install's source tree. Then run both sides with PYTHONPATH pinned and compare. Confirmed: clean upstream 36 passed; the branch 37 passed; before pinning, the same commands reported 23 and 20 failures respectively, which is the shape of the false conclusion.
