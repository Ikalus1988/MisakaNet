---
provenance:
  issue: "#3283"
  source: "MCP intake (claude-code), contributor-reported"
domain: "nodejs"
title: "JS regex: escape a literal dollar sign, never escape the end-of-line anchor"
tags:
  - "regex"
  - "javascript"
  - "nodejs"
  - "escaping"
  - "anchors"
  - "classifier"
  - "silent-failure"
  - "testing"
status: "published"
evidence_level: "E1"
created: "2026-10-17"
updated: "2026-10-17"
source: "intake-3283"
summary_plain: "在 JS 正则里 `$` 有时是行尾锚点、有时是字面量，转义写反会让分类规则整类静默失配。"
trigger: "JS regex dollar escaping literal vs end anchor trailing _TIM$ _STAT$ mid-word \\$DCS_C classifier default branch wrong category"
verify: "classify('$DCS_C_SSO[1]') hits the high-priority branch and classify('$SLSCHED1[1].ID1_1ST_TIM') the low one; un-escaping the mid-word \\$ turns the first assertion red."
---

## Problem

A field-name classifier built out of JavaScript regular expressions silently returned the
**wrong category** for two whole families of real field names, with no exception and no log
line. Fields beginning with a literal `$` (`$DCS_C_SSO`) and fields ending in `_TIM`
(`ID1_1ST_TIM`) never matched the branches written for them and fell through to the default
return value, so callers saw a plausible-looking but wrong class:

```
expected 'high' to be 'medium'
expected 'medium' to be 'low'
```

Unit tests passed the whole time, because their synthetic field names did not contain the
two characters that mattered. The gap only appeared when the classifier was run over a real
corpus of field names and the priority distribution was compared against a manual sample.

## Root Cause

In JavaScript a bare `$` is not a character — it is a **zero-width end-of-input assertion**
(and, with the `m` flag, an end-of-line assertion). A literal dollar sign must be escaped as
`\$`. The classifier got that rule backwards in both directions:

```js
// WRONG — each rule is dead for every real input
/^$DCS_C_(SSO|CSO)/   // `$` left bare in the middle: `^` then END-OF-INPUT then `DCS_C`,
                      // which can never match -> `$DCS_C_SSO` is never classified
/_TIM\$/              // the trailing anchor was escaped into a literal: this wants the
                      // text `_TIM$`, but the input ends at `_TIM` -> never matches
```

- `^$DCS_C_(SSO|CSO)` — `^` asserts start, `$` asserts end, and then `DCS_C` is expected
  *after* the end of input. The pattern matches nothing, ever.
- `_TIM\$` — `\$` is a literal `$`, so the regex looks for the five characters `_TIM$`
  at the end of the string. The field ends in `_TIM` with no dollar, so it never matches.

A third shape appears wherever a literal dollar sits after another escaped metacharacter,
e.g. `\.$PAYLOAD`: the `.` is escaped correctly, so the author assumes no other escaping is
needed — but `$PAYLOAD` still needs `\$PAYLOAD`.

The default branch made the failure invisible. `classify()` returned a real business class
(`medium`) for input it did not recognize, so a broken rule always presented as "classified
into the wrong bucket" and never as "no rule matched".

## Fix

Two rules, applied by where the `$` sits:

1. **A `$` in the middle of a token is a literal — write `\$`** (`$SBR`, `$DCS_C`,
   `\.$PAYLOAD`). **A `$` at the end of the pattern is the end-of-input anchor — do not
   escape it** (`_TIM$`, `_STAT$`).

   ```js
   // RIGHT
   /^\$DCS_C_(SSO|CSO)/   // `\$` = literal dollar at the start of the field
   /_TIM$/                // `$`  = the field ends there
   ```

2. **Never let the default branch return a business class.** An unrecognized shape must be
   explicit, so a broken rule reads as "not matched" instead of "matched something else".

   ```js
   function classify(field) {
     if (/^\$DCS_C_(SSO|CSO)/.test(field)) return 'high';
     if (/_TIM$/.test(field)) return 'low';
     return 'unknown'; // NOT 'medium': an unknown shape must not masquerade as a real class
   }
   ```

   If `unknown` is unacceptable downstream, keep the fallback but make it observable — emit a
   counter or a log line for every default hit, so a silent rule regression is visible.

When you write or change such a rule, assert on the **field names** you expect to hit and on
the neighbouring field names you expect *not* to hit, not only on the returned tier. A tier
assertion cannot tell "the rule matched and ranked it" from "nothing matched and the default
happened to be that tier".

## Verification

Use real corpus field names for both directions of each rule:

```js
assert(classify('$DCS_C_SSO[1]') === 'high');                 // mid-word `$` must be a literal
assert(classify('$SLSCHED1[1].ID1_1ST_TIM') === 'low');       // trailing `$` must be an anchor
assert(classify('$DCS_C_SSO[1]') !== 'unknown');              // and it must not be the fallback
```

Then deliberately break the escaping and confirm the tests turn **red** — either mistake
must fail an assertion, or the tests are decoration:

```js
/^$DCS_C_(SSO|CSO)/.test('$DCS_C_SSO[1]')  // false -> `expected 'high', got 'unknown'`
/_TIM\$/.test('$SLSCHED1[1].ID1_1ST_TIM')  // false -> `expected 'low', got 'unknown'`
```

Finally, sweep the real corpus and compare the priority distribution and the `unknown`
count against a manual sample; the `unknown` count is the signal that a rule is not firing.

## Notes

- The same distinction exists in other regex dialects, but the failure is *quiet* in
  JavaScript because `$` is never a syntax error there: `^$DCS_C` is a valid regex that
  simply matches nothing. An invalid pattern would have thrown; this one did not.
- Inside a character class (`[$@]`) a `$` is literal and needs no escape; the rule above is
  about `$` used as a standalone token.
- Related lessons: `lessons/contrib/regex-escaped-quotes-source-parsing.md` and
  `lessons/contrib/regex-greedy-matching.md` (other regex rules that fail silently on real
  input while passing synthetic tests).
