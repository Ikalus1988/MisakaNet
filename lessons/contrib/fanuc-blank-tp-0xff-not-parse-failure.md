---
title: "FANUC blank .tp files that read as 0xFF are placeholders, not parse failures"
domain: "fanuc"
tags:
  - "fanuc"
  - "tp-file"
  - "blank-placeholder"
  - "decompiler"
  - "pns"
  - "acc-extraction"
  - "error-classification"
  - "backup"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "FANUC 备份里整块 0xFF 的 .tp 是空壳占位而不是损坏，要单独计数，不能算成解析失败。"
trigger: "TP容器: magic 错误 ff ff  .tp 文件解析报错 全是 0xFF"
verify: "同一批备份的统计里 blank 与 tpFail 分开计数，且 PNS 全为空壳的机器人标注「不可读」而不是 ACC=0。"
source: "intake-3569"
provenance:
  issue: "#3569"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# FANUC blank .tp files that read as 0xFF are placeholders, not parse failures

## Problem

Parsing a FANUC robot backup tree, a large number of `.tp` files made the decompiler fail with:

```
TP容器: magic 错误 ff ff
```

The symptom reads like data corruption or a decompiler bug — hundreds of files "refusing" to parse — so
the obvious move is to count them as parse failures and report "N files failed to decompile". That
count is a false alarm, and it is not the only cost: on robots whose PNS scheduler programs happen to
be blank, the extracted ACC value came out as a false `0`, because every PNS read failed and the
extractor fell back to its zero default.

## Root Cause

A FANUC controller leaves an all-`0xFF` residue on disk when a `.tp` file is deleted or was never
written — anything from a few hundred bytes to a few KB. Reading such a file, `parseTp` sees
`magic = 0xFFFF` and errors out immediately.

The correct discriminator is "is the whole file `0xFF`", which the reporter's `isBlankTp` helper
checks — a blank shell is a distinct third state, not a corruption of a real program. Tool chains that
only look at the thrown exception cannot tell the two apart, so they fold "nothing was ever written
here" into "this program is broken / unreadable", and every downstream statistic inherits that fold.
The ACC damage is the sharper version of the same mistake: `0` is a *value*, and writing `0` for "could
not read it" makes an unreadable robot indistinguishable from a robot that genuinely has no ACC
instruction.

## Solution

Gate the parse on the blank check first, and count the two outcomes separately:

```js
if (isBlankTp(buf)) { stats.blank++; continue }      // empty shell — skip, not a failure
try { text = tpToLs(buf) } catch { stats.tpFail++ }  // real parse failure
```

Then apply three rules to everything downstream:

1. **Report `blank` and `tpFail` as separate counters.** Never fold blank shells into a "failed" total;
   a "decompile failures: 0" line is only meaningful next to the blank count.
2. **Classify in front of the parse attempt, not after the exception.** The blank check must be
   available to callers that have no decompiler at all — otherwise the same file is "blank" to one
   tool and "corrupt" to the next.
3. **Do not emit `0` for an unreadable PNS.** When a robot's PNS programs are all blank (the reporter
   names BIR020R01 and FI060R21/FI060R23), the ACC result is unknown, not zero: mark it
   "PNS unreadable" so a dashboard cannot read it as a measured zero.

## Verification

Reporter-reported criteria (not independently reproduced here):

- **BIR020R01**: PNS0010/0012/0021/0031 are all `0xFF` (32 blank shells). The ACC extraction returns
  0 while the call chain cannot be read → must be labelled unreadable, not 0.
- **FI080R01**: PNS fully readable, so ACC = 0 is a true value (a welding robot with no `ACC > 100`
  instruction). This is the control case: the same `0` means two different things depending on which
  side of the blank check it came from.
- **Full run over 305 robots** (the reporter's `2606` batch): with `blank` and `tpFail` split, real
  decompile failures = 0.

The check that fails without the fix: a run that reports "N decompile failures" on a backup where N
equals the number of all-`0xFF` shells. Pass = those files appear under `blank` and `tpFail` is the
number you would defend individually.

## Notes

`isBlankTp` is described by the reporter only as "the whole file is `0xFF`". The exact tolerance —
whether a partially written file (say, a `0xFF` body with a real header) counts as blank, and how
trailing padding is handled — is **报料者未给出，需复现确认**.

The `2606` batch identifier is quoted as the reporter wrote it; it is not expanded here.
