---
title: "Batch import: a fake .zip killed 144 files, and a producer field the consumer needed was dropped"
domain: "nodejs"
tags:
  - "jszip"
  - "archive-validation"
  - "magic-bytes"
  - "error-isolation"
  - "producer-consumer"
  - "contract-testing"
  - "batch-import"
  - "fanuc-backup"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "批量导入按扩展名信压缩包，一个假 .zip 就让整批 144 个文件丢掉；生产者丢字段又让消费端静默返回空结果。"
trigger: "Can't find end of central directory : is this a zip file ? JSZip ipkdmp.zip RAR magic in a .zip placeholder file"
verify: "The batch analyses the 144 healthy files and reports a skipped count, and an end-to-end test from the real scan payload (including name) yields a non-empty task list."
source: "intake-3241"
provenance:
  issue: "#3241"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Batch import: a fake .zip killed 144 files, and a producer field the consumer needed was dropped

## Problem

A desktop tool imports a FANUC full-backup directory and analyses the robot programs inside it. Two
defects in that import path, both found on real backups.

**1. Trusting the extension turned one bad file into a whole-batch failure.** A FANUC full backup ships
`*.zip` files that are not all ZIPs: of the `ipkdmp.zip` files, 779 are 5-byte text placeholders (`empty`),
and other `.zip` files are actually RAR archives (`Rar!` magic). Sending them to `JSZip.loadAsync` because
of the extension throws:

```text
Can't find end of central directory : is this a zip file ?
```

The per-file loop had no per-file `try/catch`, so one bad package dropped all **144** valid program files
and the UI reported 分析失败 (analysis failed).

**2. The producer dropped a field the consumer dispatches on.** The scan endpoint returned
`{robotName, path, type, needsExtraction}` — `name` was missing. The collect layer dispatches on the
extension of `item.name` (`.ls` / `.tp` / `.zip` / `.xml`); with an empty `name` no branch matches, every
item is silently skipped, `tasks=[]`, and the user is told 未找到可识别的机器人备份 (no recognisable robot
backup found).

The tests caught neither. The unit tests and the full sweep built their own `scanned` fixtures **with**
`name` filled in, so the contract the real producer implements was never exercised: the sweep was green
and the first real selection returned nothing.

## Root Cause

Two independent causes inside one pipeline.

- **A content type inferred from a filename.** `.zip` is a label, not a format. Placeholder files,
  RAR-in-`.zip` and 7z-in-`.zip` are all "a `.zip`" to a name check and none of them is a ZIP to a ZIP
  parser. A parser that throws, inside a loop with no error boundary, has a blast radius of the whole
  batch instead of one file.
- **An implicit producer/consumer contract.** The consumer depends on a field (`name`) that the producer's
  mapped output no longer carries. Because the failure mode is a *skip* rather than an exception, it
  produces an empty result rather than an error — the loudest symptom (nothing found) with the quietest
  trace (no stack). Fixtures written by hand can only encode the field set the test author already knows,
  which is exactly the field the producer forgot.

## Solution

1. Sniff the bytes and keep the extension as a hint only. Add `sniffArchiveKind(bytes)` returning
   `zip | rar | 7z | gzip | unknown`, and route on that result. A `.zip` that sniffs as RAR or 7z goes to
   the backend decompressor that actually supports the format.
2. Give every file its own error boundary. Wrap the per-file work in `try/catch` and push failures into a
   `skipped` list the UI reports ("N files skipped"). One bad file must not be able to drop the batch.
3. Return every field the consumer reads from the producer, and let the consumer fall back. If `name` can
   be absent, the collect layer derives it from the last path segment instead of matching nothing.
4. Test the contract against the real producer shape. At least one test must feed the actual payload the
   scan endpoint returns; a fixture with the missing field hand-filled proves the fixture, not the wiring.
5. A zip that contains only `.xml` is a device dump, not a robot backup — do not create a task for it.

## Verification

The reporter's pass criteria, as run:

- `vitest` **438/438**, entry-consistency **200/200**, UI **47/47**;
- the desktop `.exe` driven over CDP against a real full backup: **190** files analysed (including the fake
  `ipkdmp.zip`), the check-result table appears, the JSZip error is gone, and the UI reports
  已跳过 104 个非程序或无法解析的文件 (skipped 104 non-program or unparseable files).

The decisive signal for defect 2 is a non-empty task list on a backup that previously produced `tasks=[]`,
from a test that starts at the real scan payload rather than at a fixture.

## Notes

- The report gives rules and counts, not the implementation: the exact `sniffArchiveKind` magic-byte table
  and the skipped-file breakdown are not in the intake — 报料者未给出，需复现确认.
- All numbers here (779 placeholder `ipkdmp.zip`, 144 dropped, 190 analysed, 104 skipped) are the
  reporter's corpus. Expect different numbers on another backup; the *shape* — one bad file costing the
  batch, and a non-empty payload yielding an empty task list — is what transfers.
- Related: `lessons/contrib/an-archive-container-name-is-not-an-entity-name.md` covers the neighbouring
  mistake in the same importer family (using the container name as the entity name).
