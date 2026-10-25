---
title: "A two-step regex rewrite silently cut a 1648-line changelog to 81 lines; check the delta and the tail"
domain: "python"
tags:
  - "python"
  - "regex"
  - "string-slicing"
  - "changelog"
  - "silent-truncation"
  - "data-loss"
  - "diff-stat"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "两步正则改写把 1648 行的变更日志改成 81 行，内容读起来还很对——收尾那行被当成了整段历史的替身。"
trigger: "regex rewrite dropped historic sections; changelog went from 1648 lines to 81"
verify: "改写前后行数差等于预期净增行数；新文件以原文尾部结尾；章节计数正好 +1"
source: "intake-3614"
provenance:
  issue: "#3614"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A two-step regex rewrite silently cut a 1648-line changelog to 81 lines; check the delta and the tail

## Problem

A 1600+ line structured document — a version changelog with dozens of release sections — was edited
with a two-step regex rewrite in Python:

1. insert the new version section,
2. reorder the subsections **inside** the new section.

Read separately, both steps were correct. The result *looked* correct too: the new section was there,
its subsection order was right, and the document ended where it was supposed to end. What was not
correct: **the file went from 1648 lines to 81 lines.** Dozens of historical version sections were
gone.

The reason nobody caught it is the shape of the damage: the surviving text is fluent and
self-consistent. A reader re-reading the file looks at the newly written head, sees what they wrote,
and stops. No test covered the file, and no lint rule reports "the history sections are missing".

## Root Cause

Step 2 rebuilt the document as:

```python
s = s[:m.start()] + head + body2 + tail
```

`tail` was only the **single heading line** of some version — `## [x.y.z]` — while the ~1580 lines
that belong after that heading lived in `s[m.end():]` and were **never spliced back**. One heading
line was substituted for "heading plus everything under it".

Two properties of the tooling turned this into silent data loss:

- **Python string slicing never complains.** `s[:a] + new + s[b:]` with the wrong `b` produces a
  shorter string, not an error, not a warning.
- **Step 1's correctness masked step 2's bug.** After both steps the combined result reads as the new
  content; there is no obvious seam where the tail should have been. And because `tail` *was* a real
  heading line from the document, even a "is the tail still there" spot check passed — the check
  found the heading that step 2 had itself put there.

## Solution

### Step 1 — Never trust readability after a slice-based rewrite

For structured large files (CHANGELOG, migration lists, generated JSON, index files), a batch regex
or slice replacement is verified by **counts**, not by reading.

### Step 2 — Assert the delta before writing

Record the line count before the edit and require the after-minus-before delta to equal the net lines
you intended to add. In this incident the intended delta was **+13**; the actual was **−1567**, which
is a difference no amount of reading was going to reveal.

```python
before = len(original.splitlines())
new = rewrite(original)
expected_delta = 13                      # lines the new section adds
assert len(new.splitlines()) - before == expected_delta, (
    f"line delta {len(new.splitlines()) - before:+d}, expected {expected_delta:+d}"
)
```

### Step 3 — Splice explicitly and assert the tail survived

Make the "everything after the anchor" part a named value, and assert it is non-empty and still at the
end of the result:

```python
rest = original[m.end():]
assert rest, "nothing after the anchor — the match is wrong"
assert new.endswith(original[-80:]), "tail of the original is missing from the rewrite"
```

An anchored `assert old in s` before replacing (uniquely matched) is the cheap version of the same
guard: it fails loudly when the pattern drifts instead of silently replacing the wrong span.

### Step 4 — Count the structure, not just the bytes

The document's structure is countable: the number of version headings before and after must differ by
exactly the number of versions you added. Here the heading count had to go 63 → 64, i.e. **+1 and
nothing else**.

```python
assert len(re.findall(r"(?m)^## \[", new)) == len(re.findall(r"(?m)^## \[", original)) + 1
```

### Step 5 — Look at the diff stat before committing

Even with no assertions written, `git diff --stat` is a free backstop: insertions and deletions
should be the same order of magnitude as the intended edit. **This is how the bug was actually
found** — `-1591 deletions` for an edit that only added a section. If deletions far exceed the lines
you wrote, a slice removed more than it should have.

## Verification

All three must hold before the edit is accepted:

1. **Line delta:** after-minus-before equals the expected net gain (+13 here). The wrong expression
   gives −1567 and is caught immediately.
2. **Tail integrity:** the result still ends with the original file's final bytes (e.g. its last 80
   bytes unchanged), so the document's true end is present, not just *some* heading.
3. **Structure count:** the version-heading count goes 63 → 64 — exactly one new section, no
   collateral removal.

With these three in place the reporter's original wrong expression is rejected at the assertion, and
the corrected rewrite produces delta +13, an identical tail, and 64 sections.

## Notes

- The reporter's two-step script itself was not included in the intake — the expression above is the
  one quoted in the report; the surrounding code needs reproduction to confirm.
- Same family, different mechanism: silent truncation from a read tool or a cap
  (`lessons/contrib/agent-readfile-silent-truncation.md`). Here the truncation is caused by the
  writer's own slice arithmetic, which no reader-side guard would catch.
