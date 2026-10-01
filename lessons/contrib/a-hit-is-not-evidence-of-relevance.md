---
domain: "search"
title: "A hit is not evidence of relevance — the boundary queries that must come back empty"
tags:
  - "search"
  - "relevance"
  - "retrieval"
  - "no-match"
  - "relevance-floor"
  - "boundary-queries"
  - "trust"
status: "published"
evidence_level: "E1"
created: "2026-10-01"
updated: "2026-10-01"
source: "issue-2615"
summary_plain: "搜索返回了结果不等于它对题：有人搜「怎么换机油」拿到 2 条调试课程。把「有没有匹配」和「是否相关」分开，给检索设一条下限，并把边界查询固化成回归样本。"
trigger: "search returns irrelevant results no_match relevance floor boundary query pizza car engine oil confidence"
verify: "the boundary queries in workers/search-low-relevance-queries.test.mjs come back no_match, and its positive control still finds its lesson"
provenance:
  issue: "#2615"
---

## Problem

Measured on the corpus (2026-10-01): the query **`how do I fix my car engine oil change`** returned **2
results**. The query **`best pizza recipe with mozzarella`** returned none. Both are outside what this corpus
knows about, and only one of them was answered anyway.

That asymmetry is the whole problem. A search that returns nothing is *legible*: the caller learns "there is
nothing here". A search that returns two plausible-looking lessons for a question about engine oil is not —
and the caller is an agent that has been told to treat retrieved content as evidence. A wrong hit is worse
than no hit, because it is consumed silently.

## Root Cause

Two different questions get collapsed into one similarity number:

* **existence** — "is there anything in here about this?";
* **relevance** — "is this result *about* the query?".

Lexical scoring answers the first and only approximates the second. Rare terms make this worse in a specific
way: a query word that is **absent from the whole corpus** has maximal idf, so it inflates the score of any
document that matches *any other* word — and if the denominator and numerator of a relevance floor are computed
over different term sets (say, the user's words versus the alias-expanded ones), an expansion term can supply
mass the denominator never contained. That is how a query with no coverage at all clears a 0.55 coverage floor
at 0.677.

The second half of the cause is design rather than maths: teams treat "returned something" as success, so the
no-match path is never built. There is no honest answer available for the case that is actually common —
**the corpus does not cover this topic yet**.

## Solution

1. **Make `no_match` a first-class answer**, not an empty array with a 200. Say that nothing matched, and carry
   the next step with it: the intake path, so the gap can be filed instead of guessed at. An agent that knows
   the corpus is empty on a topic will say so; an agent handed two weak hits will cite them.
2. **Floor over one term space.** The numerator and the denominator must be computed from the **same** terms —
   the ones the query actually contains. Expansion and aliasing belong in *ranking*, where they can reorder
   candidates, not in the admission test, where they can manufacture coverage.
3. **Require the query's own content words to be covered**, not just any word. "Engine" appearing in a lesson
   is not coverage for "engine oil change"; a query whose distinctive terms are absent is a query this corpus
   cannot answer.
4. **Do not implement any of this with a keyword blacklist.** It is the tempting shortcut for exactly the
   queries in this lesson, and it breaks the corpus's own vocabulary: short, high-frequency terms like `serve`
   and `mcp` are legitimate queries here, and a blocklist tuned on pizza will refuse them next month.
5. **Keep a positive control in the same test file as the negatives.** A floor that refuses everything passes
   every negative assertion — and it is a different bug, not a fix.

## Verification

```bash
node --test workers/search-low-relevance-queries.test.mjs
```

Six boundary queries must come back `no_match` (pizza, engine oil, sourdough, keyboard mashing, `0x0a`, and a
sentence pulled from the corpus's own chatter), and one covered query — `pip install timeout corporate proxy`
— must still find `pip-install-proxy-timeout`. Both halves in one file, because either half alone can be
satisfied by breaking the other.

The historical detail is worth keeping in the test: the engine-oil query returned 2 results before the floor
work, so a future failure there is a regression with a known shape, not a new mystery.

## What not to do

- Do not "improve" recall by lowering the floor until the negatives pass. That is how the engine-oil answer
  happened; the two properties pull in opposite directions and only measurement decides.
- Do not answer an uncovered query with the best of a bad set. For a knowledge corpus, "nothing yet, here is
  how to file it" is the useful answer.
- Do not tune the floor on the negative set alone. Add queries the corpus *should* cover and assert they still
  resolve, or the fix silently becomes a mute button.
- Do not blame the ranker first. If a query with no coverage is admitted, the problem is the admission test.

## For agents working on this

When a search returns results, check **why** they matched before using them — the query's own words, the
domain, the rank — and treat "nothing matched" as information rather than a failure to work around. When you
report a retrieval result, quote the query and the ids you got; if a query returned hits that do not look like
the topic, that is a gap to file, and the boundary queries above are the shape of the evidence that gets it
fixed.
